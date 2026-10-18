"""
Handles storing and searching chunks in ChromaDB.

- store_chunks(): add new chunks + embeddings to the collection
  at ingestion time.
- search(): hybrid search at query time. Runs two searches and
  merges them:
    * semantic: nearest embeddings in ChromaDB (finds chunks that
      mean the same thing, even with different wording)
    * keyword: BM25 over the chunk text (finds exact terms that
      embeddings can blur - names, codes, error messages)
  The two ranked lists are merged with Reciprocal Rank Fusion.
"""

import math
import re
from collections import Counter

import chromadb

from app.config import CHROMA_DB_PATH

client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
collection = client.get_or_create_collection("askive_documents")

# RRF constant from the original paper; dampens how much the very top
# ranks dominate, so agreement between both searches matters more.
RRF_K = 60
# Each search contributes this many times top_k candidates to the fusion.
CANDIDATE_MULTIPLIER = 4

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for",
    "from", "how", "i", "in", "is", "it", "of", "on", "or", "that", "the", "this",
    "to", "was", "what", "when", "where", "which", "who", "why", "with", "you",
}


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"\w+", text.lower()) if t not in STOPWORDS]


class BM25Index:
    """Classic Okapi BM25 over every chunk in the collection."""

    K1 = 1.5
    B = 0.75

    def __init__(self, ids: list[str], documents: list[str], metadatas: list[dict]):
        self.ids = ids
        self.documents = documents
        self.document_ids = [m["document_id"] for m in metadatas]
        self.term_counts = [Counter(tokenize(d)) for d in documents]
        self.lengths = [sum(c.values()) for c in self.term_counts]
        self.avg_length = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0

        doc_freq = Counter(term for counts in self.term_counts for term in counts)
        n = len(documents)
        self.idf = {
            term: math.log((n - df + 0.5) / (df + 0.5) + 1) for term, df in doc_freq.items()
        }

    def __len__(self):
        return len(self.ids)

    def search(self, query: str, top_k: int, document_ids: list[str] | None = None) -> list[str]:
        query_terms = [t for t in tokenize(query) if t in self.idf]
        if not query_terms:
            return []

        allowed = set(document_ids) if document_ids else None
        scored = []
        for i, counts in enumerate(self.term_counts):
            if allowed is not None and self.document_ids[i] not in allowed:
                continue
            score = 0.0
            for term in query_terms:
                tf = counts.get(term, 0)
                if tf:
                    norm = 1 - self.B + self.B * self.lengths[i] / self.avg_length
                    score += self.idf[term] * tf * (self.K1 + 1) / (tf + self.K1 * norm)
            if score > 0:
                scored.append((score, self.ids[i]))

        scored.sort(reverse=True)
        return [chunk_id for _, chunk_id in scored[:top_k]]


_bm25_index: BM25Index | None = None


def _get_bm25_index() -> BM25Index:
    """The keyword index lives in memory. It's rebuilt whenever the number
    of chunks in ChromaDB changes, which also picks up uploads made by
    other API replicas sharing the same ChromaDB."""
    global _bm25_index
    if _bm25_index is None or len(_bm25_index) != collection.count():
        everything = collection.get(include=["documents", "metadatas"])
        _bm25_index = BM25Index(everything["ids"], everything["documents"], everything["metadatas"])
    return _bm25_index


def reciprocal_rank_fusion(ranked_lists: list[list[str]]) -> list[str]:
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, chunk_id in enumerate(ranked):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1 / (RRF_K + rank + 1)
    return sorted(scores, key=scores.get, reverse=True)


def store_chunks(document_id: str, chunks: list[str], embeddings: list[list[float]]):
    ids = [f"{document_id}-{i}" for i in range(len(chunks))]
    metadatas = [{"document_id": document_id} for _ in chunks]
    collection.add(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)


def semantic_search(query_embedding: list[float], top_k: int, document_ids: list[str] | None = None) -> list[str]:
    where = {"document_id": {"$in": document_ids}} if document_ids else None
    results = collection.query(query_embeddings=[query_embedding], n_results=top_k, where=where)
    return results["ids"][0]


def keyword_search(query: str, top_k: int, document_ids: list[str] | None = None) -> list[str]:
    return _get_bm25_index().search(query, top_k, document_ids)


def search(
    query: str,
    query_embedding: list[float],
    top_k: int = 5,
    document_ids: list[str] | None = None,
) -> list[str]:
    candidates = top_k * CANDIDATE_MULTIPLIER
    fused = reciprocal_rank_fusion([
        semantic_search(query_embedding, candidates, document_ids),
        keyword_search(query, candidates, document_ids),
    ])[:top_k]
    if not fused:
        return []
    found = collection.get(ids=fused, include=["documents"])
    text_by_id = dict(zip(found["ids"], found["documents"]))
    return [text_by_id[chunk_id] for chunk_id in fused]
