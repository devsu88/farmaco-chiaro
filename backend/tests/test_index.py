import json

import pytest

from aifa_rag.store import VectorStore


def write_chunks(path, rows):
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def row(chunk_id, drug_id="1", testo="dose"):
    return {"chunk_id": chunk_id, "drug_id": drug_id, "nome": "X", "testo": testo}


def build(tmp_path, monkeypatch, chunks, embeddings):
    import aifa_rag.index as idx

    monkeypatch.setattr(
        idx, "embed_texts", lambda texts, batch_size=32: embeddings[: len(texts)]
    )
    return idx.build_index(chunks, tmp_path / "embeddings", str(tmp_path / "qdrant"))


def test_build_index_writes_qdrant_points(tmp_path, monkeypatch):
    chunks = tmp_path / "chunks.jsonl"
    write_chunks(
        chunks,
        [
            row("a", "1", "dose adulti"),
            {**row("b", "2", "allergia"), "principi_attivi": ["PARACETAMOLO"], "pagina": 2},
        ],
    )

    n = build(tmp_path, monkeypatch, chunks, [[3.0, 4.0], [1.0, 0.0]])

    assert n == 2
    store = VectorStore.open(str(tmp_path / "qdrant"))
    try:
        assert store.count() == 2
        hits = store.search([1.0, 0.0], k=1)
    finally:
        store.close()

    assert hits[0]["chunk_id"] == "b"
    assert hits[0]["testo"] == "allergia"
    assert hits[0]["drug_id"] == "2"
    assert hits[0]["principi_attivi"] == ["PARACETAMOLO"]
    assert hits[0]["pagina"] == 2


def test_search_applies_filters(tmp_path, monkeypatch):
    chunks = tmp_path / "chunks.jsonl"
    write_chunks(chunks, [row("a", "1", "dose"), row("b", "2", "allergia")])
    build(tmp_path, monkeypatch, chunks, [[1.0, 0.0], [1.0, 0.0]])

    store = VectorStore.open(str(tmp_path / "qdrant"))
    try:
        assert {hit["chunk_id"] for hit in store.search([1.0, 0.0], k=2)} == {"a", "b"}
        assert [
            hit["chunk_id"] for hit in store.search([1.0, 0.0], k=2, filters={"drug_id": "2"})
        ] == ["b"]
    finally:
        store.close()


def test_build_index_resumes_embeddings(tmp_path, monkeypatch):
    import aifa_rag.index as idx

    chunks = tmp_path / "chunks.jsonl"
    write_chunks(chunks, [row("a"), row("b")])

    calls = []

    def fake_embed(texts, batch_size=32):
        calls.append(list(texts))
        return [[1.0, 0.0]] * len(texts)

    monkeypatch.setattr(idx, "embed_texts", fake_embed)

    idx.build_index(chunks, tmp_path / "embeddings", str(tmp_path / "qdrant"))
    assert len(calls) == 1

    write_chunks(chunks, [row("a"), row("b"), row("c")])
    assert idx.build_index(chunks, tmp_path / "embeddings", str(tmp_path / "qdrant")) == 3

    assert len(calls) == 2
    assert len(calls[1]) == 1

    store = VectorStore.open(str(tmp_path / "qdrant"))
    try:
        assert store.count() == 3
    finally:
        store.close()


def test_build_index_reuses_vectors_when_chunks_are_reordered(tmp_path, monkeypatch):
    import aifa_rag.index as idx

    chunks = tmp_path / "chunks.jsonl"
    write_chunks(chunks, [row("a"), row("b")])

    calls = []

    def fake_embed(texts, batch_size=32):
        calls.append(list(texts))
        return [[1.0, 0.0]] * len(texts)

    monkeypatch.setattr(idx, "embed_texts", fake_embed)

    idx.build_index(chunks, tmp_path / "embeddings", str(tmp_path / "qdrant"))
    write_chunks(chunks, [row("b"), row("a")])
    idx.build_index(chunks, tmp_path / "embeddings", str(tmp_path / "qdrant"))

    assert len(calls) == 1


def test_build_index_reuses_cache_after_dedupe_filter(tmp_path, monkeypatch):
    import aifa_rag.index as idx

    chunks = tmp_path / "chunks.jsonl"
    write_chunks(chunks, [row("a"), row("b"), row("c")])

    calls = []

    def fake_embed(texts, batch_size=32):
        calls.append(list(texts))
        return [[1.0, 0.0]] * len(texts)

    monkeypatch.setattr(idx, "embed_texts", fake_embed)

    idx.build_index(chunks, tmp_path / "embeddings", str(tmp_path / "qdrant"))
    write_chunks(chunks, [row("a"), row("c")])
    n = idx.build_index(chunks, tmp_path / "embeddings", str(tmp_path / "qdrant"))

    assert n == 2
    assert len(calls) == 1
    store = VectorStore.open(str(tmp_path / "qdrant"))
    try:
        assert store.count() == 2
    finally:
        store.close()


def test_missing_api_key_is_reported(tmp_path, monkeypatch):
    import aifa_rag.embeddings as emb
    import aifa_rag.index as idx

    chunks = tmp_path / "chunks.jsonl"
    write_chunks(chunks, [row("a")])
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(emb.config, "BASE_DIR", tmp_path)

    with pytest.raises(emb.EmbeddingError, match="OPENROUTER_API_KEY"):
        idx.build_index(chunks, tmp_path / "embeddings", str(tmp_path / "qdrant"))
