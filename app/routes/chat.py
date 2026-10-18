from fastapi import APIRouter, Depends, HTTPException
# Private import: google-genai's public `google.genai.errors` classes don't
# cover the Interactions API - it raises this internal exception type instead.
from google.genai._gaos.lib.compat_errors import APIStatusError

from app.auth import get_current_user
from app.config import gemini_client, GEMINI_MODEL
from app.models.schemas import ChatRequest, ChatResponse
from app.services import answer_cache, memory
from app.services.embeddings import embed_text
from app.services.retrieval import search

router = APIRouter()


@router.post("/", response_model=ChatResponse)
def ask_question(request: ChatRequest, user: dict = Depends(get_current_user)):
    # Each chat searches only the documents attached to it. An empty list used to
    # mean "search everything this user ever uploaded", which mixed unrelated
    # documents into answers - now it's an error instead.
    if not request.document_ids:
        raise HTTPException(status_code=400, detail="This chat has no documents yet. Upload a document first.")

    # Namespaced so one user can't read another's conversation by guessing a session id.
    session_key = f"{user['id']}:{request.session_id}"
    history = memory.get_history(session_key)
    transcript = "\n".join(f"Q: {t['question']}\nA: {t['answer']}" for t in history[-3:])

    cached = answer_cache.get(user["id"], request.question, request.document_ids, transcript)
    if cached:
        memory.add_turn(session_key, request.question, cached["answer"])
        return ChatResponse(answer=cached["answer"], sources=cached["sources"], cached=True)

    search_query = memory.build_search_query(session_key, request.question)
    query_embedding = embed_text(search_query, input_type="query")
    chunks = search(search_query, query_embedding, user_id=user["id"], document_ids=request.document_ids)

    context = "\n\n".join(chunks)
    history_block = f"Recent conversation:\n{transcript}\n\n" if transcript else ""

    prompt = (
        "Answer the question using only the context below. If the context "
        "doesn't contain the answer, say you don't know. Use the recent "
        "conversation, if any, to understand what the question refers to.\n\n"
        f"{history_block}"
        f"Context:\n{context}\n\n"
        f"Question: {request.question}"
    )

    try:
        interaction = gemini_client.interactions.create(model=GEMINI_MODEL, input=prompt)
    except APIStatusError as e:
        if e.status_code == 429:
            raise HTTPException(
                status_code=503,
                detail="Gemini's free-tier quota is exhausted for now. Wait a bit and try again.",
            ) from e
        raise

    answer = interaction.output_text.strip()

    memory.add_turn(session_key, request.question, answer)
    answer_cache.put(user["id"], request.question, request.document_ids, transcript, answer, chunks)

    return ChatResponse(answer=answer, sources=chunks)
