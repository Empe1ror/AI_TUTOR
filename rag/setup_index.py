"""Run ONCE:  python -m rag.setup_index
Creates the Atlas Vector Search index the retriever needs.
(Requires MongoDB Atlas; it takes a minute or two to become 'READY'.)
"""
from .service import CHUNKS_COLLECTION, EMBED_DIMS, INDEX_NAME, get_db, get_store

db = get_db()
if CHUNKS_COLLECTION not in db.list_collection_names():
    db.create_collection(CHUNKS_COLLECTION)

if list(db[CHUNKS_COLLECTION].list_search_indexes(INDEX_NAME)):
    print(f"Index '{INDEX_NAME}' already exists.")
else:
    get_store().create_vector_search_index(
        dimensions=EMBED_DIMS,
        filters=["user_id", "doc_id"],   # fields we filter on during search
        wait_until_complete=120,
    )
    print(f"Index '{INDEX_NAME}' created with {EMBED_DIMS} dimensions.")
