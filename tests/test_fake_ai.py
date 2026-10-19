import os
import subprocess
import sys

from app import config
from app.services import fake_ai


def test_fake_ai_is_off_by_default():
    assert config.FAKE_AI is False


def _client_types(env_overrides: dict) -> str:
    """Imports the app in a fresh process (settings are read at import time)."""
    env = {**os.environ, **env_overrides}
    code = (
        "from app import config; from app.services import embeddings; "
        "print(type(config.gemini_client).__name__, type(embeddings.client).__name__)"
    )
    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def test_only_fake_ai_1_switches_to_fakes():
    assert _client_types({"FAKE_AI": "1"}) == "FakeGeminiClient FakeVoyageClient"
    for value in ["0", "true", "yes", ""]:
        assert _client_types({"FAKE_AI": value}) == "Client Client"


def test_fake_clients_mimic_the_real_interfaces(monkeypatch):
    monkeypatch.setattr(fake_ai, "EMBED_SECONDS", 0)
    monkeypatch.setattr(fake_ai, "LLM_SECONDS", 0)

    vectors = fake_ai.FakeVoyageClient().embed(["refund policy", "shipping"], model="voyage-3").embeddings
    assert len(vectors) == 2
    assert all(len(v) == 1024 for v in vectors)  # same size as voyage-3

    answer = fake_ai.FakeGeminiClient().interactions.create(model="x", input="question")
    assert "FAKE_AI" in answer.output_text
