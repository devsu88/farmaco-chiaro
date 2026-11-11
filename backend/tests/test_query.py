from aifa_rag.query import format_result, search


def test_format_result_contains_citation():
    r = {
        "drug_id": "012745",
        "nome": "TACHIPIRINA",
        "sezione_titolo": "Come prendere Tachipirina",
        "score": 0.91,
        "testo": "1 compressa fino a 3 volte al giorno",
        "source_url": "https://x",
        "pagina": 3,
    }
    out = format_result(r)
    assert "TACHIPIRINA" in out
    assert "Come prendere" in out
    assert "https://x" in out
    assert "pag. 3" in out


def test_format_result_uses_heading_path_when_present():
    r = {
        "nome": "PLASIL",
        "heading_path": "PLASIL > Come prendere > Dose",
        "score": 0.8,
        "testo": "1 mg",
        "source_url": "u",
        "pagina": 2,
    }
    assert "PLASIL > Come prendere > Dose" in format_result(r)


class FakeIndex:
    def __init__(self):
        self.calls = []

    def search(self, query_vector, k=5, filters=None):
        self.calls.append({"vector": query_vector, "k": k, "filters": filters})
        return [
            {
                "chunk_id": "012745_01_3_00_come_prendere_00_00",
                "score": 0.75,
                "drug_id": "012745",
                "sezione_key": "posologia",
                "testo": "1 compressa",
            }
        ]


def test_search_embeds_and_delegates_to_index(monkeypatch):
    import aifa_rag.query as q

    monkeypatch.setattr(q, "embed_texts", lambda texts: [[1.0, 0.0]])
    index = FakeIndex()

    hits = search(index, "dose", k=3, filters={"drug_id": "012745"})

    assert index.calls == [{"vector": [1.0, 0.0], "k": 3, "filters": {"drug_id": "012745"}}]
    assert hits[0]["score"] == 0.75
    assert hits[0]["drug_id"] == "012745"
