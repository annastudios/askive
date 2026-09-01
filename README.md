# Askive

Chat with your documents. A RAG app with semantic chunking and
conversation memory, built with FastAPI, ChromaDB, Voyage AI, and
Gemini.

<img width="1915" height="892" alt="image" src="https://github.com/user-attachments/assets/57d33ef4-6b72-4ea7-aae0-db11f662ccc5" />


## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in your Gemini and Voyage API keys
uvicorn app.main:app --reload
```

## Architecture

**Ingestion**: upload document -> semantic chunking -> generate
embeddings -> store in ChromaDB

**Query**: user asks question -> rewrite with memory -> embed
question -> similarity search in ChromaDB -> generate answer with
Gemini, using retrieved chunks as context

## Roadmap

- [ ] Wire up `services/chunking.py` (semantic chunking)
- [ ] Wire up `services/embeddings.py`
- [ ] Wire up `services/retrieval.py` (ChromaDB store + search)
- [ ] Wire up `services/memory.py` (query rewriting)
- [ ] Connect it all in `routes/upload.py` and `routes/chat.py`
- [ ] v2: migrate storage from ChromaDB to AWS RDS Postgres + pgvector
