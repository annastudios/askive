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


def test_chunk_text_splits_on_topic_change_once_chunks_are_paragraph_sized():
    cats = " ".join(f"Cats are small quiet pets number {i}." for i in range(14))      # ~480 chars
    rockets = " ".join(f"Rockets launch into orbit from pad {i}." for i in range(14))
    chunks = chunk_text(f"{cats} {rockets}")
    assert len(chunks) == 2
    assert chunks[0].startswith("Cats") and "Rockets" not in chunks[0]
    assert chunks[1].startswith("Rockets")


def test_short_document_stays_one_chunk_despite_topic_changes():
    # Used to become one chunk per sentence.
    text = "Cats are small pets. Rockets launch into orbit. Bread needs yeast. Rain falls in spring."
    assert chunk_text(text) == [text]


def test_chunks_never_exceed_the_maximum():
    from app.services.chunking import MAX_CHUNK_CHARS

    text = " ".join(f"The refund policy covers item {i} for thirty days." for i in range(120))
    chunks = chunk_text(text)
    assert len(chunks) > 1
    assert all(len(c) <= MAX_CHUNK_CHARS for c in chunks)
    assert " ".join(chunks) == text  # nothing lost or duplicated


def test_short_leftover_joins_the_previous_chunk():
    from app.services.chunking import MIN_CHUNK_CHARS

    cats = " ".join(f"Cats are small quiet pets number {i}." for i in range(14))
    chunks = chunk_text(f"{cats} Rockets launch.")
    assert len(chunks) == 1
    assert chunks[0].endswith("Rockets launch.")
    assert len(chunks[0]) > MIN_CHUNK_CHARS


def test_chunk_text_empty():
    assert chunk_text("") == []


def test_search_query_uses_previous_question():
    assert memory.build_search_query("s1", "What about refunds?") == "What about refunds?"
    memory.add_turn("s1", "What is the shipping policy?", "Free over $50.")
    assert (
        memory.build_search_query("s1", "What about refunds?")
        == "What is the shipping policy? What about refunds?"
    )
