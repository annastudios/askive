"""
Relational storage for users and their document list. Chunks and
embeddings stay in ChromaDB; this only tracks who owns what.

Written with SQLAlchemy so the same code runs on two databases:
- Postgres when DATABASE_URL is set (docker-compose, Kubernetes): a
  server every API replica connects to over the network.
- SQLite otherwise (local dev, tests): a single file, no server needed.

Tables are created on first use. That's enough while the schema is new;
once it starts changing, a migration tool such as Alembic should take over.
"""

import os
import threading
from contextlib import contextmanager

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    func,
)

from app.config import DATABASE_URL

metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("id", String(36), primary_key=True),
    # Always stored lower-cased, so uniqueness is case-insensitive.
    Column("email", String(254), nullable=False, unique=True),
    Column("password_hash", String(100), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

documents = Table(
    "documents",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("user_id", String(36), ForeignKey("users.id"), nullable=False, index=True),
    Column("filename", String(255), nullable=False),
    Column("chunks", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)


def _make_engine():
    if DATABASE_URL.startswith("sqlite"):
        path = DATABASE_URL.removeprefix("sqlite:///")
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        return create_engine(DATABASE_URL)
    # pool_pre_ping: check a pooled connection still works before using it,
    # so a Postgres restart doesn't surface as errors on the next requests.
    return create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=5)


engine = _make_engine()

_schema_ready = False
_schema_lock = threading.Lock()


def _ensure_schema():
    """Creates missing tables on first use rather than at import, so the API
    can start before Postgres is reachable."""
    global _schema_ready
    if not _schema_ready:
        with _schema_lock:
            if not _schema_ready:
                metadata.create_all(engine)
                _schema_ready = True


@contextmanager
def connect():
    """A connection inside a transaction: committed on success, rolled back on error."""
    _ensure_schema()
    with engine.begin() as conn:
        yield conn
