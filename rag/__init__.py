"""RAG (retrieval-augmented generation) package for Renewed AI Tutor."""
from .service import (
    ingest_document,
    retrieve,
    format_context,
    list_documents,
    delete_document,
    NO_CONTEXT,
)

__all__ = [
    "ingest_document", "retrieve", "format_context",
    "list_documents", "delete_document", "NO_CONTEXT",
]
