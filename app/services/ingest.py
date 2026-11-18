"""
Turns an uploaded file into searchable chunks: extract text -> semantic
chunking -> embeddings -> ChromaDB, and records the document's owner.
"""

import io
import uuid

from docx import Document as DocxDocument
from pypdf import PdfReader

from app.services import answer_cache, users
from app.services.chunking import chunk_text
from app.services.embeddings import embed_texts
from app.services.retrieval import store_chunks


def extract_text(filename: str, raw: bytes) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(raw))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if lower.endswith(".docx"):
        doc = DocxDocument(io.BytesIO(raw))
        return "\n".join(p.text for p in doc.paragraphs)
    return raw.decode("utf-8")


def ingest(user_id: str, filename: str, raw: bytes) -> dict:
    """Returns {"id", "filename", "chunks"} for the new document."""
    chunks = chunk_text(extract_text(filename, raw))
    embeddings = embed_texts(chunks, input_type="document")

    document_id = str(uuid.uuid4())
    store_chunks(user_id, document_id, chunks, embeddings)
    users.add_document(user_id, document_id, filename, len(chunks))
    answer_cache.documents_changed(user_id)
    return {"id": document_id, "filename": filename, "chunks": len(chunks)}
