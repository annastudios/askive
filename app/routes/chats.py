"""
Conversations stored on the server, so they follow the user across devices.

A chat that doesn't exist and a chat that belongs to someone else both return
404, so nobody can probe which chat ids exist.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status

from app.auth import get_current_user
from app.models.schemas import AskRequest, AskResponse, ChatCreate, ChatDetail, ChatDocument, ChatRename, ChatSummary
from app.services import chats, qa
from app.services.ingest import ingest

router = APIRouter()

NOT_FOUND = HTTPException(status_code=404, detail="Chat not found.")


@router.get("", response_model=list[ChatSummary])
def list_chats(user: dict = Depends(get_current_user)):
    return chats.list_chats(user["id"])


@router.post("", response_model=ChatSummary, status_code=status.HTTP_201_CREATED)
def create_chat(body: ChatCreate | None = None, user: dict = Depends(get_current_user)):
    return chats.create_chat(user["id"], body.title if body else None)


@router.get("/{chat_id}", response_model=ChatDetail)
def get_chat(chat_id: str, user: dict = Depends(get_current_user)):
    chat = chats.get_chat(user["id"], chat_id)
    if chat is None:
        raise NOT_FOUND
    return chat


@router.patch("/{chat_id}", response_model=ChatSummary)
def rename_chat(chat_id: str, body: ChatRename, user: dict = Depends(get_current_user)):
    chat = chats.rename_chat(user["id"], chat_id, body.title.strip())
    if chat is None:
        raise NOT_FOUND
    return chat


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat(chat_id: str, user: dict = Depends(get_current_user)):
    if not chats.delete_chat(user["id"], chat_id):
        raise NOT_FOUND
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{chat_id}/documents", response_model=ChatDocument, status_code=status.HTTP_201_CREATED)
def upload_to_chat(chat_id: str, file: UploadFile, user: dict = Depends(get_current_user)):
    # Check ownership before the (slow) upload work, not after.
    if chats.get_chat(user["id"], chat_id) is None:
        raise NOT_FOUND
    document = ingest(user["id"], file.filename, file.file.read())
    chats.attach_document(user["id"], chat_id, document["id"])
    return document


@router.post("/{chat_id}/messages", response_model=AskResponse)
def ask(chat_id: str, body: AskRequest, user: dict = Depends(get_current_user)):
    if chats.get_chat(user["id"], chat_id) is None:
        raise NOT_FOUND
    result = qa.answer(user["id"], body.question, chats.document_ids(chat_id), chats.recent_turns(chat_id, qa.HISTORY_TURNS))
    message = chats.add_exchange(chat_id, body.question, result["answer"], result["sources"])
    return AskResponse(message=message, cached=result["cached"])
