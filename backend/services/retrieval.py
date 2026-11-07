"""Retrieval lessicale sui blocchi dei fogli illustrativi.

Interfaccia pubblica:
- ``cerca(query, farmaco_id, limite)``
- ``cerca_farmaci(query, limite)``
- ``blocchi_per_farmaco(farmaco_id)``

L'implementazione è BM25 semplificato. Per passare a embeddings basterà
sostituire questo modulo dietro la stessa interfaccia.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any

from app import farmaci
from app.config import BLOCCHI_FILE

STOPWORDS = {
    "a", "al", "alla", "alle", "allo", "ai", "agli", "le", "la", "lo", "gli",
    "i", "e", "o", "un", "uno", "una", "di", "da", "del", "della", "delle",
    "dello", "dei", "degli", "in", "con", "su", "per", "tra", "fra", "che",
    "se", "è", "era", "sono", "sì", "no", "mi", "ti", "si", "ci", "vi",
    "posso", "devo", "quale", "come", "quando", "dove", "perché", "perche",
    "il", "questo", "questa", "quello",
    "quella", "cosa", "fare", "prendere", "medicinale", "farmaco",
}

# Boost per intenti frequenti: il testo della domanda può non contenere la
# parola usata dal foglio (es. "incinta" vs "gravidanza"). In quel caso
# premiamo i blocchi il cui titolo di sezione/paragrafo parla dell'argomento.
INTENTI = {
    "gravidanza": [
        "incinta",
        "gravidanza",
        "trimestre",
        "concepimento",
    ],
    "allattamento": [
        "allattamento",
        "allattando",
        "fertilità",
        "fertilita",
    ],
    "bambini": [
        "bambino",
        "bambini",
        "bambina",
        "pediatric",
        "adolescent",
        "anni",
        "peso",
        "kg",
    ],
    "dosaggio": [
        "dose",
        "dosaggio",
        "quante",
        "quanti",
        "compressa",
        "compresse",
        "mg",
        "ogni",
        "ore",
        "giorno",
    ],
    "effetti_indesiderati": [
        "effetti indesiderati",
        "reazioni avverse",
        "effetto collaterale",
    ],
    "alcol": ["alcol", "alcool", "alcolismo"],
}

BOOST_INTENTO = 4.0

_blocchi_cache: list[dict[str, Any]] | None = None


def _load_blocchi() -> list[dict[str, Any]]:
    global _blocchi_cache
    if _blocchi_cache is None:
        if BLOCCHI_FILE.exists():
            _blocchi_cache = json.loads(BLOCCHI_FILE.read_text(encoding="utf-8"))
        else:
            _blocchi_cache = []
    return _blocchi_cache


def blocchi_per_farmaco(farmaco_id: str) -> list[dict[str, Any]]:
    return [b for b in _load_blocchi() if b["farmaco_id"] == farmaco_id]


def tokenizza(query: str) -> list[str]:
    termini = re.findall(r"[a-zA-ZÀ-ÿ0-9]+", query.lower())
    termini = [t for t in termini if len(t) > 2 and t not in STOPWORDS]
    return termini or [query.lower()]


def _intenti(query: str) -> list[str]:
    query_lower = query.lower()
    return [
        intento
        for intento, chiavi in INTENTI.items()
        if any(chiave in query_lower for chiave in chiavi)
    ]


def _score(
    query: str,
    termini: list[str],
    blocchi: list[dict[str, Any]],
    query_intento: str | None = None,
) -> list[tuple[float, dict[str, Any]]]:
    if not blocchi:
        return []

    intenti = _intenti(query_intento or query)
    n_docs = len(blocchi)
    idf: dict[str, float] = {}
    for termine in termini:
        df = sum(1 for b in blocchi if termine in b["testo"].lower())
        idf[termine] = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))

    query_lower = query.lower().strip()
    scored: list[tuple[float, dict[str, Any]]] = []
    for blocco in blocchi:
        testo_lower = blocco["testo"].lower()
        punteggio = 0.0
        for termine in termini:
            occorrenze = testo_lower.count(termine)
            if occorrenze:
                punteggio += idf[termine] * (occorrenze / (occorrenze + 1.2))
        if query_lower and query_lower in testo_lower:
            punteggio += 5.0

        if intenti:
            etichetta = f"{blocco['sezione']} {blocco['paragrafo']}".lower()
            for intento in intenti:
                if any(chiave in etichetta for chiave in INTENTI[intento]):
                    punteggio += BOOST_INTENTO
                    # "Gravidanza – ultimo trimestre" è più specifico di
                    # "Gravidanza, allattamento e fertilità".
                    if "trimestre" in etichetta:
                        punteggio += 2.0
                    if "non prenda" in etichetta:
                        punteggio += 1.0

        if punteggio > 0:
            scored.append((punteggio, blocco))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def cerca(
    query: str,
    farmaco_id: str,
    limite: int = 5,
    query_intento: str | None = None,
) -> list[dict[str, Any]]:
    """Restituisce i blocchi più pertinenti per un farmaco.

    ``query_intento`` permette di calcolare i boost di intento sulla domanda
    originale, anche quando la query usata per il matching è stata espansa.
    """
    blocchi = blocchi_per_farmaco(farmaco_id)
    scored = _score(query, tokenizza(query), blocchi, query_intento=query_intento)

    risultati: list[dict[str, Any]] = []
    for punteggio, blocco in scored[:limite]:
        risultati.append(
            {
                "blocco_id": blocco["id"],
                "sezione": blocco["sezione"],
                "paragrafo": blocco["paragrafo"],
                "documento": blocco["documento"],
                "testo": blocco["testo"],
                "score": round(punteggio, 4),
            }
        )
    return risultati


def cerca_farmaci(query: str, limite: int = 10) -> list[dict[str, Any]]:
    """Cerca su tutti i farmaci e aggrega i punteggi per farmaco."""
    if not query.strip():
        return []

    termini = tokenizza(query)
    punteggi: dict[str, float] = {}
    for blocco in _load_blocchi():
        farmaco_id = blocco["farmaco_id"]
        # Valutiamo ogni blocco contro i termini della query.
        testo_lower = blocco["testo"].lower()
        punteggio = 0.0
        for termine in termini:
            if termine in testo_lower:
                punteggio += 1.0 + math.log(1 + testo_lower.count(termine))
        if punteggio > 0:
            punteggi[farmaco_id] = punteggi.get(farmaco_id, 0.0) + punteggio

    risultati: list[dict[str, Any]] = []
    for farmaco_id, punteggio in sorted(punteggi.items(), key=lambda x: x[1], reverse=True):
        farmaco = farmaci.get(farmaco_id)
        risultati.append(
            {
                "id": farmaco_id,
                "nome": farmaco.nome if farmaco else farmaco_id,
                "principio_attivo": farmaco.principio_attivo if farmaco else "",
                "score": round(punteggio, 2),
                "motivo": "Corrispondenza nei testi del foglio illustrativo",
            }
        )
    return risultati[:limite]


def trova_blocco(blocco_id: str) -> dict[str, Any] | None:
    for blocco in _load_blocchi():
        if blocco["id"] == blocco_id:
            return blocco
    return None


def trova_blocco_per_offset(
    farmaco_id: str, offset_inizio: int, offset_fine: int
) -> dict[str, Any] | None:
    for blocco in _load_blocchi():
        if (
            blocco["farmaco_id"] == farmaco_id
            and blocco["offset_inizio"] <= offset_inizio
            and blocco["offset_fine"] >= offset_fine
        ):
            return blocco
    return None


def reset_cache() -> None:
    """Utile nei test quando l'indice viene rigenerato."""
    global _blocchi_cache
    _blocchi_cache = None
