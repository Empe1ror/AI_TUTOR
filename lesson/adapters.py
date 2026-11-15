"""Glue between lesson mode and other parts of the project (kept out of the engine)."""


def rag_retriever(user_id: str, doc_ids=None, k: int = 4):
    """Return a retriever(query) -> (context_text, sources) backed by the existing rag package."""
    def _retrieve(query: str):
        from rag import format_context, retrieve
        return format_context(retrieve(user_id, query, k=k, doc_ids=doc_ids))
    return _retrieve
