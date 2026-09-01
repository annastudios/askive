from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes import upload, chat

app = FastAPI(title="Askive", description="Chat with your documents")

app.include_router(upload.router, prefix="/upload", tags=["upload"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])


@app.get("/health")
async def health():
    return {"status": "ok"}


app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
