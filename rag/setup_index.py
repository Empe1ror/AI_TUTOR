"""Run:  python -m rag.setup_index
Creates the Atlas Vector Search index, replacing it if the dimensions are wrong."""
import time
from .service import CHUNKS_COLLECTION, EMBED_DIMS, INDEX_NAME, get_db, get_store

db = get_db()
if CHUNKS_COLLECTION not in db.list_collection_names():
    db.create_collection(CHUNKS_COLLECTION)
col = db[CHUNKS_COLLECTION]

existing = list(col.list_search_indexes(INDEX_NAME))
if existing:
    fields = existing[0].get("latestDefinition", {}).get("fields", [])
    dims = next((f.get("numDimensions") for f in fields if f.get("type") == "vector"), None)
    if dims == EMBED_DIMS:
        print(f"Index '{INDEX_NAME}' already exists with {dims} dimensions.")
        raise SystemExit
    print(f"Index has {dims} dimensions, need {EMBED_DIMS}. Dropping it...")
    col.drop_search_index(INDEX_NAME)
    while list(col.list_search_indexes(INDEX_NAME)):
        time.sleep(3)

get_store().create_vector_search_index(
    dimensions=EMBED_DIMS,
    filters=["user_id", "doc_id"],
    wait_until_complete=120,
)
print(f"Index '{INDEX_NAME}' created with {EMBED_DIMS} dimensions.")