from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.models.schemas import DocumentInfo
from app.services import users

router = APIRouter()


@router.get("/", response_model=list[DocumentInfo])
def list_documents(user: dict = Depends(get_current_user)):
    return users.list_documents(user["id"])
