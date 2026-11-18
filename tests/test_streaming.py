import json

import httpx
from fastapi.testclient import TestClient
from google.genai._gaos.lib.compat_errors import APIStatusError

from app.main import app
from app.services import qa

from tests.conftest import sign_up
from tests.test_chats import new_chat, upload_to


def stream(client, chat_id, question):
    """Posts a question and returns (status, [(event, data), ...])."""
    response = client.post(f"/chats/{chat_id}/messages/stream", json={"question": question})
    if response.status_code != 200:
        return response.status_code, response.json()
    assert response.headers["content-type"].startswith("text/event-stream")
    events = []
    for block in response.text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return 200, events


def chat_with_document(client):
    chat = new_chat(client)
    document = upload_to(client, chat["id"])
    return chat, document


def test_answer_streams_in_pieces_then_is_saved(client, fake_gemini):
    chat, _ = chat_with_document(client)

    status, events = stream(client, chat["id"], "How long do refunds take?")

    assert status == 200
    names = [name for name, _ in events]
    assert names[0] == "sources" and names[-1] == "done"
    assert names[1:-1] == ["delta", "delta"]  # the fake writes "Fake " then "answer."
    assert any("Refunds" in s for s in events[0][1]["sources"])
    assert "".join(data["text"] for name, data in events if name == "delta").strip() == "Fake answer."

    done = events[-1][1]
    assert done["message"]["role"] == "assistant"
    assert done["message"]["content"] == "Fake answer."
    assert done["cached"] is False

    saved = client.get(f"/chats/{chat['id']}").json()
    assert [(m["role"], m["content"]) for m in saved["messages"]] == [
        ("user", "How long do refunds take?"),
        ("assistant", "Fake answer."),
    ]
    assert saved["title"] == "How long do refunds take?"


def test_streamed_answer_goes_into_the_cache(client, fake_gemini):
    chat, document = chat_with_document(client)
    stream(client, chat["id"], "How long do refunds take?")

    user_id = client.get("/auth/me").json()["id"]
    result = qa.answer(user_id, "How long do refunds take?", [document["id"]], history=[])

    assert result["cached"] is True
    assert len(fake_gemini.prompts) == 1


def test_cached_answer_streams_as_one_piece(client, fake_gemini, monkeypatch):
    chat, _ = chat_with_document(client)
    monkeypatch.setattr(qa.answer_cache, "get", lambda *a: {"answer": "From the cache.", "sources": ["s1"]})

    _, events = stream(client, chat["id"], "How long do refunds take?")

    assert [name for name, _ in events] == ["sources", "delta", "done"]
    assert events[0][1] == {"sources": ["s1"], "cached": True}
    assert events[-1][1]["cached"] is True
    assert fake_gemini.prompts == []


def test_error_mid_stream_saves_nothing(client, fake_gemini):
    chat, _ = chat_with_document(client)
    fake_gemini.stream_error = "model overloaded"

    _, events = stream(client, chat["id"], "How long do refunds take?")

    assert [name for name, _ in events] == ["sources", "delta", "error"]
    assert "interrupted" in events[-1][1]["detail"]
    assert client.get(f"/chats/{chat['id']}").json()["messages"] == []


def test_chat_without_documents_is_a_normal_http_error(client, fake_gemini):
    empty = new_chat(client)
    assert stream(client, empty["id"], "Hello?")[0] == 400


def test_sources_are_ready_before_gemini_is_called(client, fake_gemini):
    # Gemini thinks for seconds before its first word, so the sources are
    # found (and can be sent) first, and Gemini starts only when the stream is read.
    _, document = chat_with_document(client)
    user_id = client.get("/auth/me").json()["id"]

    answer = qa.start_answer_stream(user_id, "How long do refunds take?", [document["id"]], history=[])

    assert any("Refunds" in s for s in answer.sources)
    assert fake_gemini.prompts == []
    assert "".join(answer.pieces).strip() == "Fake answer."
    assert len(fake_gemini.prompts) == 1


def test_quota_exhausted_arrives_as_an_error_event(client, fake_gemini):
    chat, _ = chat_with_document(client)
    request = httpx.Request("POST", "https://example.invalid")
    fake_gemini.error = APIStatusError("quota", response=httpx.Response(429, request=request), body=None)

    status, events = stream(client, chat["id"], "Hello?")

    assert status == 200
    assert [name for name, _ in events] == ["sources", "error"]
    assert "quota" in events[-1][1]["detail"]
    assert client.get(f"/chats/{chat['id']}").json()["messages"] == []


def test_other_users_cannot_stream_in_your_chat(client, fake_gemini):
    chat, _ = chat_with_document(client)
    intruder = TestClient(app)
    sign_up(intruder)

    status, body = stream(intruder, chat["id"], "Hello?")

    assert status == 404
    assert fake_gemini.prompts == []


def test_load_test_fake_streams_word_by_word(monkeypatch):
    from app.services import fake_ai

    monkeypatch.setattr(fake_ai, "LLM_SECONDS", 0)
    monkeypatch.setattr(fake_ai, "FIRST_WORDS_SECONDS", 0)

    pieces = [e.delta.text for e in fake_ai.FakeGeminiClient().interactions.create(model="x", input="q", stream=True)]

    assert len(pieces) > 5
    assert "".join(pieces) == fake_ai.ANSWER
