"""
Shared test setup. The real app talks to Voyage (embeddings) and
Gemini (answers); tests swap both for fakes so they run offline,
for free, and give the same result every time.
"""

import hashlib
import math
import os
import tempfile
from types import SimpleNamespace

# Must be set before anything under app/ is imported: config.py reads
# these at import time and retrieval.py opens ChromaDB at import time.
os.environ["GEMINI_API_KEY"] = "test-key"
os.environ["VOYAGE_API_KEY"] = "test-key"
os.environ["CHROMA_DB_PATH"] = tempfile.mkdtemp(prefix="askive-test-chroma-")

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routes import chat
from app.services import embeddings, memory

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
    def embed(self, texts, model=None, input_type=None):
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
    monkeypatch.setattr(embeddings, "client", FakeVoyageClient())


@pytest.fixture
def fake_gemini(monkeypatch):
    interactions = FakeInteractions()
    monkeypatch.setattr(chat, "gemini_client", SimpleNamespace(interactions=interactions))
    return interactions


@pytest.fixture(autouse=True)
def clear_memory():
    memory.session_history.clear()


@pytest.fixture
def client():
    return TestClient(app)
