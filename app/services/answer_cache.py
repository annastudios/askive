"""
Caches final answers so a repeated question skips retrieval and the
Gemini call entirely.

A cached answer is only reused when everything that shaped it is the
same: the user, the question (ignoring case, spacing and trailing
punctuation), which documents were selected, the recent conversation
that went into the prompt, and the user's set of documents. That last
one is tracked as a per-user version number bumped on every upload,
so new documents never get answered from a stale cache.
"""

import hashlib
import json
import re

from app.config import CACHE_TTL_SECONDS
from app.services import cache


def normalize_question(question: str) -> str:
    return re.sub(r"\s+", " ", question).strip().rstrip("?!. ").lower()


def _docs_version(user_id: str) -> str:
    return cache.store.get(f"docs_version:{user_id}") or "0"


def documents_changed(user_id: str):
    cache.store.incr(f"docs_version:{user_id}")


def _key(user_id: str, question: str, document_ids: list[str], transcript: str) -> str:
    fingerprint = json.dumps(
        [normalize_question(question), sorted(document_ids), transcript], ensure_ascii=False
    )
    digest = hashlib.sha256(fingerprint.encode()).hexdigest()
    return f"answer:{user_id}:{_docs_version(user_id)}:{digest}"


def get(user_id: str, question: str, document_ids: list[str], transcript: str) -> dict | None:
    cached = cache.store.get(_key(user_id, question, document_ids, transcript))
    return json.loads(cached) if cached else None


def put(user_id: str, question: str, document_ids: list[str], transcript: str, answer: str, sources: list[str]):
    cache.store.set(
        _key(user_id, question, document_ids, transcript),
        json.dumps({"answer": answer, "sources": sources}),
        ex=CACHE_TTL_SECONDS,
    )
