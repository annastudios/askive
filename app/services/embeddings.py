"""
Turns text into embedding vectors using whichever embedding
model you choose (OpenAI, Bedrock Titan, etc).

Used twice in the pipeline:
- At ingestion time, to embed each document chunk.
- At query time, to embed the user's (rewritten) question.

Both calls must use the SAME model, or the vectors won't be
comparable in similarity search.
"""


import hashlib
import json

import voyageai
import voyageai.error

from app.config import EMBEDDING_MODEL, FAKE_AI, VOYAGE_API_KEY
from app.services import cache

if FAKE_AI:
    from app.services.fake_ai import FakeVoyageClient

    client = FakeVoyageClient()
else:
    # max_retries: on a rate limit, a timeout or a 503 from Voyage, the client
    # waits (about 1s, 2s, 4s, with jitter) and tries again before giving up.
    client = voyageai.Client(api_key=VOYAGE_API_KEY, max_retries=4)

# Embeddings for a given text and model never change, so they can live long.
EMBEDDING_CACHE_TTL_SECONDS = 7 * 24 * 3600

# Voyage rejects a request with more than 1,000 texts, or (for voyage-3) more
# than 120K tokens. Long documents have more sentences than that, so they're
# sent in batches. The token budget is kept well under the limit because it's
# only estimated (about 3 characters per token is deliberately pessimistic).
MAX_TEXTS_PER_REQUEST = 1000
MAX_TOKENS_PER_REQUEST = 60_000


def _estimated_tokens(text: str) -> int:
    return len(text) // 3 + 1


def _batches(texts: list[str]) -> list[list[str]]:
    batches, current, current_tokens = [], [], 0
    for text in texts:
        tokens = _estimated_tokens(text)
        if current and (len(current) == MAX_TEXTS_PER_REQUEST or current_tokens + tokens > MAX_TOKENS_PER_REQUEST):
            batches.append(current)
            current, current_tokens = [], 0
        current.append(text)
        current_tokens += tokens
    if current:
        batches.append(current)
    return batches


class EmbeddingRateLimited(Exception):
    """Voyage refused the request for exceeding its rate limit. Without a
    payment method on the account that's only 3 requests and 10K tokens
    per minute, which a single multi-page PDF can exceed on its own.
    Raised only after the client's own retries have run out."""


def embed_texts(texts: list[str], input_type: str = "document") -> list[list[float]]:
    """Returns one vector per text, in the same order, however many requests it takes."""
    vectors: list[list[float]] = []
    for batch in _batches(texts):
        try:
            result = client.embed(batch, model=EMBEDDING_MODEL, input_type=input_type)
        except voyageai.error.RateLimitError as e:
            raise EmbeddingRateLimited(str(e)) from e
        vectors.extend(result.embeddings)
    return vectors


def embed_text(text: str, input_type: str = "document") -> list[float]:
    # Questions repeat a lot; caching their vectors saves a Voyage call each
    # time, which matters with the free tier's 3 requests per minute.
    key = f"embedding:{EMBEDDING_MODEL}:{input_type}:{hashlib.sha256(text.encode()).hexdigest()}"
    cached = cache.store.get(key)
    if cached:
        return json.loads(cached)
    vector = embed_texts([text], input_type=input_type)[0]
    cache.store.set(key, json.dumps(vector), ex=EMBEDDING_CACHE_TTL_SECONDS)
    return vector
