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
GEMINI_MODEL = "gemini-3.5-flash-lite"

DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/askive.db")
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

if not JWT_SECRET:
    # Fine for local dev, but every restart logs everyone out and multiple
    # replicas would reject each other's tokens - always set it in deployments.
    warnings.warn("JWT_SECRET is not set; using a random one for this process.")
    JWT_SECRET = secrets.token_urlsafe(32)

gemini_client = genai.Client(api_key=GEMINI_API_KEY)
