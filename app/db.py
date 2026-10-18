"""
SQLite storage for users and their document list. Chunks and
embeddings stay in ChromaDB; this only tracks who owns what.

Each call opens its own short-lived connection, which keeps it safe
to use from FastAPI's worker threads without any locking.
"""

import os
import sqlite3
from contextlib import contextmanager

from app.config import DATABASE_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id),
    filename   TEXT NOT NULL,
    chunks     INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS documents_user_id ON documents(user_id);
"""


@contextmanager
def connect():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db():
    os.makedirs(os.path.dirname(os.path.abspath(DATABASE_PATH)), exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)


init_db()
