"""
Answers one question from a set of documents: answer cache -> hybrid search
-> Gemini. Shared by the original /chat route (memory in Redis) and the
/chats routes (conversations stored in the database), which differ only in
where the conversation history comes from.
"""

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


def build_prompt(question: str, chunks: list[str], transcript: str) -> str:
    context = "\n\n".join(chunks)
    history_block = f"Recent conversation:\n{transcript}\n\n" if transcript else ""
    return (
        "Answer the question using only the context below. If the context "
        "doesn't contain the answer, say you don't know. Use the recent "
        "conversation, if any, to understand what the question refers to.\n\n"
        f"{history_block}"
        f"Context:\n{context}\n\n"
        f"Question: {question}"
    )


def gemini_unavailable(e: APIStatusError) -> HTTPException | None:
    if e.status_code == 429:
        return HTTPException(
            status_code=503,
            detail="Gemini's free-tier quota is exhausted for now. Wait a bit and try again.",
        )
    return None


def answer(user_id: str, question: str, document_ids: list[str], history: list[dict]) -> dict:
    """Returns {"answer", "sources", "cached"}. Raises HTTPException(400) when
    there are no documents to search."""
    # Each chat searches only the documents attached to it. An empty list used to
    # mean "search everything this user ever uploaded", which mixed unrelated
    # documents into answers - now it's an error instead.
    if not document_ids:
        raise HTTPException(status_code=400, detail="This chat has no documents yet. Upload a document first.")

    transcript = transcript_of(history)
    cached = answer_cache.get(user_id, question, document_ids, transcript)
    if cached:
        return {"answer": cached["answer"], "sources": cached["sources"], "cached": True}

    # A follow-up like "what about digital products?" is searched together with
    # the previous question, so retrieval knows what it refers to.
    search_query = f"{history[-1]['question']} {question}" if history else question
    query_embedding = embed_text(search_query, input_type="query")
    chunks = search(search_query, query_embedding, user_id=user_id, document_ids=document_ids)

    try:
        interaction = gemini_client.interactions.create(
            model=GEMINI_MODEL, input=build_prompt(question, chunks, transcript)
        )
    except APIStatusError as e:
        if (error := gemini_unavailable(e)) is not None:
            raise error from e
        raise

    text = interaction.output_text.strip()
    answer_cache.put(user_id, question, document_ids, transcript, text, chunks)
    return {"answer": text, "sources": chunks, "cached": False}
