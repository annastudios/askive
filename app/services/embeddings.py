"""
Turns text into embedding vectors using whichever embedding
model you choose (OpenAI, Bedrock Titan, etc).

Used twice in the pipeline:
- At ingestion time, to embed each document chunk.
- At query time, to embed the user's (rewritten) question.

Both calls must use the SAME model, or the vectors won't be
comparable in similarity search.
"""


import voyageai

from app.config import VOYAGE_API_KEY, EMBEDDING_MODEL

client = voyageai.Client(api_key=VOYAGE_API_KEY)


def embed_texts(texts: list[str], input_type: str = "document") -> list[list[float]]:
    result = client.embed(texts, model=EMBEDDING_MODEL, input_type=input_type)
    return result.embeddings


def embed_text(text: str, input_type: str = "document") -> list[float]:
    return embed_texts([text], input_type=input_type)[0]
