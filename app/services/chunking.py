"""
Semantic chunking: splits document text into chunks based on
meaning/topic shifts rather than a fixed character count.

Typical approach:
1. Split raw text into sentences.
2. Embed each sentence.
3. Walk through sentences, comparing embedding similarity
   between consecutive sentences.
4. When similarity drops below a threshold, start a new chunk
   (that's a topic boundary).
"""


import re

from app.services.embeddings import embed_texts

SIMILARITY_THRESHOLD = 0.5

# Chunk size limits, in characters (~a short paragraph to ~a long one).
# Topic shifts alone split too eagerly: a one-page document became a dozen
# one-sentence chunks, which read badly and give the model little context.
# So a topic shift only starts a new chunk once the current one is at least
# MIN long, and a chunk is always cut before it grows past MAX.
MIN_CHUNK_CHARS = 400
MAX_CHUNK_CHARS = 1500


def _split_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if s.strip()]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def chunk_text(text: str) -> list[str]:
    sentences = _split_sentences(text)
    if not sentences:
        return []

    embeddings = embed_texts(sentences, input_type="document")

    chunks: list[str] = []
    current = [sentences[0]]
    current_len = len(sentences[0])

    for i in range(1, len(sentences)):
        sentence = sentences[i]
        too_big = current_len + 1 + len(sentence) > MAX_CHUNK_CHARS
        topic_shift = _cosine_similarity(embeddings[i - 1], embeddings[i]) < SIMILARITY_THRESHOLD
        if too_big or (topic_shift and current_len >= MIN_CHUNK_CHARS):
            chunks.append(" ".join(current))
            current, current_len = [sentence], len(sentence)
        else:
            current.append(sentence)
            current_len += 1 + len(sentence)

    last = " ".join(current)
    # A short leftover reads better as the end of the previous chunk.
    if chunks and len(last) < MIN_CHUNK_CHARS and len(chunks[-1]) + 1 + len(last) <= MAX_CHUNK_CHARS:
        chunks[-1] = f"{chunks[-1]} {last}"
    else:
        chunks.append(last)
    return chunks
