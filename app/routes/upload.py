import io
import uuid

from docx import Document as DocxDocument
from fastapi import APIRouter, UploadFile
from pypdf import PdfReader

from app.models.schemas import UploadResponse
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
def upload_document(file: UploadFile):
    raw = file.file.read()
    text = _extract_text(file.filename, raw)

    chunks = chunk_text(text)
    embeddings = embed_texts(chunks, input_type="document")

    document_id = str(uuid.uuid4())
    store_chunks(document_id, chunks, embeddings)

    return UploadResponse(document_id=document_id, chunks_created=len(chunks))
