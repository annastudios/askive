import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.services import ingest, users

from tests.conftest import sign_up
from tests.test_api import DOC
from tests.test_chats import new_chat


def upload(client, data: bytes = DOC.encode(), name="policy.txt", content_type="text/plain"):
    chat = new_chat(client)
    response = client.post(f"/chats/{chat['id']}/documents", files={"file": (name, data, content_type)})
    assert response.status_code == 201, response.text
    return response.json()


def test_original_file_comes_back_for_preview(client):
    document = upload(client)

    response = client.get(f"/documents/{document['id']}/file")

    assert response.status_code == 200
    assert response.content == DOC.encode()
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert response.headers["content-disposition"].startswith("inline")
    assert response.headers["x-content-type-options"] == "nosniff"


def test_document_text_for_preview(client):
    document = upload(client)

    body = client.get(f"/documents/{document['id']}/text").json()

    assert body == {"filename": "policy.txt", "text": DOC}


def test_unsafe_file_types_are_downloaded_not_displayed(client):
    # An uploaded HTML file must never run as a page on this site.
    document = upload(client, b"<script>alert(1)</script> Refunds take 30 days.", "evil.html", "text/html")

    response = client.get(f"/documents/{document['id']}/file")

    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-disposition"].startswith("attachment")


def test_other_users_cannot_fetch_your_files(client):
    document = upload(client)
    intruder = TestClient(app)
    sign_up(intruder)

    assert intruder.get(f"/documents/{document['id']}/file").status_code == 404
    assert intruder.get(f"/documents/{document['id']}/text").status_code == 404


def test_documents_from_before_previews_say_so(client):
    user_id = client.get("/auth/me").json()["id"]
    old_id = str(uuid.uuid4())
    users.add_document(user_id, old_id, "old.pdf", 3)  # no stored file, like pre-v3 uploads

    response = client.get(f"/documents/{old_id}/file")

    assert response.status_code == 404
    assert "uploaded again" in response.json()["detail"]


def test_files_over_the_limit_are_rejected(client, monkeypatch):
    monkeypatch.setattr(ingest, "MAX_UPLOAD_MB", 0)
    chat = new_chat(client)

    response = client.post(f"/chats/{chat['id']}/documents", files={"file": ("big.txt", DOC.encode(), "text/plain")})

    assert response.status_code == 413
    assert client.get(f"/chats/{chat['id']}").json()["documents"] == []


def test_file_type_is_guessed_when_the_browser_sends_none(client):
    document = upload(client, content_type="application/octet-stream")
    assert client.get(f"/documents/{document['id']}/file").headers["content-type"] == "text/plain; charset=utf-8"
