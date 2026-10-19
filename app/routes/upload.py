import io
import uuid

from docx import Document as DocxDocument
from fastapi import APIRouter, Depends, UploadFile
from pypdf import PdfReader

from app.auth import get_current_user
from app.models.schemas import UploadResponse
from app.services import answer_cache, users
from app.services.chunking import chunk_text
from app.services.embeddings import embed_texts
from app.services.retrieval import store_chunks

router = APIRouter()


def _extract_text(filename: str, raw: bytes) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(raw))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if lower.endswith(".docx"):
        doc = DocxDocument(io.BytesIO(raw))
        return "\n".join(p.text for p in doc.paragraphs)
    return raw.decode("utf-8")


@router.post("/", response_model=UploadResponse)
def upload_document(file: UploadFile, user: dict = Depends(get_current_user)):
    raw = file.file.read()
    text = _extract_text(file.filename, raw)

    chunks = chunk_text(text)
    embeddings = embed_texts(chunks, input_type="document")

    document_id = str(uuid.uuid4())
    store_chunks(user["id"], document_id, chunks, embeddings)
    users.add_document(user["id"], document_id, file.filename, len(chunks))
    answer_cache.documents_changed(user["id"])

    return UploadResponse(document_id=document_id, chunks_created=len(chunks))
