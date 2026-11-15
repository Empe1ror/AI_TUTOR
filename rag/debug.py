from .service import get_db, get_store, CHUNKS_COLLECTION, EMBED_DIMS, INDEX_NAME

db = get_db()
print("chunks stored:", db[CHUNKS_COLLECTION].count_documents({}))

sample = db[CHUNKS_COLLECTION].find_one()
if sample:
    print({k: (f"<{len(v)} floats>" if k == "embedding" else v)
           for k, v in sample.items() if k != "_id"})

store = get_store()
print("EMBED_DIMS setting:", EMBED_DIMS,
      "| actual model output:", len(store._embedding.embed_query("test")))

for idx in db[CHUNKS_COLLECTION].list_search_indexes(INDEX_NAME):
    print("index:", idx)   # check status/queryable and numDimensions

q = "a phrase that appears in your document"
print("no filter :", store.similarity_search_with_score(q, k=3))
print("with filter:", store.similarity_search_with_score(
    q, k=3, pre_filter={"user_id": {"$eq": "your_student_id"}}))