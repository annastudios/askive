from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    question: str
    session_id: str
    document_ids: list[str] = []


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = []
    cached: bool = False


class UploadResponse(BaseModel):
    document_id: str
    chunks_created: int


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def fits_bcrypt(cls, password: str) -> str:
        # bcrypt only looks at the first 72 bytes and rejects longer input.
        if len(password.encode()) > 72:
            raise ValueError("password must be at most 72 bytes")
        return password


class User(BaseModel):
    id: str
    username: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DocumentInfo(BaseModel):
    id: str
    filename: str
    chunks: int
    created_at: str
