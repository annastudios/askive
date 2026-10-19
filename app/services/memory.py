"""
Lightweight conversation memory: keeps recent Q&A pairs per
session, and uses them to build a better search query for
follow-up questions before retrieval.

Example:
  History: "What's the refund policy?" -> "30 days for physical goods."
  Follow-up: "What about digital products?"
  Search query: "What's the refund policy? What about digital products?"

Turns are stored as a list in the cache store (see cache.py), so with
Redis they survive restarts and are shared by every API replica. Only
the most recent MAX_TURNS are kept, and an idle session expires after
SESSION_TTL_SECONDS.

Note: this used to call Gemini to rewrite the follow-up into a
standalone question. That cost a full extra LLM call per turn,
which matters a lot on Gemini's free tier (very low daily request
quota). Concatenating the previous question is a free heuristic
that's good enough to steer retrieval - the final answer prompt
in routes/chat.py still gets the real conversation history, so
Gemini itself resolves the reference precisely when generating
the answer.
"""

import json

from app.services import cache

MAX_TURNS = 10
SESSION_TTL_SECONDS = 7 * 24 * 3600


def _key(session_id: str) -> str:
    return f"memory:{session_id}"


def get_history(session_id: str) -> list[dict]:
    return [json.loads(turn) for turn in cache.store.lrange(_key(session_id), 0, -1)]


def add_turn(session_id: str, question: str, answer: str):
    key = _key(session_id)
    cache.store.rpush(key, json.dumps({"question": question, "answer": answer}))
    cache.store.ltrim(key, -MAX_TURNS, -1)
    cache.store.expire(key, SESSION_TTL_SECONDS)


def build_search_query(session_id: str, question: str) -> str:
    history = get_history(session_id)
    if not history:
        return question
    return f"{history[-1]['question']} {question}"
