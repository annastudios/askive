"""
User accounts and the documents each user has uploaded.
"""

import sqlite3
import uuid

import bcrypt

from app.db import connect


class UsernameTaken(Exception):
    pass


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_user(username: str, password: str) -> dict:
    user = {"id": str(uuid.uuid4()), "username": username}
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO users (id, username, password_hash) VALUES (?, ?, ?)",
                (user["id"], username, hash_password(password)),
            )
    except sqlite3.IntegrityError as e:
        raise UsernameTaken(username) from e
    return user


def get_user(user_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def authenticate(username: str, password: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
    if row is None or not verify_password(password, row["password_hash"]):
        return None
    return {"id": row["id"], "username": row["username"]}


def add_document(user_id: str, document_id: str, filename: str, chunks: int):
    with connect() as conn:
        conn.execute(
            "INSERT INTO documents (id, user_id, filename, chunks) VALUES (?, ?, ?, ?)",
            (document_id, user_id, filename, chunks),
        )


def list_documents(user_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, filename, chunks, created_at FROM documents "
            "WHERE user_id = ? ORDER BY created_at, rowid",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]
