from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.routes import auth, chat, documents, upload
from app.services.embeddings import EmbeddingRateLimited

app = FastAPI(title="Askive", description="Chat with your documents")


@app.exception_handler(EmbeddingRateLimited)
async def embedding_rate_limited(request: Request, exc: EmbeddingRateLimited):
    return JSONResponse(
        status_code=429,
        headers={"Retry-After": "60"},
        content={
            "detail": (
                "Voyage AI's rate limit was hit (the free tier without a payment method "
                "allows about 10,000 tokens and 3 requests per minute). Wait a minute and "
                "try again, or try a smaller file."
            )
        },
    )

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(upload.router, prefix="/upload", tags=["upload"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])


@app.get("/health")
async def health():
    return {"status": "ok"}


app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
