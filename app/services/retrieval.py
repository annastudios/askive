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
import threading
from collections import Counter, OrderedDict

import chromadb

from app.config import CHROMA_DB_PATH, CHROMA_HOST, CHROMA_PORT

_collection = None


def get_collection():
    """Connects on first use rather than at import, so the API can start
    before the ChromaDB server is up; a failed attempt is retried on the
    next call.

    With CHROMA_HOST set (docker-compose, Kubernetes) ChromaDB runs as its
    own server; otherwise it's embedded in this process, storing files on disk."""
    global _collection
    if _collection is None:
        if CHROMA_HOST:
            client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        else:
            client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        _collection = client.get_or_create_collection("askive_documents")
    return _collection

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
    """Classic Okapi BM25 over a set of chunks (one chat's documents)."""

    K1 = 1.5
    B = 0.75

    def __init__(self, ids: list[str], documents: list[str], metadatas: list[dict]):
        self.ids = ids
        self.documents = documents
        self.document_ids = [m["document_id"] for m in metadatas]
        # v1 chunks were stored without an owner; they never match any user.
        self.user_ids = [m.get("user_id") for m in metadatas]
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

    def search(
        self, query: str, top_k: int, user_id: str, document_ids: list[str] | None = None
    ) -> list[str]:
        query_terms = [t for t in tokenize(query) if t in self.idf]
        if not query_terms:
            return []

        allowed = set(document_ids) if document_ids else None
        scored = []
        for i, counts in enumerate(self.term_counts):
            if self.user_ids[i] != user_id:
                continue
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


# Keyword indexes, one per (user, set of documents) - i.e. per chat. Uploaded
# documents never change, so an index can be reused for as long as it stays in
# this small least-recently-used cache.
#
# This replaced a single index over every chunk of every user, rebuilt whenever
# the total chunk count changed. Under load that meant a 9-second rebuild after
# every upload, run by many requests at once - the load test found it
# saturating the CPU until Kubernetes restarted the pod.
KEYWORD_INDEX_CACHE_SIZE = 256
_keyword_indexes: "OrderedDict[tuple, BM25Index]" = OrderedDict()
_keyword_indexes_lock = threading.Lock()


def _keyword_index(user_id: str, document_ids: list[str] | None) -> BM25Index:
    where = {"user_id": user_id}
    if document_ids:
        where = {"$and": [where, {"document_id": {"$in": document_ids}}]}
    # Without a document list the index covers all of a user's documents, which
    # grows with every upload - so only explicit document sets are cached.
    key = (user_id, tuple(sorted(document_ids))) if document_ids else None

    if key is not None:
        with _keyword_indexes_lock:
            if key in _keyword_indexes:
                _keyword_indexes.move_to_end(key)
                return _keyword_indexes[key]

    chunks = get_collection().get(where=where, include=["documents", "metadatas"])
    index = BM25Index(chunks["ids"], chunks["documents"], chunks["metadatas"])

    if key is not None:
        with _keyword_indexes_lock:
            _keyword_indexes[key] = index
            _keyword_indexes.move_to_end(key)
            while len(_keyword_indexes) > KEYWORD_INDEX_CACHE_SIZE:
                _keyword_indexes.popitem(last=False)
    return index


def reciprocal_rank_fusion(ranked_lists: list[list[str]]) -> list[str]:
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, chunk_id in enumerate(ranked):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1 / (RRF_K + rank + 1)
    return sorted(scores, key=scores.get, reverse=True)


def store_chunks(user_id: str, document_id: str, chunks: list[str], embeddings: list[list[float]]):
    if not chunks:
        return
    ids = [f"{document_id}-{i}" for i in range(len(chunks))]
    metadatas = [{"document_id": document_id, "user_id": user_id} for _ in chunks]
    get_collection().add(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)


def semantic_search(
    query_embedding: list[float], top_k: int, user_id: str, document_ids: list[str] | None = None
) -> list[str]:
    where = {"user_id": user_id}
    if document_ids:
        where = {"$and": [where, {"document_id": {"$in": document_ids}}]}
    results = get_collection().query(query_embeddings=[query_embedding], n_results=top_k, where=where)
    return results["ids"][0]


def keyword_search(
    query: str, top_k: int, user_id: str, document_ids: list[str] | None = None
) -> list[str]:
    return _keyword_index(user_id, document_ids).search(query, top_k, user_id, document_ids)


def search(
    query: str,
    query_embedding: list[float],
    user_id: str,
    top_k: int = 5,
    document_ids: list[str] | None = None,
) -> list[str]:
    """Only ever returns chunks owned by user_id."""
    candidates = top_k * CANDIDATE_MULTIPLIER
    fused = reciprocal_rank_fusion([
        semantic_search(query_embedding, candidates, user_id, document_ids),
        keyword_search(query, candidates, user_id, document_ids),
    ])[:top_k]
    if not fused:
        return []
    found = get_collection().get(ids=fused, include=["documents"])
    text_by_id = dict(zip(found["ids"], found["documents"]))
    return [text_by_id[chunk_id] for chunk_id in fused]
