"""Adapter Qdrant per il retrieval denso.

L'indice vive su Qdrant Cloud (o su un server locale in Docker). Se il
servizio non è raggiungibile o l'embedding fallisce, il chiamante degrada a
BM25: il chatbot non deve smettere di funzionare.
"""
from __future__ import annotations

import logging
import threading
from typing import Any

from qdrant_client import QdrantClient, models

from app.config import QDRANT_API_KEY, QDRANT_COLLECTION, QDRANT_TIMEOUT, QDRANT_URL
from services.embeddings import EmbeddingError, embed_query

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_client: QdrantClient | None = None


def _get_client() -> QdrantClient | None:
    global _client
    if _client is not None:
        return _client
    with _lock:
        if _client is not None:
            return _client
        try:
            _client = QdrantClient(
                url=QDRANT_URL,
                api_key=QDRANT_API_KEY or None,
                timeout=QDRANT_TIMEOUT,
            )
        except Exception:
            logger.warning("Client Qdrant non inizializzabile", exc_info=True)
            return None
        return _client


def is_available() -> bool:
    client = _get_client()
    if client is None:
        return False
    try:
        return client.collection_exists(QDRANT_COLLECTION)
    except Exception:
        logger.warning("Qdrant non raggiungibile", exc_info=True)
        return False


def count() -> int:
    client = _get_client()
    if client is None:
        return 0
    try:
        return int(
            client.count(collection_name=QDRANT_COLLECTION, exact=True).count
        )
    except Exception:
        logger.warning("Impossibile leggere il conteggio Qdrant", exc_info=True)
        return 0


def query_dense(
    query: str,
    farmaco_id: str | None = None,
    n_results: int = 30,
) -> list[dict[str, Any]]:
    """Restituisce i chunk più simili, con i campi del payload."""
    client = _get_client()
    if client is None:
        return []

    try:
        vettore = embed_query(query)
    except EmbeddingError:
        logger.warning("Embedding query fallito, fallback a BM25", exc_info=True)
        return []

    query_filter = None
    if farmaco_id:
        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="farmaco_id", match=models.MatchValue(value=farmaco_id)
                )
            ]
        )

    try:
        points = client.query_points(
            collection_name=QDRANT_COLLECTION,
            query=vettore,
            limit=n_results,
            query_filter=query_filter,
            with_payload=True,
        ).points
    except Exception:
        logger.warning("Query Qdrant fallita, fallback a BM25", exc_info=True)
        return []

    hits: list[dict[str, Any]] = []
    for point in points:
        payload = dict(point.payload or {})
        payload.setdefault("chunk_id", str(point.id))
        payload["score_dense"] = float(point.score)
        hits.append(payload)
    return hits


def reset_client() -> None:
    """Utile nei test o dopo una nuova ingestion."""
    global _client
    with _lock:
        if _client is not None:
            try:
                _client.close()
            except Exception:
                pass
        _client = None
