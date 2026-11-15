from .service import get_db, CHUNKS_COLLECTION, DOCS_COLLECTION

db = get_db()
valid = {d["doc_id"] for d in db[DOCS_COLLECTION].find({}, {"doc_id": 1})}
res = db[CHUNKS_COLLECTION].delete_many({"doc_id": {"$nin": list(valid)}})
print("removed", res.deleted_count)