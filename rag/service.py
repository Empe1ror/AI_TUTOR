"""Ingest, store, and retrieve study documents (MongoDB Atlas Vector Search).

Flow:  upload -> extract text -> split into chunks -> embed -> store in MongoDB
       question -> embed question -> vector search (this user's chunks only)
                -> put best chunks into the prompt as {context}
"""
import hashlib
import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_mongodb import MongoDBAtlasVectorSearch
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pymongo import MongoClient

from .loaders import extract_text

load_dotenv()

DB_NAME = "tutor_database"
CHUNKS_COLLECTION = "rag_chunks"      # one document per text chunk (+ embedding)
DOCS_COLLECTION = "rag_documents"     # one document per uploaded file
INDEX_NAME = "rag_vector_index"

# The embedding model decides the vector size. EMBED_DIMS must match it AND the
# Atlas index. Check NVIDIA Build for an embedding model your key can use.
EMBED_MODEL = os.getenv("EMBED_MODEL", "nvidia/nemotron-3.5-embed-1b")
EMBED_DIMS = int(os.getenv("EMBED_DIMS", "2048"))


CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
MAX_FILE_MB = 10
NO_CONTEXT = "No uploaded documents, or nothing relevant was found for this question."

_client = None
_store = None


def get_db():
    global _client
    uri = os.getenv("MONGODB_URI")
    if not uri:
        raise RuntimeError("MONGODB_URI is not set.")
    if _client is None:
        _client = MongoClient(uri, serverSelectionTimeoutMS=20000)
    return _client[DB_NAME]


def get_store() -> MongoDBAtlasVectorSearch:
    global _store
    if _store is None:
        embeddings = NVIDIAEmbeddings(
            model=EMBED_MODEL,
            api_key=os.getenv("NVIDIA_EMBEDING_KEY"),
            base_url=os.getenv("NVIDIA_BASE_URL"),
        )
        _store = MongoDBAtlasVectorSearch(
            collection=get_db()[CHUNKS_COLLECTION],
            embedding=embeddings,
            index_name=INDEX_NAME,
            relevance_score_fn="cosine",
        )
    return _store


def ingest_document(user_id: str, filename: str, data: bytes) -> dict:
    """Process one uploaded file. Returns its record; 'duplicate': True if already stored."""
    if len(data) > MAX_FILE_MB * 1024 * 1024:
        raise ValueError(f"File is larger than {MAX_FILE_MB} MB.")

    docs_col = get_db()[DOCS_COLLECTION]
    file_hash = hashlib.sha256(data).hexdigest()
    existing = docs_col.find_one({"user_id": user_id, "file_hash": file_hash}, {"_id": 0})
    if existing:
        return {**existing, "duplicate": True}

    pages = extract_text(filename, data)  # raises ValueError with a friendly message
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)

    doc_id = uuid.uuid4().hex
    chunks: list[Document] = []
    for text, page in pages:
        for piece in splitter.split_text(text):
            chunks.append(Document(
                page_content=piece,
                metadata={
                    "user_id": user_id,   # privacy: every search filters on this
                    "doc_id": doc_id,
                    "filename": filename,
                    "page": page,
                    "chunk_index": len(chunks),
                },
            ))
    if not chunks:
        raise ValueError("Nothing to index after processing this file.")

    store = get_store()
    skipped = 0

    def add_safely(batch):
        """Try the whole batch; if the content filter rejects it, split to isolate the bad chunk(s)."""
        nonlocal skipped
        try:
            store.add_documents(batch)
        except Exception as exc:
            msg = str(exc).lower()
            if "content safety" not in msg and "422" not in msg:
                raise                      # network/key/other problem: don't hide it
            if len(batch) == 1:
                skipped += 1               # this single chunk is rejected: skip it
                return
            mid = len(batch) // 2
            add_safely(batch[:mid])
            add_safely(batch[mid:])

    try:
        for i in range(0, len(chunks), 32):
            add_safely(chunks[i:i + 32])
        stored = len(chunks) - skipped
        if stored == 0:
            raise ValueError("Every section of this file was rejected by the embedding service's content filter.")
    except Exception:
        # don't leave half-saved chunks behind
        get_db()[CHUNKS_COLLECTION].delete_many({"user_id": user_id, "doc_id": doc_id})
        raise

    record = {
        "user_id": user_id, "doc_id": doc_id, "filename": filename,
        "file_hash": file_hash, "n_chunks": stored, "skipped_chunks": skipped,
        "created_at": datetime.now(timezone.utc),
    }
    docs_col.insert_one(dict(record))
    return {**record, "duplicate": False}

def retrieve(user_id: str, query: str, k: int = 4, min_score: float = 0.0, doc_ids=None):
    """Return [(Document, score), ...] from THIS user's documents only."""
    if get_db()[DOCS_COLLECTION].count_documents({"user_id": user_id}, limit=1) == 0:
        return []  # no uploads: skip the embedding call entirely
    pre_filter = {"user_id": {"$eq": user_id}}
    if doc_ids:
        pre_filter["doc_id"] = {"$in": list(doc_ids)}
    results = get_store().similarity_search_with_score(query, k=k, pre_filter=pre_filter)
    return [(d, s) for d, s in results if s >= min_score]


def format_context(results) -> tuple[str, list[dict]]:
    """Build the text block for the prompt, plus a source list for the UI."""
    if not results:
        return NO_CONTEXT, []
    blocks, sources = [], []
    for n, (doc, score) in enumerate(results, start=1):
        m = doc.metadata
        label = m.get("filename", "document") + (f", page {m['page']}" if m.get("page") else "")
        blocks.append(f"[{n}] ({label})\n{doc.page_content}")
        sources.append({"n": n, "label": label, "score": round(float(score), 3),
                        "text": doc.page_content})
    return "\n\n".join(blocks), sources


def list_documents(user_id: str) -> list[dict]:
    cur = get_db()[DOCS_COLLECTION].find({"user_id": user_id}, {"_id": 0, "file_hash": 0})
    return list(cur.sort("created_at", -1))


def delete_document(user_id: str, doc_id: str) -> None:
    get_db()[CHUNKS_COLLECTION].delete_many({"user_id": user_id, "doc_id": doc_id})
    get_db()[DOCS_COLLECTION].delete_one({"user_id": user_id, "doc_id": doc_id})
