from fastapi.testclient import TestClient

from app.main import app

from tests.conftest import sign_up
from tests.test_api import DOC


def new_chat(client, title=None):
    response = client.post("/chats", json={"title": title} if title else None)
    assert response.status_code == 201
    return response.json()


def upload_to(client, chat_id, text=DOC, name="policy.txt"):
    response = client.post(f"/chats/{chat_id}/documents", files={"file": (name, text.encode(), "text/plain")})
    assert response.status_code == 201
    return response.json()


def ask(client, chat_id, question):
    response = client.post(f"/chats/{chat_id}/messages", json={"question": question})
    assert response.status_code == 200, response.text
    return response.json()


def test_create_list_rename_delete(client):
    first = new_chat(client)
    second = new_chat(client, "Contracts")
    assert first["title"] == "New chat"

    titles = [c["title"] for c in client.get("/chats").json()]
    assert set(titles) == {"New chat", "Contracts"}

    renamed = client.patch(f"/chats/{first['id']}", json={"title": "  Policies  "})
    assert renamed.json()["title"] == "Policies"

    assert client.delete(f"/chats/{second['id']}").status_code == 204
    assert [c["id"] for c in client.get("/chats").json()] == [first["id"]]
    assert client.get(f"/chats/{second['id']}").status_code == 404


def test_upload_into_chat_and_open_it(client):
    chat = new_chat(client)
    document = upload_to(client, chat["id"])

    detail = client.get(f"/chats/{chat['id']}").json()

    assert detail["documents"] == [document]
    assert detail["messages"] == []


def test_asking_stores_both_messages_and_names_the_chat(client, fake_gemini):
    chat = new_chat(client)
    upload_to(client, chat["id"])

    reply = ask(client, chat["id"], "How long do refunds take?")

    assert reply["message"]["role"] == "assistant"
    assert reply["message"]["content"] == "Fake answer."
    assert any("Refunds" in s for s in reply["message"]["sources"])

    detail = client.get(f"/chats/{chat['id']}").json()
    assert [(m["role"], m["content"]) for m in detail["messages"]] == [
        ("user", "How long do refunds take?"),
        ("assistant", "Fake answer."),
    ]
    assert detail["title"] == "How long do refunds take?"


def test_chat_title_is_only_set_automatically_once(client, fake_gemini):
    chat = new_chat(client, "My title")
    upload_to(client, chat["id"])
    ask(client, chat["id"], "How long do refunds take?")
    assert client.get(f"/chats/{chat['id']}").json()["title"] == "My title"


def test_previous_turns_go_into_the_prompt(client, fake_gemini):
    chat = new_chat(client)
    upload_to(client, chat["id"])

    ask(client, chat["id"], "How long do refunds take?")
    ask(client, chat["id"], "Do I need anything?")

    assert "Q: How long do refunds take?\nA: Fake answer." in fake_gemini.prompts[-1]


def test_conversation_survives_a_new_client(client, fake_gemini):
    # What "saved on the server" means: a fresh browser with the same login sees it.
    chat = new_chat(client)
    upload_to(client, chat["id"])
    ask(client, chat["id"], "How long do refunds take?")

    other_device = TestClient(app)
    other_device.headers["Authorization"] = client.headers["Authorization"]

    messages = other_device.get(f"/chats/{chat['id']}").json()["messages"]
    assert len(messages) == 2


def test_chat_without_documents_is_rejected(client, fake_gemini):
    chat = new_chat(client)
    response = client.post(f"/chats/{chat['id']}/messages", json={"question": "Hello?"})
    assert response.status_code == 400
    assert fake_gemini.prompts == []


def test_only_the_chats_own_documents_are_searched(client, fake_gemini):
    refunds = new_chat(client)
    upload_to(client, refunds["id"])
    penguins = new_chat(client)
    upload_to(client, penguins["id"], text="Penguins live in Antarctica. Penguins eat fish.", name="penguins.txt")

    reply = ask(client, refunds["id"], "Where do penguins live?")

    assert all("Penguins" not in s for s in reply["message"]["sources"])


def test_other_users_get_404_for_every_route(client, fake_gemini):
    chat = new_chat(client)
    upload_to(client, chat["id"])

    intruder = TestClient(app)
    sign_up(intruder)
    chat_url = f"/chats/{chat['id']}"

    assert intruder.get(chat_url).status_code == 404
    assert intruder.patch(chat_url, json={"title": "mine now"}).status_code == 404
    assert intruder.delete(chat_url).status_code == 404
    assert intruder.post(f"{chat_url}/messages", json={"question": "Hi?"}).status_code == 404
    files = {"file": ("x.txt", b"Sneaky text.", "text/plain")}
    assert intruder.post(f"{chat_url}/documents", files=files).status_code == 404
    assert intruder.get("/chats").json() == []

    # And the owner's chat is untouched.
    assert client.get(chat_url).json()["title"] == "New chat"


def test_unknown_chat_is_404(client):
    assert client.get("/chats/does-not-exist").status_code == 404


def test_chats_require_login(anon_client):
    assert anon_client.get("/chats").status_code == 401
    assert anon_client.post("/chats").status_code == 401


def test_newest_activity_lists_first(client, fake_gemini):
    older = new_chat(client, "Older")
    newer = new_chat(client, "Newer")
    upload_to(client, older["id"])
    ask(client, older["id"], "How long do refunds take?")  # activity moves it to the top

    assert client.get("/chats").json()[0]["id"] == older["id"]
    assert newer["id"] in [c["id"] for c in client.get("/chats").json()]
