"""Valutazione del retrieval sul golden set (P0.7 del piano di impatto).

Ogni domanda deve avere almeno un blocco atteso nel top 5. Il test fissa una
soglia minima di Recall@5 e MRR, così un peggioramento del retrieval non passa
silenziosamente.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.retrieval import cerca

GOLDEN_FILE = Path(__file__).parent / "data" / "golden_set.json"
GOLDEN = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))["domande"]

RECALL_MINIMO = 0.95
MRR_MINIMO = 0.70


def _rank(domanda: dict) -> int:
    risultati = cerca(domanda["domanda"], domanda["farmaco_id"], limite=5)
    ids = [risultato["blocco_id"] for risultato in risultati]
    for indice, blocco_id in enumerate(ids, start=1):
        if blocco_id in domanda["blocchi_attesi"]:
            return indice
    return 0


@pytest.mark.parametrize("domanda", GOLDEN, ids=[d["id"] for d in GOLDEN])
def test_blocco_atteso_nel_top_5(domanda):
    assert _rank(domanda) > 0, (
        f"Nessun blocco atteso per {domanda['id']} nel top 5: "
        f"{[r['blocco_id'] for r in cerca(domanda['domanda'], domanda['farmaco_id'], limite=5)]}"
    )


def test_metriche_golden_set():
    ranks = [_rank(domanda) for domanda in GOLDEN]
    recall = sum(1 for rank in ranks if rank > 0) / len(ranks)
    mrr = sum(1 / rank for rank in ranks if rank > 0) / len(ranks)

    assert recall >= RECALL_MINIMO, f"Recall@5 {recall:.2f} sotto la soglia"
    assert mrr >= MRR_MINIMO, f"MRR {mrr:.2f} sotto la soglia"
