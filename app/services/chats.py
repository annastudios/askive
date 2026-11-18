"""
Conversations stored in the database: each chat has an owner, a title, the
documents attached to it, and its messages in order. Every lookup is scoped
to the owner, so one user can never read or change another user's chat.
"""

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, insert, select, update

from app.db import chat_documents, chats, connect, documents, messages

DEFAULT_TITLE = "New chat"
TITLE_LENGTH = 60


def _now() -> datetime:
    # Set from Python rather than the database clock: SQLite's CURRENT_TIMESTAMP
    # only has 1-second precision, so "most recent activity first" would tie.
    return datetime.now(timezone.utc)


def _summary(row) -> dict:
    return {"id": row.id, "title": row.title, "created_at": row.created_at, "updated_at": row.updated_at}


def create_chat(user_id: str, title: str | None = None) -> dict:
    chat_id = str(uuid.uuid4())
    with connect() as conn:
        now = _now()
        conn.execute(insert(chats).values(id=chat_id, user_id=user_id, title=title or DEFAULT_TITLE, created_at=now, updated_at=now))
        row = conn.execute(select(chats).where(chats.c.id == chat_id)).first()
    return _summary(row)


def list_chats(user_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            select(chats).where(chats.c.user_id == user_id).order_by(chats.c.updated_at.desc(), chats.c.created_at.desc())
        ).all()
    return [_summary(r) for r in rows]


def _owned(conn, user_id: str, chat_id: str):
    return conn.execute(select(chats).where(chats.c.id == chat_id, chats.c.user_id == user_id)).first()


def get_chat(user_id: str, chat_id: str) -> dict | None:
    """The chat with its documents and messages, or None if it doesn't exist
    or belongs to someone else."""
    with connect() as conn:
        row = _owned(conn, user_id, chat_id)
        if row is None:
            return None
        docs = conn.execute(
            select(documents.c.id, documents.c.filename, documents.c.chunks)
            .join(chat_documents, chat_documents.c.document_id == documents.c.id)
            .where(chat_documents.c.chat_id == chat_id)
            .order_by(documents.c.created_at, documents.c.id)
        ).mappings().all()
        msgs = conn.execute(
            select(messages).where(messages.c.chat_id == chat_id).order_by(messages.c.id)
        ).all()
    return {
        **_summary(row),
        "documents": [dict(d) for d in docs],
        "messages": [
            {"id": m.id, "role": m.role, "content": m.content, "sources": json.loads(m.sources), "created_at": m.created_at}
            for m in msgs
        ],
    }


def rename_chat(user_id: str, chat_id: str, title: str) -> dict | None:
    with connect() as conn:
        if _owned(conn, user_id, chat_id) is None:
            return None
        conn.execute(update(chats).where(chats.c.id == chat_id).values(title=title, updated_at=_now()))
        return _summary(_owned(conn, user_id, chat_id))


def delete_chat(user_id: str, chat_id: str) -> bool:
    """Deletes the chat and its messages. The documents stay in the user's
    library (and in /documents); only their link to this chat is removed."""
    with connect() as conn:
        if _owned(conn, user_id, chat_id) is None:
            return False
        # Explicit rather than relying on ON DELETE CASCADE, which SQLite
        # ignores unless foreign keys are switched on per connection.
        conn.execute(delete(messages).where(messages.c.chat_id == chat_id))
        conn.execute(delete(chat_documents).where(chat_documents.c.chat_id == chat_id))
        conn.execute(delete(chats).where(chats.c.id == chat_id))
    return True


def attach_document(user_id: str, chat_id: str, document_id: str) -> bool:
    with connect() as conn:
        if _owned(conn, user_id, chat_id) is None:
            return False
        conn.execute(insert(chat_documents).values(chat_id=chat_id, document_id=document_id))
        conn.execute(update(chats).where(chats.c.id == chat_id).values(updated_at=_now()))
    return True


def document_ids(chat_id: str) -> list[str]:
    with connect() as conn:
        rows = conn.execute(select(chat_documents.c.document_id).where(chat_documents.c.chat_id == chat_id)).all()
    return [r.document_id for r in rows]


def recent_turns(chat_id: str, limit: int = 3) -> list[dict]:
    """The last `limit` question/answer pairs, oldest first."""
    with connect() as conn:
        rows = conn.execute(
            select(messages.c.role, messages.c.content)
            .where(messages.c.chat_id == chat_id)
            .order_by(messages.c.id.desc())
            .limit(limit * 2)
        ).all()
    rows = list(reversed(rows))
    turns, question = [], None
    for row in rows:
        if row.role == "user":
            question = row.content
        elif question is not None:
            turns.append({"question": question, "answer": row.content})
            question = None
    return turns


def add_exchange(chat_id: str, question: str, answer: str, sources: list[str]) -> dict:
    """Stores a question and its answer, names an untitled chat after its first
    question, and returns the stored answer message."""
    with connect() as conn:
        conn.execute(insert(messages).values(chat_id=chat_id, role="user", content=question))
        result = conn.execute(
            insert(messages).values(chat_id=chat_id, role="assistant", content=answer, sources=json.dumps(sources))
        )
        message_id = result.inserted_primary_key[0]
        values = {"updated_at": _now()}
        title = conn.execute(select(chats.c.title).where(chats.c.id == chat_id)).scalar_one()
        if title == DEFAULT_TITLE:
            values["title"] = question.strip()[:TITLE_LENGTH] or DEFAULT_TITLE
        conn.execute(update(chats).where(chats.c.id == chat_id).values(**values))
        row = conn.execute(select(messages).where(messages.c.id == message_id)).first()
    return {"id": row.id, "role": row.role, "content": row.content, "sources": sources, "created_at": row.created_at}
