from app.services import embeddings
from app.services.embeddings import MAX_TEXTS_PER_REQUEST, MAX_TOKENS_PER_REQUEST, embed_texts

from tests.conftest import fake_embedding


def test_long_documents_are_split_into_requests_voyage_accepts(fake_voyage):
    texts = [f"Sentence number {i}." for i in range(2500)]

    vectors = embed_texts(texts)

    assert [len(call) for call in fake_voyage.calls] == [1000, 1000, 500]
    assert all(len(call) <= MAX_TEXTS_PER_REQUEST for call in fake_voyage.calls)
    # One vector per text, in the original order.
    assert vectors == [fake_embedding(t) for t in texts]


def test_batches_also_respect_the_token_budget(fake_voyage):
    # Each text is estimated at just over half the per-request budget, so no
    # two fit in one request even though there are far fewer than 1,000.
    long_text = "word " * (MAX_TOKENS_PER_REQUEST * 3 // 10)
    texts = [long_text + str(i) for i in range(5)]

    embed_texts(texts)

    for call in fake_voyage.calls:
        assert sum(embeddings._estimated_tokens(t) for t in call) <= MAX_TOKENS_PER_REQUEST
    assert sum(len(call) for call in fake_voyage.calls) == 5


def test_a_single_huge_text_is_still_sent(fake_voyage):
    huge = "x" * (MAX_TOKENS_PER_REQUEST * 4)
    embed_texts(["small", huge, "small again"])
    assert sum(len(call) for call in fake_voyage.calls) == 3


def test_short_input_is_one_request(fake_voyage):
    embed_texts(["one", "two", "three"])
    assert len(fake_voyage.calls) == 1

