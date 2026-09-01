"""
Lightweight conversation memory: keeps recent Q&A pairs per
session, and uses them to build a better search query for
follow-up questions before retrieval.

Example:
  History: "What's the refund policy?" -> "30 days for physical goods."
  Follow-up: "What about digital products?"
  Search query: "What's the refund policy? What about digital products?"

Start simple: an in-memory dict of session_id -> list of turns.
This resets when the server restarts, which is fine for v1.

Note: this used to call Gemini to rewrite the follow-up into a
standalone question. That cost a full extra LLM call per turn,
which matters a lot on Gemini's free tier (very low daily request
quota). Concatenating the previous question is a free heuristic
that's good enough to steer retrieval - the final answer prompt
in routes/chat.py still gets the real conversation history, so
Gemini itself resolves the reference precisely when generating
the answer.
"""

session_history: dict[str, list[dict]] = {}


def get_history(session_id: str) -> list[dict]:
    return session_history.get(session_id, [])


def add_turn(session_id: str, question: str, answer: str):
    session_history.setdefault(session_id, []).append(
        {"question": question, "answer": answer}
    )


def build_search_query(session_id: str, question: str) -> str:
    history = get_history(session_id)
    if not history:
        return question
    return f"{history[-1]['question']} {question}"
