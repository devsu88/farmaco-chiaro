"""Valutazione del retrieval: recall@k e MRR su un set di domande."""

from __future__ import annotations

import json
from pathlib import Path

from aifa_rag.query import search


def _hit_fields(hit) -> tuple[str, str | None]:
    if isinstance(hit, dict):
        return str(hit.get("chunk_id", "")), hit.get("sezione_key")
    return str(hit), None


def _matches(hit, expected: dict) -> bool:
    chunk_id, sezione_key = _hit_fields(hit)
    drug = expected.get("expected_drug_id")
    if drug and not chunk_id.startswith(str(drug)):
        return False
    section = expected.get("expected_sezione_key")
    if section and sezione_key is not None and sezione_key != section:
        return False
    tokens = expected.get("must_contain") or []
    if tokens and isinstance(hit, dict):
        testo = str(hit.get("testo", "")).lower()
        if not all(token.lower() in testo for token in tokens):
            return False
    return True


def recall_at_k(results: list[list], expected: list[dict], k: int = 5) -> float:
    if not expected:
        return 0.0
    hits = 0
    for row, exp in zip(results, expected):
        if any(_matches(hit, exp) for hit in row[:k]):
            hits += 1
    return hits / len(expected)


def mrr(results: list[list], expected: list[dict]) -> float:
    if not expected:
        return 0.0
    total = 0.0
    for row, exp in zip(results, expected):
        for rank, hit in enumerate(row, start=1):
            if _matches(hit, exp):
                total += 1.0 / rank
                break
    return total / len(expected)


def load_qa(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def evaluate(index, qa: list[dict], k: int = 5) -> dict:
    results: list[list[dict]] = []
    failures: list[dict] = []

    for item in qa:
        hits = search(index, item["question"], k=k)
        results.append(hits)
        if not any(_matches(hit, item) for hit in hits):
            failures.append(
                {
                    "question": item["question"],
                    "expected_drug_id": item.get("expected_drug_id"),
                    "expected_sezione_key": item.get("expected_sezione_key"),
                    "top": [hit["chunk_id"] for hit in hits],
                }
            )

    return {
        "recall_at_k": recall_at_k(results, qa, k=k),
        "mrr": mrr(results, qa),
        "n": len(qa),
        "k": k,
        "failures": failures,
    }
