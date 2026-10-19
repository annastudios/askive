import httpx
import voyageai.error
from google.genai._gaos.lib.compat_errors import APIStatusError

DOC = (
    "Refunds are accepted within 30 days. Refunds need a receipt. "
    "Shipping takes five business days. Shipping is free over fifty dollars."
)


def upload(client, text=DOC, name="policy.txt"):
    response = client.post("/upload/", files={"file": (name, text.encode(), "text/plain")})
    assert response.status_code == 200
    return response.json()


def test_health(anon_client):
    response = anon_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {"chroma": "ok", "cache": "ok", "database": "ok"},
    }


def test_liveness(anon_client):
    assert anon_client.get("/health/live").json() == {"status": "ok"}


def test_health_reports_503_when_a_dependency_is_down(anon_client, fresh_cache, monkeypatch):
    def redis_down():
        raise ConnectionError("redis unreachable")

    monkeypatch.setattr(fresh_cache, "ping", redis_down)

    response = anon_client.get("/health")

    assert response.status_code == 503
    assert response.json()["checks"]["cache"] == "error: ConnectionError"
    # Liveness ignores dependencies, so Kubernetes won't restart the API over a Redis outage.
    assert anon_client.get("/health/live").status_code == 200


def test_frontend_files_are_always_revalidated(anon_client):
    for path in ["/", "/app.js", "/style.css"]:
        response = anon_client.get(path)
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == "no-cache"
        assert "etag" in response.headers

    etag = anon_client.get("/app.js").headers["etag"]
    assert anon_client.get("/app.js", headers={"If-None-Match": etag}).status_code == 304


def test_upload_txt(client):
    body = upload(client)
    assert body["document_id"]
    assert body["chunks_created"] > 0


def test_chat_answers_from_uploaded_document(client, fake_gemini):
    doc_id = upload(client)["document_id"]

    response = client.post(
        "/chat/",
        json={"question": "How long do refunds take?", "session_id": "s1", "document_ids": [doc_id]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Fake answer."
    assert any("Refunds" in source for source in body["sources"])
    assert "Refunds are accepted within 30 days." in fake_gemini.prompts[0]


def test_chat_only_searches_selected_documents(client, fake_gemini):
    first = upload(client)["document_id"]
    upload(client, text="Penguins live in Antarctica. Penguins eat fish.", name="penguins.txt")

    response = client.post(
        "/chat/",
        json={"question": "Where do penguins live?", "session_id": "s1", "document_ids": [first]},
    )

    assert all("Penguins" not in source for source in response.json()["sources"])


def test_chat_includes_recent_conversation(client, fake_gemini):
    doc_id = upload(client)["document_id"]
    payload = {"session_id": "s1", "document_ids": [doc_id]}

    client.post("/chat/", json={"question": "How long do refunds take?", **payload})
    client.post("/chat/", json={"question": "Do I need anything?", **payload})

    assert "Q: How long do refunds take?\nA: Fake answer." in fake_gemini.prompts[1]


def test_chat_without_documents_is_rejected_not_searched_across_everything(client, fake_gemini, fake_voyage):
    upload(client)  # the user owns a document, but this chat has none attached
    calls_after_upload = len(fake_voyage.calls)

    response = client.post("/chat/", json={"question": "What is this about?", "session_id": "new-chat"})

    assert response.status_code == 400
    assert "no documents" in response.json()["detail"]
    assert fake_gemini.prompts == []
    assert len(fake_voyage.calls) == calls_after_upload


def test_chat_returns_503_when_gemini_quota_exhausted(client, fake_gemini):
    doc_id = upload(client)["document_id"]
    request = httpx.Request("POST", "https://example.invalid")
    fake_gemini.error = APIStatusError(
        "quota", response=httpx.Response(429, request=request), body=None
    )

    response = client.post("/chat/", json={"question": "Hi?", "session_id": "s1", "document_ids": [doc_id]})

    assert response.status_code == 503


def test_upload_returns_clear_429_when_voyage_rate_limited(client, fake_voyage):
    fake_voyage.error = voyageai.error.RateLimitError("reduced rate limits of 3 RPM and 10K TPM")

    response = client.post("/upload/", files={"file": ("big.txt", DOC.encode(), "text/plain")})

    assert response.status_code == 429
    assert "rate limit" in response.json()["detail"]
    assert response.headers["Retry-After"] == "60"
    # Nothing half-saved: the failed upload doesn't appear in the document list.
    assert client.get("/documents/").json() == []


def test_chat_returns_clear_429_when_voyage_rate_limited(client, fake_voyage, fake_gemini):
    doc_id = upload(client)["document_id"]
    fake_voyage.error = voyageai.error.RateLimitError("reduced rate limits")

    response = client.post("/chat/", json={"question": "Hi?", "session_id": "s1", "document_ids": [doc_id]})

    assert response.status_code == 429
    assert "rate limit" in response.json()["detail"]
    assert fake_gemini.prompts == []


def test_liveness_does_not_need_a_worker_thread():
    # Under load every worker thread can be busy; an async route still answers.
    import inspect

    from app.routes import health

    assert inspect.iscoroutinefunction(health.live)


def test_startup_sets_the_thread_pool_size():
    import anyio
    import anyio.to_thread

    from app.config import THREAD_POOL_SIZE
    from app.main import configure_thread_pool

    async def configured_size():
        configure_thread_pool()
        return anyio.to_thread.current_default_thread_limiter().total_tokens

    assert THREAD_POOL_SIZE == 100
    assert anyio.run(configured_size) == 100
