"""
Stand-ins for Voyage and Gemini, used ONLY for load testing (FAKE_AI=1).

A load test with real AI calls would burn through API quota in minutes
and mostly measure Google's and Voyage's speed rather than ours. These
fakes keep the test realistic by waiting as long as the real services
do (measured: ~0.15s per Voyage request, ~4.5s per Gemini answer), so
everything around them - threads, ChromaDB, Redis, Postgres, Kubernetes -
sees the same load it would in real use. Answers are placeholder text.
"""

import hashlib
import math
import os
import time
from types import SimpleNamespace

EMBED_SECONDS = float(os.getenv("FAKE_EMBED_SECONDS", "0.15"))
LLM_SECONDS = float(os.getenv("FAKE_LLM_SECONDS", "4.5"))

# Same size as voyage-3 vectors, so fake and real chunks can share a ChromaDB collection.
DIMENSIONS = 1024


def _vector(text: str) -> list[float]:
    vector = [0.0] * DIMENSIONS
    for word in text.lower().split():
        bucket = int(hashlib.md5(word.strip(".,!?;:").encode()).hexdigest(), 16) % DIMENSIONS
        vector[bucket] += 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


class FakeVoyageClient:
    def embed(self, texts, model=None, input_type=None):
        time.sleep(EMBED_SECONDS)
        return SimpleNamespace(embeddings=[_vector(t) for t in texts])


class _FakeInteractions:
    def create(self, model, input):
        time.sleep(LLM_SECONDS)
        return SimpleNamespace(output_text="(Load-test placeholder answer: FAKE_AI is on.)")


class FakeGeminiClient:
    def __init__(self):
        self.interactions = _FakeInteractions()
