from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

from app.main import app

from tests.conftest import TEST_JWT_SECRET, sign_up, unique_email
from tests.test_api import upload


def test_register_and_login_with_email(anon_client):
    email = unique_email("ankita")
    response = anon_client.post("/auth/register", json={"email": email, "password": "s3cret-pass"})
    assert response.status_code == 201
    assert response.json()["email"] == email
    assert "password" not in response.text

    login = anon_client.post("/auth/login", data={"username": email, "password": "s3cret-pass"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = anon_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["email"] == email


def test_email_is_case_insensitive(anon_client):
    email = unique_email("Mixed.Case")
    response = anon_client.post("/auth/register", json={"email": f"  {email.upper()} ", "password": "password1"})
    assert response.json()["email"] == email.lower()

    login = anon_client.post("/auth/login", data={"username": email.title(), "password": "password1"})
    assert login.status_code == 200


def test_duplicate_email_rejected_case_insensitively(anon_client):
    email = unique_email("dupe")
    anon_client.post("/auth/register", json={"email": email, "password": "password1"})
    response = anon_client.post("/auth/register", json={"email": email.upper(), "password": "password2"})
    assert response.status_code == 409


def test_wrong_password_rejected(anon_client):
    email = unique_email("wrongpw")
    anon_client.post("/auth/register", json={"email": email, "password": "right-password"})
    response = anon_client.post("/auth/login", data={"username": email, "password": "nope-nope"})
    assert response.status_code == 401


def test_unknown_user_rejected(anon_client):
    response = anon_client.post("/auth/login", data={"username": unique_email("ghost"), "password": "whatever1"})
    assert response.status_code == 401


def test_bad_registration_input_rejected(anon_client):
    def register(email, password):
        return anon_client.post("/auth/register", json={"email": email, "password": password}).status_code

    assert register(unique_email("ok"), "short") == 422
    assert register("not-an-email", "longenough") == 422
    assert register("two@@example.com", "longenough") == 422
    assert register(unique_email("longpw"), "x" * 73) == 422


def test_protected_routes_require_login(anon_client):
    assert anon_client.get("/documents/").status_code == 401
    assert anon_client.post("/chat/", json={"question": "hi", "session_id": "s"}).status_code == 401
    files = {"file": ("a.txt", b"hello.", "text/plain")}
    assert anon_client.post("/upload/", files=files).status_code == 401


def test_garbage_and_expired_tokens_rejected(anon_client):
    assert anon_client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401

    user = sign_up(anon_client)
    expired = jwt.encode(
        {"sub": user["id"], "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    assert anon_client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_token_signed_with_wrong_secret_rejected(anon_client):
    user = sign_up(anon_client)
    forged = jwt.encode({"sub": user["id"]}, "attacker-secret-also-32-bytes-long-xx", algorithm="HS256")
    assert anon_client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_documents_list_shows_only_own_uploads(client):
    upload(client, name="mine.txt")

    other = TestClient(app)
    sign_up(other)
    upload(other, name="theirs.txt")

    assert [d["filename"] for d in client.get("/documents/").json()] == ["mine.txt"]
    assert [d["filename"] for d in other.get("/documents/").json()] == ["theirs.txt"]


def test_users_cannot_search_each_others_documents(client, fake_gemini):
    doc_id = upload(client, text="The vault combination is 4-8-15-16.", name="vault.txt")["document_id"]

    intruder = TestClient(app)
    sign_up(intruder)
    # Even passing the victim's document id explicitly must not leak it.
    response = intruder.post(
        "/chat/",
        json={"question": "What is the vault combination?", "session_id": "s1", "document_ids": [doc_id]},
    )

    assert response.status_code == 200
    assert response.json()["sources"] == []


def test_chat_memory_is_separate_per_user(client, fake_gemini):
    doc_id = upload(client)["document_id"]
    client.post("/chat/", json={"question": "Private question?", "session_id": "shared", "document_ids": [doc_id]})

    other = TestClient(app)
    sign_up(other)
    their_doc = upload(other)["document_id"]
    other.post("/chat/", json={"question": "Hello?", "session_id": "shared", "document_ids": [their_doc]})

    assert "Private question?" not in fake_gemini.prompts[-1]
