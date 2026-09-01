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
    current_chunk = [sentences[0]]

    for i in range(1, len(sentences)):
        similarity = _cosine_similarity(embeddings[i - 1], embeddings[i])
        if similarity < SIMILARITY_THRESHOLD:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentences[i]]
        else:
            current_chunk.append(sentences[i])

    chunks.append(" ".join(current_chunk))
    return chunks
