"""Step 1 of RAG: turn an uploaded file into plain text.

Returns a list of (text, page_number) pairs. page_number is None for formats
without pages (txt, md, docx), so answers can cite "page 3" for PDFs.
"""
from io import BytesIO

SUPPORTED_TYPES = ["pdf", "txt", "md", "docx"]


def extract_text(filename: str, data: bytes) -> list[tuple[str, int | None]]:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "pdf":
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(data))
        pages = [((p.extract_text() or "").strip(), i + 1) for i, p in enumerate(reader.pages)]
        pages = [(t, n) for t, n in pages if t]
        if not pages:
            raise ValueError(
                "No readable text found. This PDF may be a scan (images only). "
                "Run OCR on it first, or upload a text-based PDF."
            )
        return pages

    if ext in ("txt", "md"):
        text = data.decode("utf-8", errors="ignore").strip()
        if not text:
            raise ValueError("The file is empty.")
        return [(text, None)]

    if ext == "docx":
        from docx import Document
        doc = Document(BytesIO(data))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        if not text:
            raise ValueError("No readable text found in this Word file.")
        return [(text, None)]

    raise ValueError(f"Unsupported file type '.{ext}'. Use: {', '.join(SUPPORTED_TYPES)}.")
