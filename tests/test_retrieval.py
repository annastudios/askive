import uuid

from app.services import retrieval
from app.services.retrieval import BM25Index, reciprocal_rank_fusion, tokenize

from tests.conftest import fake_embedding


def make_index(*docs: tuple[str, str]) -> BM25Index:
    """docs are (document_id, text) pairs; chunk ids are c0, c1, ..."""
    return BM25Index(
        ids=[f"c{i}" for i in range(len(docs))],
        documents=[text for _, text in docs],
        metadatas=[{"document_id": doc_id} for doc_id, _ in docs],
    )


def test_tokenize_drops_stopwords_and_punctuation():
    assert tokenize("What is the ERR_4521 error?") == ["err_4521", "error"]


def test_bm25_ranks_exact_term_matches_first():
    index = make_index(
        ("d1", "The printer shows a paper jam warning."),
        ("d1", "Error ERR_4521 means the toner cartridge is missing."),
        ("d1", "Restart the printer to clear most errors."),
    )
    assert index.search("ERR_4521", top_k=3) == ["c1"]


def test_bm25_rare_terms_outweigh_common_ones():
    index = make_index(
        ("d1", "printer printer printer setup"),
        ("d1", "printer firmware update"),
    )
    assert index.search("printer firmware", top_k=2)[0] == "c1"


def test_bm25_filters_by_document():
    index = make_index(("d1", "refund policy"), ("d2", "refund policy"))
    assert index.search("refund", top_k=5, document_ids=["d2"]) == ["c1"]


def test_bm25_no_matching_terms():
    index = make_index(("d1", "refund policy"))
    assert index.search("penguins", top_k=5) == []


def test_rrf_rewards_agreement_between_lists():
    fused = reciprocal_rank_fusion([["a", "b"], ["c", "b"]])
    # b is only 2nd in each list, but appearing in both beats being 1st in just one.
    assert fused == ["b", "a", "c"] or fused == ["b", "c", "a"]


def store(text_chunks: list[str]) -> str:
    doc_id = str(uuid.uuid4())
    retrieval.store_chunks(doc_id, text_chunks, [fake_embedding(c) for c in text_chunks])
    return doc_id


def test_hybrid_search_finds_keyword_hit_semantic_search_missed(monkeypatch):
    doc_id = store([
        "Shipping takes five business days.",
        "Error ERR_4521 means the toner cartridge is missing.",
    ])
    # Simulate embeddings that blur the error code and only surface the shipping chunk.
    monkeypatch.setattr(retrieval, "semantic_search", lambda *a, **k: [f"{doc_id}-0"])

    results = retrieval.search("ERR_4521", fake_embedding("ERR_4521"), top_k=2, document_ids=[doc_id])

    assert "Error ERR_4521 means the toner cartridge is missing." in results


def test_keyword_index_picks_up_new_uploads():
    store(["Alpacas hum when they are curious."])
    doc_id = store(["Narwhal tusks are actually teeth."])
    assert retrieval.keyword_search("narwhal", top_k=5, document_ids=[doc_id]) == [f"{doc_id}-0"]
