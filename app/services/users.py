"""
User accounts and the documents each user has uploaded.
"""

import uuid

import bcrypt
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from app.db import connect, documents, users


class EmailTaken(Exception):
    pass


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_user(email: str, password: str) -> dict:
    user = {"id": str(uuid.uuid4()), "email": normalize_email(email)}
    try:
        with connect() as conn:
            conn.execute(insert(users).values(password_hash=hash_password(password), **user))
    except IntegrityError as e:
        raise EmailTaken(email) from e
    return user


def get_user(user_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(select(users.c.id, users.c.email).where(users.c.id == user_id)).mappings().first()
    return dict(row) if row else None


def authenticate(email: str, password: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            select(users.c.id, users.c.email, users.c.password_hash).where(
                users.c.email == normalize_email(email)
            )
        ).mappings().first()
    if row is None or not verify_password(password, row["password_hash"]):
        return None
    return {"id": row["id"], "email": row["email"]}


def add_document(user_id: str, document_id: str, filename: str, chunks: int):
    with connect() as conn:
        conn.execute(
            insert(documents).values(id=document_id, user_id=user_id, filename=filename, chunks=chunks)
        )


def list_documents(user_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            select(documents.c.id, documents.c.filename, documents.c.chunks, documents.c.created_at)
            .where(documents.c.user_id == user_id)
            .order_by(documents.c.created_at, documents.c.id)
        ).mappings().all()
    return [dict(r) for r in rows]
