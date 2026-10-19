"""
Askive load test. Each simulated user behaves like a person:

  1. registers and logs in (once),
  2. uploads one small document into their chat (once),
  3. then loops: mostly re-asks common questions (served from cache), sometimes
     asks something new (full search + LLM call), occasionally lists documents,
     pausing 1-3 seconds between actions like a person reading the answer.

Meant to run against an API started with FAKE_AI=1 (see app/services/fake_ai.py),
so no real Voyage/Gemini quota is spent. Results are grouped by request name,
so cached and uncached questions show up as separate rows.

Run:  locust -f loadtest/locustfile.py --host http://localhost:8000
"""

import random
import uuid
from collections import Counter

from locust import HttpUser, between, events, task

DOCUMENT = (
    "Refunds are accepted within 30 days of purchase. A receipt is required for every refund. "
    "Shipping takes five business days. Shipping is free on orders over fifty dollars. "
    "Gift cards cannot be refunded. Support is available on weekdays from nine to five. "
    "Damaged items can be exchanged within seven days. International orders take two weeks."
)

# A small, shared set: after the first user asks one, everyone else gets the cached answer.
COMMON_QUESTIONS = [
    "How long do refunds take?",
    "Is shipping free?",
    "Can gift cards be refunded?",
    "When is support available?",
    "How long do international orders take?",
]

PASSWORD = "load-test-password"

# How many answers came from the cache, per request name. The cache is per
# user, so each user's first ask of a common question is still a miss.
cache_hits: Counter = Counter()
answers: Counter = Counter()


@events.reset_stats.add_listener
def _reset_cache_counts(**kwargs):
    cache_hits.clear()
    answers.clear()


@events.quitting.add_listener
def _print_cache_hit_rate(environment, **kwargs):
    for name in sorted(answers):
        print(f"CACHE {name}: {cache_hits[name]}/{answers[name]} answers cached "
              f"({100 * cache_hits[name] / answers[name]:.0f}%)")


class AskiveUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        email = f"load.{uuid.uuid4().hex[:12]}@example.com"
        self.client.post("/auth/register", json={"email": email, "password": PASSWORD}, name="auth: register")
        token = self.client.post(
            "/auth/login", data={"username": email, "password": PASSWORD}, name="auth: login"
        ).json()["access_token"]
        self.client.headers["Authorization"] = f"Bearer {token}"

        upload = self.client.post(
            "/upload/", files={"file": ("policy.txt", DOCUMENT.encode(), "text/plain")}, name="upload"
        )
        self.document_ids = [upload.json()["document_id"]]

    def _ask(self, question: str, name: str):
        # A fresh session per question: a question with no conversation history
        # is what the answer cache can reuse.
        with self.client.post(
            "/chat/",
            json={"question": question, "session_id": str(uuid.uuid4()), "document_ids": self.document_ids},
            name=name,
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")
                return
            answers[name] += 1
            if response.json().get("cached"):
                cache_hits[name] += 1

    @task(6)
    def ask_common_question(self):
        self._ask(random.choice(COMMON_QUESTIONS), "chat: common question")

    @task(3)
    def ask_new_question(self):
        self._ask(f"What does the policy say about case {uuid.uuid4().hex[:8]}?", "chat: new question")

    @task(1)
    def list_documents(self):
        self.client.get("/documents/", name="documents: list")
