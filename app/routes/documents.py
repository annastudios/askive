from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response

from app.auth import get_current_user
from app.models.schemas import DocumentInfo
from app.services import users
from app.services.ingest import extract_text

router = APIRouter()

NO_PREVIEW = HTTPException(
    status_code=404,
    detail="No preview for this document. Documents uploaded before previews existed need to be uploaded again.",
)

# Only these are shown in the browser. Anything else (an uploaded .html file,
# say) is served as a download, so it can never run as a page on this site.
INLINE_TYPES = {
    "application/pdf",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.get("/", response_model=list[DocumentInfo])
def list_documents(user: dict = Depends(get_current_user)):
    return users.list_documents(user["id"])


@router.get("/{document_id}/file")
def get_file(document_id: str, user: dict = Depends(get_current_user)):
    """The original uploaded file, for previews."""
    file = users.get_document_file(user["id"], document_id)
    if file is None:
        raise NO_PREVIEW
    inline = file["content_type"] in INLINE_TYPES
    media_type = file["content_type"] if inline else "application/octet-stream"
    if media_type == "text/plain":
        media_type = "text/plain; charset=utf-8"
    disposition = "inline" if inline else "attachment"
    return Response(
        content=file["data"],
        media_type=media_type,
        headers={
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(file['filename'])}",
            "X-Content-Type-Options": "nosniff",  # never let the browser guess a riskier type
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.get("/{document_id}/text")
def get_text(document_id: str, user: dict = Depends(get_current_user)):
    """The document's text, for previewing Word and text files and for
    highlighting a cited passage."""
    file = users.get_document_file(user["id"], document_id)
    if file is None:
        raise NO_PREVIEW
    return {"filename": file["filename"], "text": extract_text(file["filename"], file["data"])}
