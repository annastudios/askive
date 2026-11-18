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
# A stand-in for the built React app, so tests don't need `npm run build`.
_dist = os.path.join(_tmp, "dist")
os.makedirs(os.path.join(_dist, "assets"))
with open(os.path.join(_dist, "index.html"), "w") as f:
    f.write("<!doctype html><div id=root></div>")
with open(os.path.join(_dist, "assets", "index-abc123.js"), "w") as f:
    f.write("console.log('app')")
os.environ["FRONTEND_DIST"] = _dist
# Tests use that SQLite file unless DATABASE_URL points at a Postgres
# (CI runs the suite against both).
TEST_JWT_SECRET = "test-secret-that-is-at-least-32-bytes-long"
os.environ["JWT_SECRET"] = TEST_JWT_SECRET

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import cache, embeddings, qa

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


FAKE_ANSWER = " Fake answer. "


def text_event(text: str):
    """Shaped like Gemini's streaming events (event_type "step.delta", delta.text)."""
    return SimpleNamespace(event_type="step.delta", delta=SimpleNamespace(type="text", text=text))


class FakeInteractions:
    def __init__(self):
        self.prompts: list[str] = []
        self.error: Exception | None = None           # raised when the request is made
        self.stream_error: str | None = None          # sent as an error event mid-stream

    def create(self, model, input, stream=False):
        if self.error:
            raise self.error
        self.prompts.append(input)
        if not stream:
            return SimpleNamespace(output_text=FAKE_ANSWER)
        return self._events()

    def _events(self):
        yield SimpleNamespace(event_type="interaction.created")
        yield text_event(" Fake ")
        if self.stream_error:
            yield SimpleNamespace(event_type="error", error=self.stream_error)
            return
        yield text_event("answer. ")
        yield SimpleNamespace(event_type="interaction.completed")
        # Real Gemini keeps the connection open for ~2 s after "completed";
        # the app must stop reading at "completed", so reading on is a bug.
        raise AssertionError("read past interaction.completed")


@pytest.fixture(autouse=True)
def fake_voyage(monkeypatch):
    voyage = FakeVoyageClient()
    monkeypatch.setattr(embeddings, "client", voyage)
    return voyage


@pytest.fixture
def fake_gemini(monkeypatch):
    interactions = FakeInteractions()
    monkeypatch.setattr(qa, "gemini_client", SimpleNamespace(interactions=interactions))
    return interactions


@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch):
    """Each test starts with an empty cache and chat memory."""
    store = cache.InMemoryStore()
    monkeypatch.setattr(cache, "store", store)
    return store


def unique_email(prefix: str = "user") -> str:
    """Unique per call, so tests never collide - even against a shared Postgres."""
    return f"{prefix}.{uuid.uuid4().hex[:10]}@example.com".lower()


def sign_up(client: TestClient, email: str | None = None, password: str = "correct-horse") -> dict:
    """Registers a fresh user, logs in, and puts the token on the client.
    Returns the user."""
    email = email or unique_email()
    user = client.post("/auth/register", json={"email": email, "password": password}).json()
    token = client.post("/auth/login", data={"username": email, "password": password}).json()
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
