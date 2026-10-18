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

from app.config import VOYAGE_API_KEY, EMBEDDING_MODEL
from app.services import cache

client = voyageai.Client(api_key=VOYAGE_API_KEY)

# Embeddings for a given text and model never change, so they can live long.
EMBEDDING_CACHE_TTL_SECONDS = 7 * 24 * 3600


class EmbeddingRateLimited(Exception):
    """Voyage refused the request for exceeding its rate limit. Without a
    payment method on the account that's only 3 requests and 10K tokens
    per minute, which a single multi-page PDF can exceed on its own."""


def embed_texts(texts: list[str], input_type: str = "document") -> list[list[float]]:
    try:
        result = client.embed(texts, model=EMBEDDING_MODEL, input_type=input_type)
    except voyageai.error.RateLimitError as e:
        raise EmbeddingRateLimited(str(e)) from e
    return result.embeddings


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
