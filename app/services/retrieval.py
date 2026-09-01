"""
Handles storing and searching chunk embeddings in ChromaDB.

Two responsibilities:
- store_chunks(): add new chunks + embeddings to the collection
  at ingestion time.
- search(): given a query embedding, return the top-k most
  similar chunks at query time.
"""

import chromadb

from app.config import CHROMA_DB_PATH

client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
collection = client.get_or_create_collection("askive_documents")


def store_chunks(document_id: str, chunks: list[str], embeddings: list[list[float]]):
    ids = [f"{document_id}-{i}" for i in range(len(chunks))]
    metadatas = [{"document_id": document_id} for _ in chunks]
    collection.add(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)


def search(query_embedding: list[float], top_k: int = 5, document_ids: list[str] | None = None) -> list[str]:
    where = {"document_id": {"$in": document_ids}} if document_ids else None
    results = collection.query(query_embeddings=[query_embedding], n_results=top_k, where=where)
    return results["documents"][0]
