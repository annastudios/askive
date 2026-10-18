"""
Shared test setup. The real app talks to Voyage (embeddings) and
Gemini (answers); tests swap both for fakes so they run offline,
for free, and give the same result every time.
"""

import hashlib
import math
import os
import tempfile
import uuid
from types import SimpleNamespace

# Must be set before anything under app/ is imported: config.py reads
# these at import time and retrieval.py opens ChromaDB at import time.
os.environ["GEMINI_API_KEY"] = "test-key"
os.environ["VOYAGE_API_KEY"] = "test-key"
_tmp = tempfile.mkdtemp(prefix="askive-test-")
os.environ["CHROMA_DB_PATH"] = os.path.join(_tmp, "chroma")
os.environ["DATABASE_PATH"] = os.path.join(_tmp, "askive.db")
TEST_JWT_SECRET = "test-secret-that-is-at-least-32-bytes-long"
os.environ["JWT_SECRET"] = TEST_JWT_SECRET

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routes import chat
from app.services import cache, embeddings

DIMENSIONS = 64


def fake_embedding(text: str) -> list[float]:
    """Bag-of-words hashed into a fixed-size vector, so texts that share
    words get similar vectors - enough to exercise chunking and search."""
    vector = [0.0] * DIMENSIONS
    for word in text.lower().split():
        word = word.strip(".,!?;:")
        bucket = int(hashlib.md5(word.encode()).hexdigest(), 16) % DIMENSIONS
        vector[bucket] += 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


class FakeVoyageClient:
    def __init__(self):
        self.error: Exception | None = None
        self.calls: list[list[str]] = []

    def embed(self, texts, model=None, input_type=None):
        if self.error:
            raise self.error
        self.calls.append(list(texts))
        return SimpleNamespace(embeddings=[fake_embedding(t) for t in texts])


class FakeInteractions:
    def __init__(self):
        self.prompts: list[str] = []
        self.error: Exception | None = None

    def create(self, model, input):
        if self.error:
            raise self.error
        self.prompts.append(input)
        return SimpleNamespace(output_text=" Fake answer. ")


@pytest.fixture(autouse=True)
def fake_voyage(monkeypatch):
    voyage = FakeVoyageClient()
    monkeypatch.setattr(embeddings, "client", voyage)
    return voyage


@pytest.fixture
def fake_gemini(monkeypatch):
    interactions = FakeInteractions()
    monkeypatch.setattr(chat, "gemini_client", SimpleNamespace(interactions=interactions))
    return interactions


@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch):
    """Each test starts with an empty cache and chat memory."""
    store = cache.InMemoryStore()
    monkeypatch.setattr(cache, "store", store)
    return store


def sign_up(client: TestClient, username: str | None = None, password: str = "correct-horse") -> dict:
    """Registers a fresh user, logs in, and puts the token on the client.
    Returns the user."""
    username = username or f"user_{uuid.uuid4().hex[:8]}"
    user = client.post("/auth/register", json={"username": username, "password": password}).json()
    token = client.post("/auth/login", data={"username": username, "password": password}).json()
    client.headers["Authorization"] = f"Bearer {token['access_token']}"
    return user


@pytest.fixture
def anon_client():
    return TestClient(app)


@pytest.fixture
def client():
    """A client already signed in as a brand-new user."""
    c = TestClient(app)
    sign_up(c)
    return c
