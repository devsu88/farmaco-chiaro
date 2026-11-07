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
import os
import re
from typing import Any

from app import farmaci
from app.config import BLOCCHI_FILE

RETRIEVAL_MODE = os.getenv("RETRIEVAL_MODE", "hybrid").strip().lower()
RRF_K = 60

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
        "giorno",
    ],
    "effetti_indesiderati": [
        "effetti indesiderati",
        "reazioni avverse",
        "effetto collaterale",
    ],
    "alcol": ["alcol", "alcool", "alcolismo"],
    "cuore": [
        "cuore",
        "cardiac",
        "cardiopat",
        "aritmia",
        "infarto",
        "ictus",
        "ipertensione",
    ],
    "stomaco": [
        "stomaco",
        "addominal",
        "gastric",
        "gastrointestinal",
        "nausea",
        "vomito",
    ],
    "indicazioni": [
        "mal di",
        "dolore",
        "serve per",
        "indicato per",
        "infezione",
        "infezioni",
        "che cos",
        "a cosa serve",
        "indicazioni terapeutiche",
    ],
    "denti": [
        "dente",
        "denti",
        "dentale",
        "dentali",
        "odontoiatric",
        "ascesso",
    ],
}

# Sinonimi clinici ricorrenti: il paziente dice "cuore", il foglio dice
# "cardiaco"; il paziente dice "mal di stomaco", il foglio "dolore addominale".
SINONIMI = {
    "cuore": ["cardiaco", "cardiaca", "cardiaci", "cardiache", "cardiopatia", "aritmia", "infarto", "ictus"],
    "stomaco": ["addominale", "gastrico", "gastrica", "gastrointestinale", "nausea", "vomito"],
    "fegato": ["epatico", "epatica", "epatite"],
    "reni": ["renale", "renali"],
    "pressione": ["ipertensione", "ipotensione"],
    "mal di testa": ["cefalea", "emicrania"],
    "denti": ["dente", "dentale", "dentali", "odontoiatrico"],
}

# Intenti che si riconoscono da frasi presenti nel corpo del blocco, non dal
# titolo. Esempio: "posso darlo a un parente?" -> il foglio usa la frase
# "Non lo dia ad altre persone".
INTENTI_TESTO = {
    "condivisione": {
        "query": [
            "parente",
            "familiare",
            "amico",
            "amica",
            "sorella",
            "fratello",
            "madre",
            "padre",
            "figlio",
            "figlia",
            "moglie",
            "marito",
            "nonna",
            "nonno",
            "zia",
            "zio",
            "cugino",
            "cugina",
            "altra persona",
            "altre persone",
            "condividere",
            "prestare",
            "stesso problema",
            "sintomi uguali",
            "stessa malattia",
            "darlo a",
            "dargli",
            "darle",
        ],
        "frasi": [
            "non lo dia ad altre persone",
            "soltanto per lei",
            "sintomi della malattia sono uguali",
        ],
    },
}

BOOST_INTENTO = 4.0
BOOST_FRASE = 10.0

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


def espandi_sinonimi(query: str) -> str:
    query_lower = query.lower()
    extra: list[str] = []
    for chiave, sinonimi in SINONIMI.items():
        if chiave in query_lower:
            extra.extend(s for s in sinonimi if s not in query_lower)
    return f"{query} {' '.join(extra)}".strip() if extra else query


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


def _intenti_testo(query: str) -> list[str]:
    query_lower = query.lower()
    return [
        intento
        for intento, configurazione in INTENTI_TESTO.items()
        if any(chiave in query_lower for chiave in configurazione["query"])
    ]


def _score(
    query: str,
    termini: list[str],
    blocchi: list[dict[str, Any]],
    query_intento: str | None = None,
) -> list[tuple[float, dict[str, Any]]]:
    if not blocchi:
        return []

    query_riferimento = query_intento or query
    intenti = _intenti(query_riferimento)
    intenti_testo = _intenti_testo(query_riferimento)
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

        if intenti_testo:
            for intento in intenti_testo:
                frasi = INTENTI_TESTO[intento]["frasi"]
                if any(frase in testo_lower for frase in frasi):
                    punteggio += BOOST_FRASE

        if punteggio > 0:
            scored.append((punteggio, blocco))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def _block_to_result(
    blocco: dict[str, Any],
    score_bm25: float = 0.0,
    score_dense: float = 0.0,
) -> dict[str, Any]:
    return {
        "blocco_id": blocco["id"],
        "sezione": blocco["sezione"],
        "paragrafo": blocco["paragrafo"],
        "documento": blocco["documento"],
        "testo": blocco["testo"],
        "score": round(max(score_bm25, score_dense * 10), 4),
        "score_bm25": round(score_bm25, 4),
        "score_dense": round(score_dense, 4),
    }


def _bm25_results(
    query: str,
    farmaco_id: str,
    limite: int,
    query_intento: str | None = None,
) -> list[dict[str, Any]]:
    blocchi = blocchi_per_farmaco(farmaco_id)
    query_match = espandi_sinonimi(query)
    scored = _score(
        query_match,
        tokenizza(query_match),
        blocchi,
        query_intento=query_intento or query,
    )
    return [
        _block_to_result(blocco, score_bm25=punteggio)
        for punteggio, blocco in scored[:limite]
    ]


def _fuse_rrf(
    bm25_results: list[dict[str, Any]],
    dense_results: list[dict[str, Any]],
    limite: int,
) -> list[dict[str, Any]]:
    punteggi: dict[str, float] = {}
    per_id: dict[str, dict[str, Any]] = {}

    for rank, risultato in enumerate(bm25_results):
        blocco_id = risultato["blocco_id"]
        punteggi[blocco_id] = punteggi.get(blocco_id, 0.0) + 1.0 / (
            RRF_K + rank + 1
        )
        per_id[blocco_id] = {**risultato}

    for rank, denso in enumerate(dense_results):
        blocco_id = denso["blocco_id"]
        punteggi[blocco_id] = punteggi.get(blocco_id, 0.0) + 1.0 / (
            RRF_K + rank + 1
        )
        if blocco_id in per_id:
            per_id[blocco_id]["score_dense"] = round(denso["score_dense"], 4)
        else:
            blocco = trova_blocco(blocco_id)
            if blocco is None:
                continue
            per_id[blocco_id] = _block_to_result(
                blocco,
                score_dense=denso["score_dense"],
            )

    for blocco_id, risultato in per_id.items():
        risultato["score_rrf"] = round(punteggi[blocco_id], 6)
        risultato["score"] = round(
            max(risultato.get("score_bm25", 0.0), risultato.get("score_dense", 0.0) * 10),
            4,
        )

    return sorted(
        per_id.values(),
        key=lambda item: item["score_rrf"],
        reverse=True,
    )[:limite]


def cerca(
    query: str,
    farmaco_id: str,
    limite: int = 5,
    query_intento: str | None = None,
) -> list[dict[str, Any]]:
    """Restituisce i blocchi più pertinenti per un farmaco.

    Usa BM25 + ChromaDB con fusione RRF. Se Chroma non è disponibile o
    l'embedding fallisce, restituisce il risultato BM25 senza errori.
    """
    bm25_results = _bm25_results(
        query,
        farmaco_id,
        limite=max(limite, 20),
        query_intento=query_intento or query,
    )
    if RETRIEVAL_MODE != "hybrid":
        return bm25_results[:limite]

    try:
        from services import vector_store

        densi = vector_store.query_dense(
            query,
            farmaco_id=farmaco_id,
            n_results=max(limite, 20),
        )
    except Exception:
        densi = []

    if not densi:
        return bm25_results[:limite]
    return _fuse_rrf(bm25_results, densi, limite=limite)


def cerca_farmaci(query: str, limite: int = 10) -> list[dict[str, Any]]:
    """Cerca su tutti i farmaci e aggrega i punteggi per farmaco."""
    if not query.strip():
        return []

    termini = tokenizza(espandi_sinonimi(query))
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
