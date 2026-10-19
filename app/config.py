import os
import secrets
import warnings

from dotenv import load_dotenv
from google import genai

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "voyage-3")
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
CHROMA_HOST = os.getenv("CHROMA_HOST")  # set to use a ChromaDB server instead of CHROMA_DB_PATH
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
GEMINI_MODEL = "gemini-3.5-flash-lite"

# Postgres in deployments, e.g. postgresql+psycopg://askive:secret@postgres:5432/askive.
# Unset means a local SQLite file at DATABASE_PATH (dev and tests).
DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/askive.db")
DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{DATABASE_PATH}"
# Unset means an in-process cache: fine for one local server, but not shared between replicas.
REDIS_URL = os.getenv("REDIS_URL")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

if not JWT_SECRET:
    # Fine for local dev, but every restart logs everyone out and multiple
    # replicas would reject each other's tokens - always set it in deployments.
    warnings.warn("JWT_SECRET is not set; using a random one for this process.")
    JWT_SECRET = secrets.token_urlsafe(32)

# Worker threads for FastAPI's plain `def` routes. Each question holds one for
# the whole ~4.5s Gemini call, mostly just waiting, so the default of 40 capped
# a pod at ~40 questions in flight (found by the load test). Waiting threads
# are cheap; making the AI calls fully async would remove the limit entirely.
THREAD_POOL_SIZE = int(os.getenv("THREAD_POOL_SIZE", "100"))

# Load testing only: replaces Voyage and Gemini with timed stand-ins (see fake_ai.py).
FAKE_AI = os.getenv("FAKE_AI") == "1"

if FAKE_AI:
    from app.services.fake_ai import FakeGeminiClient

    warnings.warn("FAKE_AI=1: Voyage and Gemini are replaced with fakes. Never use this for real users.")
    gemini_client = FakeGeminiClient()
else:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
