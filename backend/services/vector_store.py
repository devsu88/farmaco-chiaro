"""Adapter ChromaDB per il retrieval denso.

L'indice è prodotto dallo script ``scripts/ingest_vector_index.py``. Se
l'indice non esiste o l'embedding fallisce, il chiamante deve degradare a
BM25: il chatbot non deve smettere di funzionare.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any

import chromadb
from chromadb.config import Settings

from app.config import INDEX_DIR
from services.embeddings import EmbeddingError, embed_query

logger = logging.getLogger(__name__)

CHROMA_DIR = INDEX_DIR / "chroma"
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "farmaci_blocchi")

_lock = threading.Lock()
_client = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is not None:
        return _collection
    with _lock:
        if _collection is not None:
            return _collection
        if not CHROMA_DIR.exists():
            return None
        try:
            _client = chromadb.PersistentClient(
                path=str(CHROMA_DIR),
                settings=Settings(anonymized_telemetry=False),
            )
            _collection = _client.get_collection(COLLECTION_NAME)
        except Exception:
            logger.warning("Collezione Chroma non disponibile", exc_info=True)
            _collection = None
        return _collection


def is_available() -> bool:
    collection = _get_collection()
    if collection is None:
        return False
    try:
        return collection.count() > 0
    except Exception:
        logger.warning("Impossibile leggere il conteggio Chroma", exc_info=True)
        return False


def count() -> int:
    collection = _get_collection()
    if collection is None:
        return 0
    try:
        return collection.count()
    except Exception:
        return 0


def query_dense(
    query: str,
    farmaco_id: str | None = None,
    n_results: int = 20,
) -> list[dict[str, Any]]:
    """Restituisce i blocchi più simili, deduplicati per blocco padre."""
    collection = _get_collection()
    if collection is None:
        return []

    try:
        vettore = embed_query(query)
    except EmbeddingError:
        logger.warning("Embedding query fallito, fallback a BM25", exc_info=True)
        return []

    where = {"farmaco_id": farmaco_id} if farmaco_id else None
    try:
        with _lock:
            risultato = collection.query(
                query_embeddings=[vettore],
                n_results=n_results,
                where=where,
                include=["metadatas", "distances", "documents"],
            )
    except Exception:
        logger.warning("Query Chroma fallita", exc_info=True)
        return []

    ids = (risultato.get("ids") or [[]])[0]
    metadati = (risultato.get("metadatas") or [[]])[0]
    distanze = (risultato.get("distances") or [[]])[0]
    documenti = (risultato.get("documents") or [[]])[0]

    migliori: dict[str, dict[str, Any]] = {}
    for chunk_id, meta, distanza, documento in zip(ids, metadati, distanze, documenti):
        meta = meta or {}
        blocco_id = str(meta.get("blocco_id", ""))
        if not blocco_id:
            continue
        similarita = max(0.0, 1.0 - float(distanza))
        esistente = migliori.get(blocco_id)
        if esistente and esistente["score_dense"] >= similarita:
            continue
        migliori[blocco_id] = {
            "blocco_id": blocco_id,
            "farmaco_id": meta.get("farmaco_id", ""),
            "sezione": meta.get("sezione", ""),
            "paragrafo": meta.get("paragrafo", ""),
            "documento": meta.get("documento", ""),
            "chunk_id": chunk_id,
            "chunk": documento or "",
            "score_dense": similarita,
        }

    return sorted(
        migliori.values(),
        key=lambda item: item["score_dense"],
        reverse=True,
    )


def reset_client() -> None:
    """Utile nei test o dopo una nuova ingestion."""
    global _client, _collection
    with _lock:
        _client = None
        _collection = None
