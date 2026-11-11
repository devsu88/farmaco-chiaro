"""Embedding delle query via OpenRouter.

La pipeline di indicizzazione vive in ``aifa_rag.embeddings``; qui esponiamo
solo l'operazione usata a runtime, con cache in memoria per le domande ripetute.
"""
from __future__ import annotations

from functools import lru_cache

from aifa_rag.config import EMBEDDING_MODEL
from aifa_rag.embeddings import EmbeddingError, embed_texts

__all__ = [
    "EMBEDDING_MODEL",
    "EmbeddingError",
    "embed_query",
    "embed_texts",
    "reset_query_cache",
]


@lru_cache(maxsize=256)
def _embed_query_cached(testo: str) -> tuple[float, ...]:
    return tuple(embed_texts([testo])[0])


def embed_query(testo: str) -> list[float]:
    return list(_embed_query_cached(testo.strip()))


def reset_query_cache() -> None:
    _embed_query_cached.cache_clear()
