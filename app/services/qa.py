"""
Answers one question from a set of documents: answer cache -> hybrid search
-> Gemini. Shared by the original /chat route (memory in Redis) and the
/chats routes (conversations stored in the database), which differ only in
where the conversation history comes from.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass

from fastapi import HTTPException
# Private import: google-genai's public `google.genai.errors` classes don't
# cover the Interactions API - it raises this internal exception type instead.
from google.genai._gaos.lib.compat_errors import APIStatusError

from app.config import gemini_client, GEMINI_MODEL
from app.services import answer_cache
from app.services.embeddings import embed_text
from app.services.retrieval import search

# How many previous question/answer pairs go into the prompt.
HISTORY_TURNS = 3


def transcript_of(history: list[dict]) -> str:
    """history: [{"question": ..., "answer": ...}], oldest first."""
    return "\n".join(f"Q: {t['question']}\nA: {t['answer']}" for t in history[-HISTORY_TURNS:])


def normalize_sources(sources: list) -> list[dict]:
    """Sources are {"document_id", "text"}. Answers saved (or cached) before
    passages carried their document were plain strings; read those too."""
    return [s if isinstance(s, dict) else {"document_id": None, "text": s} for s in sources]


def build_prompt(question: str, chunks: list, transcript: str) -> str:
    # Passages are numbered in the same order as the `sources` returned with the
    # answer, so a citation like [2] points at sources[1] in the UI.
    texts = [c["text"] if isinstance(c, dict) else c for c in chunks]
    passages = "\n\n".join(f"[{i}] {text}" for i, text in enumerate(texts, start=1))
    history_block = f"Recent conversation:\n{transcript}\n\n" if transcript else ""
    return (
        "Answer the question using only the numbered passages below. After each "
        "statement, cite the passage it came from in square brackets, like [2]. "
        "If the passages don't contain the answer, say you don't know. Use the "
        "recent conversation, if any, to understand what the question refers to.\n\n"
        f"{history_block}"
        f"Passages:\n{passages}\n\n"
        f"Question: {question}"
    )


def gemini_unavailable(e: APIStatusError) -> HTTPException | None:
    if e.status_code == 429:
        return HTTPException(
            status_code=503,
            detail="Gemini's free-tier quota is exhausted for now. Wait a bit and try again.",
        )
    return None


def _prepare(user_id: str, question: str, document_ids: list[str], history: list[dict]):
    """Everything before the language model: validation, cache lookup, search.
    Returns (transcript, cached answer or None, retrieved chunks)."""
    # Each chat searches only the documents attached to it. An empty list used to
    # mean "search everything this user ever uploaded", which mixed unrelated
    # documents into answers - now it's an error instead.
    if not document_ids:
        raise HTTPException(status_code=400, detail="This chat has no documents yet. Upload a document first.")

    transcript = transcript_of(history)
    cached = answer_cache.get(user_id, question, document_ids, transcript)
    if cached:
        cached = {**cached, "sources": normalize_sources(cached["sources"])}
        return transcript, cached, cached["sources"]

    # A follow-up like "what about digital products?" is searched together with
    # the previous question, so retrieval knows what it refers to.
    search_query = f"{history[-1]['question']} {question}" if history else question
    query_embedding = embed_text(search_query, input_type="query")
    chunks = search(search_query, query_embedding, user_id=user_id, document_ids=document_ids)
    return transcript, None, chunks


def _ask_gemini(prompt: str, stream: bool = False):
    try:
        return gemini_client.interactions.create(model=GEMINI_MODEL, input=prompt, stream=stream)
    except APIStatusError as e:
        if (error := gemini_unavailable(e)) is not None:
            raise error from e
        raise


def answer(user_id: str, question: str, document_ids: list[str], history: list[dict]) -> dict:
    """Returns {"answer", "sources", "cached"}. Raises HTTPException(400) when
    there are no documents to search."""
    transcript, cached, chunks = _prepare(user_id, question, document_ids, history)
    if cached:
        return {"answer": cached["answer"], "sources": cached["sources"], "cached": True}

    text = _ask_gemini(build_prompt(question, chunks, transcript)).output_text.strip()
    answer_cache.put(user_id, question, document_ids, transcript, text, chunks)
    return {"answer": text, "sources": chunks, "cached": False}


class StreamFailed(Exception):
    """The answer couldn't be finished once streaming had started. The message
    is safe to show to the user."""


@dataclass
class AnswerStream:
    sources: list[dict]           # [{"document_id", "text"}]
    pieces: Iterator[str]          # the answer, piece by piece as it is written
    cached: bool
    _on_complete: Callable[[str], None] | None = None

    def complete(self, full_text: str):
        """Call once the whole answer has been streamed, so it gets cached."""
        if self._on_complete:
            self._on_complete(full_text)


def start_answer_stream(user_id: str, question: str, document_ids: list[str], history: list[dict]) -> AnswerStream:
    """Like answer(), but the text arrives piece by piece. Validation, the cache
    and the search happen here (so "no documents" is still a clean HTTP 400);
    Gemini is only called once the caller starts reading `pieces`.

    Why start Gemini late: the model thinks for ~4 s before its first word
    (measured), so the sources can reach the user well before the answer
    does. The cost is that a quota error now arrives inside the stream, as
    StreamFailed, rather than as an HTTP 503 before it."""
    transcript, cached, chunks = _prepare(user_id, question, document_ids, history)
    if cached:
        return AnswerStream(sources=cached["sources"], pieces=iter([cached["answer"]]), cached=True)

    prompt = build_prompt(question, chunks, transcript)

    def pieces() -> Iterator[str]:
        try:
            events = _ask_gemini(prompt, stream=True)
        except HTTPException as e:
            raise StreamFailed(e.detail) from e
        try:
            for event in events:
                kind = getattr(event, "event_type", None)
                if kind == "step.delta" and getattr(event.delta, "type", None) == "text":
                    yield event.delta.text
                elif kind == "error":
                    raise StreamFailed("The answer was interrupted. Please try again.")
                elif kind == "interaction.completed":
                    # The answer is complete. Gemini keeps the connection open for
                    # ~2 s more before closing it (measured), so stop reading now.
                    break
        finally:
            if hasattr(events, "close"):
                events.close()

    def cache_it(full_text: str):
        answer_cache.put(user_id, question, document_ids, transcript, full_text.strip(), chunks)

    return AnswerStream(sources=chunks, pieces=pieces(), cached=False, _on_complete=cache_it)
