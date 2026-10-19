import time

import fakeredis
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import answer_cache, cache, memory

from tests.conftest import sign_up
from tests.test_api import upload


@pytest.fixture(params=["in-memory", "redis"])
def store(request, monkeypatch):
    """Runs a test against both the in-process fallback and (fake) Redis."""
    if request.param == "redis":
        s = fakeredis.FakeRedis(decode_responses=True)
    else:
        s = cache.InMemoryStore()
    monkeypatch.setattr(cache, "store", s)
    return s


# --- The store itself ---


def test_store_get_set_and_expiry(store):
    assert store.get("missing") is None
    store.set("k", "v")
    assert store.get("k") == "v"
    store.set("short", "v", ex=1)
    time.sleep(1.1)
    assert store.get("short") is None


def test_store_incr(store):
    assert store.incr("n") == 1
    assert store.incr("n") == 2
    assert store.get("n") == "2"


def test_store_lists(store):
    for i in range(5):
        store.rpush("l", str(i))
    assert store.lrange("l", 0, -1) == ["0", "1", "2", "3", "4"]
    store.ltrim("l", -3, -1)
    assert store.lrange("l", 0, -1) == ["2", "3", "4"]
    assert store.lrange("nothing", 0, -1) == []


def test_memory_keeps_only_recent_turns(store):
    for i in range(memory.MAX_TURNS + 5):
        memory.add_turn("s1", f"q{i}", f"a{i}")
    history = memory.get_history("s1")
    assert len(history) == memory.MAX_TURNS
    assert history[-1] == {"question": f"q{memory.MAX_TURNS + 4}", "answer": f"a{memory.MAX_TURNS + 4}"}


def test_normalize_question():
    assert answer_cache.normalize_question("  What   is the REFUND policy?? ") == "what is the refund policy"


# --- Answer caching through the API ---


def ask(client, question, document_ids, session_id="s1"):
    response = client.post(
        "/chat/", json={"question": question, "session_id": session_id, "document_ids": list(document_ids)}
    )
    assert response.status_code == 200
    return response.json()


def test_repeated_question_is_served_from_cache(store, client, fake_gemini):
    docs = [upload(client)["document_id"]]

    first = ask(client, "How long do refunds take?", docs, session_id="a")
    second = ask(client, "how long do refunds take", docs, session_id="b")

    assert first["cached"] is False
    assert second["cached"] is True
    assert second["answer"] == first["answer"]
    assert second["sources"] == first["sources"]
    assert len(fake_gemini.prompts) == 1


def test_cached_answer_still_recorded_in_memory(client, fake_gemini):
    docs = [upload(client)["document_id"]]
    ask(client, "How long do refunds take?", docs, session_id="a")
    ask(client, "How long do refunds take?", docs, session_id="b")

    assert memory.get_history(f"{client.get('/auth/me').json()['id']}:b") == [
        {"question": "How long do refunds take?", "answer": "Fake answer."}
    ]


def test_upload_invalidates_cached_answers(client, fake_gemini):
    docs = [upload(client)["document_id"]]
    ask(client, "How long do refunds take?", docs, session_id="a")

    upload(client, text="Refunds now take 90 days.", name="update.txt")
    again = ask(client, "How long do refunds take?", docs, session_id="b")

    assert again["cached"] is False
    assert len(fake_gemini.prompts) == 2


def test_different_document_selection_is_not_a_cache_hit(client, fake_gemini):
    first_doc = upload(client)["document_id"]
    second_doc = upload(client, name="copy.txt")["document_id"]

    ask(client, "How long do refunds take?", [first_doc], session_id="a")
    other = ask(client, "How long do refunds take?", [second_doc], session_id="b")

    assert other["cached"] is False


def test_follow_up_with_different_history_is_not_a_cache_hit(client, fake_gemini):
    docs = [upload(client)["document_id"]]
    ask(client, "Do I need anything?", docs, session_id="fresh")

    ask(client, "How long do refunds take?", docs, session_id="ongoing")
    follow_up = ask(client, "Do I need anything?", docs, session_id="ongoing")

    # Same words, but here it's a follow-up about refunds, so it needs a fresh answer.
    assert follow_up["cached"] is False


def test_cache_is_not_shared_between_users(client, fake_gemini):
    ask(client, "How long do refunds take?", [upload(client)["document_id"]])

    other = TestClient(app)
    sign_up(other)
    theirs = ask(other, "How long do refunds take?", [upload(other)["document_id"]])

    assert theirs["cached"] is False


def test_failed_answers_are_not_cached(client, fake_gemini):
    import httpx
    from google.genai._gaos.lib.compat_errors import APIStatusError

    docs = [upload(client)["document_id"]]
    fake_gemini.error = APIStatusError(
        "quota", response=httpx.Response(429, request=httpx.Request("POST", "https://x.invalid")), body=None
    )
    client.post("/chat/", json={"question": "How long do refunds take?", "session_id": "a", "document_ids": docs})

    fake_gemini.error = None
    assert ask(client, "How long do refunds take?", docs, session_id="b")["cached"] is False


# --- Query embedding cache ---


def test_query_embeddings_are_cached(client, fake_gemini, fake_voyage):
    first = upload(client)["document_id"]
    second = upload(client, name="copy.txt")["document_id"]
    calls_after_upload = len(fake_voyage.calls)

    # Different document selections, so the answer cache can't short-circuit -
    # the second request still needs an embedding, but it reuses the first one.
    ask(client, "How long do refunds take?", [first], session_id="a")
    ask(client, "How long do refunds take?", [first, second], session_id="b")

    assert len(fake_voyage.calls) == calls_after_upload + 1
