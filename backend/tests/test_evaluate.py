from aifa_rag.evaluate import evaluate, mrr, recall_at_k


def test_recall_and_mrr():
    results = [["a", "b"], ["c", "d"]]
    expected = [{"expected_drug_id": "a"}, {"expected_drug_id": "x"}]
    assert recall_at_k(results, expected, k=2) == 0.5
    assert mrr(results, expected) == 0.5


def test_mrr_uses_first_hit_rank():
    results = [["x", "a"], ["a"]]
    expected = [{"expected_drug_id": "a"}, {"expected_drug_id": "a"}]
    assert recall_at_k(results, expected, k=2) == 1.0
    assert mrr(results, expected) == 0.75


def test_metadata_hits_are_supported():
    results = [
        [{"chunk_id": "012745_01_3_00_come_prendere_00_00", "sezione_key": "posologia"}],
    ]
    expected = [{"expected_drug_id": "012745", "expected_sezione_key": "posologia"}]
    assert recall_at_k(results, expected, k=1) == 1.0
    assert mrr(results, expected) == 1.0


def test_evaluate_reports_failures(monkeypatch):
    import aifa_rag.evaluate as ev

    hits = {
        "dose?": [
            {"chunk_id": "012745_01_3_00_come_prendere_00_00", "sezione_key": "posologia",
             "testo": "1 compressa"},
        ],
        "allergia?": [
            {"chunk_id": "099999_01_2_00_non_prenda_00_00", "sezione_key": "avvertenze_e_controindicazioni",
             "testo": "allergia"},
        ],
    }
    monkeypatch.setattr(ev, "search", lambda collection, query, k=5: hits[query])

    qa = [
        {"question": "dose?", "expected_drug_id": "012745", "expected_sezione_key": "posologia"},
        {"question": "allergia?", "expected_drug_id": "012745"},
    ]
    report = evaluate(index=None, qa=qa, k=5)

    assert report["recall_at_k"] == 0.5
    assert report["mrr"] == 0.5
    assert len(report["failures"]) == 1
    assert report["failures"][0]["question"] == "allergia?"


def test_must_contain_marks_partial_answer_as_failure(monkeypatch):
    import aifa_rag.evaluate as ev

    monkeypatch.setattr(
        ev,
        "search",
        lambda collection, query, k=5: [
            {"chunk_id": "012745_01_1_00_body_00_00", "sezione_key": "indicazioni", "testo": "febbre"}
        ],
    )
    qa = [
        {
            "question": "a cosa serve?",
            "expected_drug_id": "012745",
            "expected_sezione_key": "indicazioni",
            "must_contain": ["paracetamolo"],
        }
    ]
    report = evaluate(index=None, qa=qa, k=5)
    assert report["recall_at_k"] == 0.0
    assert len(report["failures"]) == 1