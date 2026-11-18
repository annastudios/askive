"""
The original stateless chat endpoint: the browser sends a session id and the
conversation memory lives in Redis. Kept for compatibility (and the load
test); the React app uses the /chats routes, which store conversations in
the database.
"""

from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.models.schemas import ChatRequest, ChatResponse
from app.services import memory, qa

router = APIRouter()


@router.post("/", response_model=ChatResponse)
def ask_question(request: ChatRequest, user: dict = Depends(get_current_user)):
    # Namespaced so one user can't read another's conversation by guessing a session id.
    session_key = f"{user['id']}:{request.session_id}"
    result = qa.answer(user["id"], request.question, request.document_ids, memory.get_history(session_key))
    memory.add_turn(session_key, request.question, result["answer"])
    # This older endpoint has always returned plain passage texts.
    return ChatResponse(answer=result["answer"], sources=[s["text"] for s in result["sources"]], cached=result["cached"])
