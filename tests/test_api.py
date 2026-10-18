import httpx
from google.genai._gaos.lib.compat_errors import APIStatusError

DOC = (
    "Refunds are accepted within 30 days. Refunds need a receipt. "
    "Shipping takes five business days. Shipping is free over fifty dollars."
)


def upload(client, text=DOC, name="policy.txt"):
    response = client.post("/upload/", files={"file": (name, text.encode(), "text/plain")})
    assert response.status_code == 200
    return response.json()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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


def test_chat_returns_503_when_gemini_quota_exhausted(client, fake_gemini):
    request = httpx.Request("POST", "https://example.invalid")
    fake_gemini.error = APIStatusError(
        "quota", response=httpx.Response(429, request=request), body=None
    )

    response = client.post("/chat/", json={"question": "Hi?", "session_id": "s1"})

    assert response.status_code == 503
