"""Client embeddings via OpenRouter.

Il modello è configurabile con EMBEDDING_MODEL. Le chiamate sono sincrone
perché il backend FastAPI le esegue nel threadpool e l'ingestion è uno script.
"""
from __future__ import annotations

import os
import time
from functools import lru_cache

import httpx

from app.llm import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, has_valid_api_key

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL", "nvidia/nemotron-3-embed-1b:free"
)
EMBEDDING_TIMEOUT = int(os.getenv("EMBEDDING_TIMEOUT", "60"))
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))
EMBEDDINGS_URL = f"{OPENROUTER_BASE_URL}/embeddings"


class EmbeddingError(RuntimeError):
    pass


def _request_batch(testi: list[str]) -> list[list[float]]:
    if not has_valid_api_key():
        raise EmbeddingError("API key OpenRouter non configurata")

    payload = {"model": EMBEDDING_MODEL, "input": testi}
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    ultimo_errore = ""
    for tentativo in range(3):
        try:
            risposta = httpx.post(
                EMBEDDINGS_URL,
                headers=headers,
                json=payload,
                timeout=EMBEDDING_TIMEOUT,
            )
        except httpx.HTTPError as exc:
            ultimo_errore = f"Embedding non raggiungibile: {type(exc).__name__}"
            time.sleep(1.5 * (tentativo + 1))
            continue

        if risposta.status_code == 429:
            time.sleep(2.0 * (tentativo + 1))
            ultimo_errore = "Rate limit embeddings"
            continue
        if risposta.status_code != 200:
            ultimo_errore = f"Embedding HTTP {risposta.status_code}: {risposta.text[:200]}"
            break

        try:
            data = risposta.json().get("data") or []
            data.sort(key=lambda item: item.get("index", 0))
            vettori = [item["embedding"] for item in data]
        except (ValueError, KeyError, TypeError) as exc:
            ultimo_errore = f"Risposta embeddings non valida: {exc}"
            break

        if len(vettori) != len(testi):
            ultimo_errore = "Numero di embeddings diverso dal numero di testi"
            break
        return vettori

    raise EmbeddingError(ultimo_errore or "Errore embeddings")


def embed_texts(testi: list[str], batch_size: int | None = None) -> list[list[float]]:
    if not testi:
        return []
    batch_size = batch_size or EMBEDDING_BATCH_SIZE
    vettori: list[list[float]] = []
    for inizio in range(0, len(testi), batch_size):
        batch = testi[inizio : inizio + batch_size]
        vettori.extend(_request_batch(batch))
    return vettori


@lru_cache(maxsize=256)
def _embed_query_cached(testo: str) -> tuple[float, ...]:
    return tuple(_request_batch([testo])[0])


def embed_query(testo: str) -> list[float]:
    return list(_embed_query_cached(testo.strip()))


def reset_query_cache() -> None:
    _embed_query_cached.cache_clear()
