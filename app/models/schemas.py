from pydantic import BaseModel


class ChatRequest(BaseModel):
    question: str
    session_id: str
    document_ids: list[str] = []


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = []


class UploadResponse(BaseModel):
    document_id: str
    chunks_created: int
