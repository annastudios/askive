from fastapi import APIRouter, Depends, UploadFile

from app.auth import get_current_user
from app.models.schemas import UploadResponse
from app.services.ingest import ingest

router = APIRouter()


@router.post("/", response_model=UploadResponse)
def upload_document(file: UploadFile, user: dict = Depends(get_current_user)):
    document = ingest(user["id"], file.filename, file.file.read(), file.content_type)
    return UploadResponse(document_id=document["id"], chunks_created=document["chunks"])
