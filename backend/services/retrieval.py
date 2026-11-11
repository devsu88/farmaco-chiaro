"""Retrieval ibrido sui fogli illustrativi.

Interfaccia pubblica:
- ``cerca(query, farmaco_id, limite)``
- ``cerca_farmaci(query, limite)``
- ``blocchi_per_farmaco(farmaco_id)``
- ``trova_blocco(blocco_id)``

BM25 in-process sui chunk + ricerca densa su Qdrant, fusi con Reciprocal
Rank Fusion. Se Qdrant o l'embedding falliscono, resta il BM25.
"""
from __future__ import annotations

import json
import logging
import math
import re
from typing import Any

from app import farmaci
from app.config import CHUNKS_FILE, DOCUMENTO_FILE, RETRIEVAL_MODE

logger = logging.getLogger(__name__)

RRF_K = 60
BM25_K1 = 1.2
TITLE_BOOST = 0.6
PHRASE_BOOST = 5.0

STOPWORDS = {
    "a", "al", "alla", "alle", "allo", "ai", "agli", "le", "la", "lo", "gli",
    "i", "e", "o", "un", "uno", "una", "di", "da", "del", "della", "delle",
    "dello", "dei", "degli", "in", "con", "su", "per", "tra", "fra", "che",
    "se", "è", "era", "sono", "sì", "no", "mi", "ti", "si", "ci", "vi",
    "posso", "devo", "quale", "come", "quando", "dove", "perché", "perche",
    "il", "questo", "questa", "quello", "quella", "cosa", "fare", "prendere",
    "medicinale", "farmaco", "foglietto", "illustrativo",
}

# Sinonimi clinici: il paziente dice "cuore", il foglio dice "cardiaco".
SINONIMI = {
    "cuore": ["cardiaco", "cardiaca", "cardiaci", "cardiache", "cardiopatia", "aritmia", "infarto", "ictus"],
    "stomaco": ["addominale", "gastrico", "gastrica", "gastrointestinale", "nausea", "vomito"],
    "fegato": ["epatico", "epatica", "epatite"],
    "reni": ["renale", "renali"],
    "pressione": ["ipertensione", "ipotensione"],
    "mal di testa": ["cefalea", "emicrania"],
    "denti": ["dente", "dentale", "dentali", "odontoiatrico"],
    "alcol": ["alcool", "alcolismo"],
    "incinta": ["gravidanza", "gestazione", "trimestre"],
    "gravidanza": ["incinta", "gestazione", "trimestre"],
    "allatta": ["allattamento", "allattare", "lattazione"],
    "bambino": ["bambini", "pediatrico", "pediatrica", "adolescente"],
    "sangue": ["emorragia", "sanguinamento", "piastrine"],
}

_chunks: list[dict[str, Any]] | None = None
_chunk_by_id: dict[str, dict[str, Any]] = {}
_blocchi: dict[str, dict[str, Any]] = {}
_blocchi_per_farmaco: dict[str, list[dict[str, Any]]] = {}


def _load() -> None:
    global _chunks, _chunk_by_id, _blocchi, _blocchi_per_farmaco
    if _chunks is not None:
        return

    chunks: list[dict[str, Any]] = []
    if CHUNKS_FILE.exists():
        chunks = [
            json.loads(line)
            for line in CHUNKS_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    blocchi: dict[str, dict[str, Any]] = {}
    per_farmaco: dict[str, list[dict[str, Any]]] = {}
    if DOCUMENTO_FILE.exists():
        for line in DOCUMENTO_FILE.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            blocchi[row["blocco_id"]] = row
            per_farmaco.setdefault(row["farmaco_id"], []).append(row)

    _chunks = chunks
    _chunk_by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
    _blocchi = blocchi
    _blocchi_per_farmaco = per_farmaco


def blocchi_per_farmaco(farmaco_id: str) -> list[dict[str, Any]]:
    _load()
    return list(_blocchi_per_farmaco.get(farmaco_id, []))


def trova_blocco(blocco_id: str) -> dict[str, Any] | None:
    _load()
    return _blocchi.get(blocco_id)


def _chunks_per_farmaco(farmaco_id: str) -> list[dict[str, Any]]:
    _load()
    return [chunk for chunk in _chunks or [] if chunk.get("farmaco_id") == farmaco_id]


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


def _idf(termini: list[str], documenti: list[dict[str, Any]], campo: str = "testo") -> dict[str, float]:
    n_docs = len(documenti) or 1
    valori: dict[str, float] = {}
    for termine in termini:
        df = sum(1 for doc in documenti if termine in str(doc.get(campo, "")).lower())
        valori[termine] = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
    return valori


def _score_bm25(
    query: str,
    termini: list[str],
    documenti: list[dict[str, Any]],
) -> list[tuple[float, dict[str, Any]]]:
    if not documenti:
        return []

    idf = _idf(termini, documenti)
    query_lower = query.lower().strip()
    scored: list[tuple[float, dict[str, Any]]] = []

    for doc in documenti:
        testo = str(doc.get("testo", "")).lower()
        titolo = " ".join(
            str(doc.get(campo, "")) for campo in ("sezione_titolo", "sottosezione_titolo")
        ).lower()
        punteggio = 0.0
        for termine in termini:
            occorrenze = testo.count(termine)
            if occorrenze:
                punteggio += idf[termine] * (
                    occorrenze * (BM25_K1 + 1) / (occorrenze + BM25_K1)
                )
            if termine in titolo:
                punteggio += idf[termine] * TITLE_BOOST
        if query_lower and query_lower in testo:
            punteggio += PHRASE_BOOST
        if punteggio > 0:
            scored.append((punteggio, doc))

    scored.sort(key=lambda item: item[0], reverse=True)
    return scored


def _chunk_to_result(
    chunk: dict[str, Any],
    score_bm25: float = 0.0,
    score_dense: float = 0.0,
) -> dict[str, Any]:
    _load()
    blocco = _blocchi.get(chunk.get("blocco_id", ""), {})
    return {
        "blocco_id": chunk.get("blocco_id", ""),
        "farmaco_id": chunk.get("farmaco_id", ""),
        "documento": blocco.get("documento", ""),
        "sezione": blocco.get("sezione", chunk.get("sezione_titolo", "")),
        "paragrafo": blocco.get("paragrafo", chunk.get("sottosezione_titolo", "")),
        "testo": blocco.get("testo") or chunk.get("testo", ""),
        "chunk_id": chunk.get("chunk_id", ""),
        "chunk": chunk.get("testo", ""),
        "score_bm25": round(score_bm25, 4),
        "score_dense": round(score_dense, 4),
        "score": round(max(score_bm25, score_dense * 10), 4),
    }


def _dedupe_per_blocco(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    visti: dict[str, dict[str, Any]] = {}
    for risultato in results:
        blocco_id = risultato.get("blocco_id")
        if not blocco_id or blocco_id in visti:
            continue
        visti[blocco_id] = risultato
    return list(visti.values())


def _bm25_chunks(
    query: str,
    chunks: list[dict[str, Any]],
    limite: int,
    query_intento: str | None = None,
) -> list[dict[str, Any]]:
    query_espansa = espandi_sinonimi(query_intento or query)
    scored = _score_bm25(query_espansa, tokenizza(query_espansa), chunks)
    risultati = [
        _chunk_to_result(chunk, score_bm25=punteggio)
        for punteggio, chunk in scored[: max(limite * 3, limite)]
    ]
    return _dedupe_per_blocco(risultati)[:limite]


def _fuse_rrf(
    bm25_results: list[dict[str, Any]],
    dense_results: list[dict[str, Any]],
    limite: int,
) -> list[dict[str, Any]]:
    punteggi: dict[str, float] = {}
    per_id: dict[str, dict[str, Any]] = {}

    for rank, risultato in enumerate(bm25_results):
        blocco_id = risultato["blocco_id"]
        punteggi[blocco_id] = punteggi.get(blocco_id, 0.0) + 1.0 / (RRF_K + rank + 1)
        per_id[blocco_id] = dict(risultato)

    for rank, denso in enumerate(dense_results):
        blocco_id = denso["blocco_id"]
        punteggi[blocco_id] = punteggi.get(blocco_id, 0.0) + 1.0 / (RRF_K + rank + 1)
        if blocco_id in per_id:
            per_id[blocco_id]["score_dense"] = round(denso.get("score_dense", 0.0), 4)
            per_id[blocco_id]["chunk_id_dense"] = denso.get("chunk_id", "")
        else:
            per_id[blocco_id] = dict(denso)

    for blocco_id, risultato in per_id.items():
        risultato["score_rrf"] = round(punteggi[blocco_id], 6)
        risultato["score"] = round(
            max(
                risultato.get("score_bm25", 0.0),
                risultato.get("score_dense", 0.0) * 10,
            ),
            4,
        )

    return sorted(per_id.values(), key=lambda item: item["score_rrf"], reverse=True)[:limite]


def _dense_results(
    query: str,
    farmaco_id: str | None,
    limite: int,
) -> list[dict[str, Any]]:
    try:
        from services import vector_store

        hits = vector_store.query_dense(
            query,
            farmaco_id=farmaco_id,
            n_results=max(limite * 3, 30),
        )
    except Exception:
        logger.warning("Retrieval denso non disponibile", exc_info=True)
        return []

    _load()
    risultati: list[dict[str, Any]] = []
    for hit in hits:
        chunk = _chunk_by_id.get(hit.get("chunk_id", ""))
        if chunk is None:
            continue
        risultati.append(
            _chunk_to_result(
                chunk,
                score_dense=float(hit.get("score_dense", 0.0)),
            )
        )
    return _dedupe_per_blocco(risultati)[:limite]


def cerca(
    query: str,
    farmaco_id: str,
    limite: int = 5,
    query_intento: str | None = None,
) -> list[dict[str, Any]]:
    """Restituisce i blocchi più pertinenti per un foglio illustrativo."""
    bm25_results = _bm25_chunks(
        query,
        _chunks_per_farmaco(farmaco_id),
        limite=max(limite, 20),
        query_intento=query_intento or query,
    )

    if RETRIEVAL_MODE != "hybrid":
        return bm25_results[:limite]

    dense_results = _dense_results(query, farmaco_id, limite=max(limite, 20))
    if not dense_results:
        return bm25_results[:limite]
    return _fuse_rrf(bm25_results, dense_results, limite=limite)


def cerca_farmaci(query: str, limite: int = 10) -> list[dict[str, Any]]:
    """Cerca su tutti i fogli e aggrega i punteggi per farmaco."""
    if not query.strip():
        return []

    _load()
    termini = tokenizza(espandi_sinonimi(query))
    idf = _idf(termini, _chunks or [])
    punteggi: dict[str, float] = {}

    for chunk in _chunks or []:
        farmaco_id = chunk.get("farmaco_id", "")
        if not farmaco_id:
            continue
        testo = str(chunk.get("testo", "")).lower()
        titolo = str(chunk.get("foglio", "")).lower()
        punteggio = 0.0
        for termine in termini:
            occorrenze = testo.count(termine)
            if occorrenze:
                punteggio += idf.get(termine, 1.0) * (
                    occorrenze * (BM25_K1 + 1) / (occorrenze + BM25_K1)
                )
            if termine in titolo:
                punteggio += idf.get(termine, 1.0) * 3.0
        if punteggio > 0:
            punteggi[farmaco_id] = punteggi.get(farmaco_id, 0.0) + punteggio

    query_lower = query.lower().strip()
    risultati: list[dict[str, Any]] = []
    for farmaco_id, punteggio in punteggi.items():
        farmaco = farmaci.get(farmaco_id)
        if farmaco is None:
            continue
        nome_lower = farmaco.nome.lower()
        principio_lower = farmaco.principio_attivo.lower()
        motivo = "Corrispondenza nei testi del foglio illustrativo"
        if query_lower and query_lower in nome_lower:
            punteggio += 50.0
            motivo = "Corrispondenza nel nome del farmaco"
        elif query_lower and query_lower in principio_lower:
            punteggio += 30.0
            motivo = "Corrispondenza nel principio attivo"
        risultati.append(
            {
                "id": farmaco_id,
                "nome": farmaco.nome,
                "principio_attivo": farmaco.principio_attivo,
                "score": round(punteggio, 2),
                "motivo": motivo,
            }
        )

    # I farmaci il cui nome/principio corrisponde ma che non hanno chunk nel
    # testo (es. query = "tachipirina") devono comunque comparire.
    if query_lower:
        for farmaco in farmaci.all():
            if farmaco.id in {r["id"] for r in risultati}:
                continue
            if (
                query_lower in farmaco.nome.lower()
                or query_lower in farmaco.principio_attivo.lower()
            ):
                risultati.append(
                    {
                        "id": farmaco.id,
                        "nome": farmaco.nome,
                        "principio_attivo": farmaco.principio_attivo,
                        "score": 20.0,
                        "motivo": "Corrispondenza nel nome del farmaco",
                    }
                )

    risultati.sort(key=lambda item: item["score"], reverse=True)
    return risultati[:limite]


def reset_cache() -> None:
    """Utile nei test quando gli artefatti vengono rigenerati."""
    global _chunks
    _chunks = None
    _chunk_by_id.clear()
    _blocchi.clear()
    _blocchi_per_farmaco.clear()
