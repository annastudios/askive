FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    DATABASE_PATH=/app/data/askive.db \
    CHROMA_DB_PATH=/app/data/chroma_db

WORKDIR /app

# Dependencies first: this layer is only rebuilt when requirements.txt
# changes, so code edits rebuild in seconds.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

# Run as an unprivileged user; it owns only the data directory.
RUN useradd --create-home --uid 1000 askive \
    && mkdir -p /app/data \
    && chown askive:askive /app/data
USER askive

EXPOSE 8000

# API keys and secrets (GEMINI_API_KEY, VOYAGE_API_KEY, JWT_SECRET) are
# never baked into the image - pass them as environment variables at runtime.

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live', timeout=3)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
