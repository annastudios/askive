from app.services import memory
from app.services.chunking import _cosine_similarity, _split_sentences, chunk_text


def test_split_sentences():
    text = "First one. Second one!  Third one?\nFourth."
    assert _split_sentences(text) == ["First one.", "Second one!", "Third one?", "Fourth."]


def test_split_sentences_empty():
    assert _split_sentences("   ") == []


def test_cosine_similarity():
    assert _cosine_similarity([1, 0], [1, 0]) == 1.0
    assert _cosine_similarity([1, 0], [0, 1]) == 0.0
    assert _cosine_similarity([0, 0], [1, 0]) == 0.0


def test_chunk_text_splits_on_topic_change():
    text = (
        "Cats are small pets. Cats are quiet pets. "
        "Rockets launch into orbit. Rockets launch from pads."
    )
    chunks = chunk_text(text)
    assert chunks == [
        "Cats are small pets. Cats are quiet pets.",
        "Rockets launch into orbit. Rockets launch from pads.",
    ]


def test_chunk_text_empty():
    assert chunk_text("") == []


def test_search_query_uses_previous_question():
    assert memory.build_search_query("s1", "What about refunds?") == "What about refunds?"
    memory.add_turn("s1", "What is the shipping policy?", "Free over $50.")
    assert (
        memory.build_search_query("s1", "What about refunds?")
        == "What is the shipping policy? What about refunds?"
    )
