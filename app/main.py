import os
from contextlib import asynccontextmanager

import anyio.to_thread
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import FRONTEND_DIST, THREAD_POOL_SIZE
from app.routes import auth, chat, chats, documents, health, upload
from app.services.embeddings import EmbeddingRateLimited


def configure_thread_pool():
    """Sets how many plain `def` route calls can run at once (default 40).
    Must run inside the event loop, hence at startup."""
    anyio.to_thread.current_default_thread_limiter().total_tokens = THREAD_POOL_SIZE


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_thread_pool()
    yield


app = FastAPI(title="Askive", description="Chat with your documents", lifespan=lifespan)


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
app.include_router(chats.router, prefix="/chats", tags=["chats"])
app.include_router(health.router, prefix="/health", tags=["health"])


class FrontendFiles(StaticFiles):
    """Serves the built React app (frontend/dist).

    Caching: Vite puts a content hash in every file under assets/
    (index-DTJd0T_V.js), so those can be cached forever - a new build gets new
    names. index.html is re-checked on every visit (a tiny 304 when unchanged),
    so users never keep running old code after a deploy.

    Routing: the app has its own addresses (/c/<chat id>). Refreshing one asks
    the server for a file that doesn't exist, so any path that doesn't look
    like a file gets index.html, and React shows the right page."""

    async def get_response(self, path, scope):
        path = path.replace("\\", "/")  # Starlette uses the OS separator; Windows gives "assets\\x.js"
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as e:
            looks_like_file = "." in path.rsplit("/", 1)[-1]
            if e.status_code != 404 or looks_like_file:
                raise
            response = await super().get_response("index.html", scope)
        if path.startswith("assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "no-cache"
        return response


if os.path.isdir(FRONTEND_DIST):
    app.mount("/", FrontendFiles(directory=FRONTEND_DIST, html=True), name="frontend")
else:
    @app.get("/", include_in_schema=False)
    def frontend_not_built():
        return HTMLResponse(
            "<p>The React frontend isn't built. Run <code>npm run build</code> in "
            "<code>frontend/</code>, or use the Vite dev server (<code>npm run dev</code>).</p>"
        )
