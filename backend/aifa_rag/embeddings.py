"""Embedding via OpenRouter (``nvidia/nemotron-3-embed-1b:free``).

L'API è ``POST https://openrouter.ai/api/v1/embeddings`` con ``model`` e
``input`` (array di stringhe); la risposta contiene ``data[i].embedding``
con ``data[i].index`` che identifica la posizione dell'input.

I modelli free hanno un limite di 20 richieste al minuto: quando la risposta
segnala ``X-RateLimit-Remaining: 0`` il client aspetta ``X-RateLimit-Reset``
prima della richiesta successiva.
"""

from __future__ import annotations

import os
import time

import httpx

from aifa_rag import config

API_URL = "https://openrouter.ai/api/v1/embeddings"
TIMEOUT = 120
RETRIES = 8
MAX_BACKOFF = 30
RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504}

_cooldown_until = 0.0


class EmbeddingError(RuntimeError):
    """Errore non recuperabile della API di embedding."""


def _api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        key = _dotenv_value("OPENROUTER_API_KEY")
    if not key:
        raise EmbeddingError(
            "OPENROUTER_API_KEY non impostata: esportala o scrivila in .env "
            "prima di indicizzare o interrogare."
        )
    return key


def _dotenv_value(name: str) -> str:
    """Legge ``KEY=valore`` da ``.env`` nella radice del backend, se esiste."""
    path = config.BASE_DIR / ".env"
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() == name:
            return value.strip().strip("\"'")
    return ""


def _parse(payload: dict, expected: int) -> list[list[float]]:
    items = payload.get("data") or []
    if len(items) != expected:
        raise EmbeddingError(f"risposta con {len(items)} embedding, attesi {expected}")
    items.sort(key=lambda item: item.get("index", 0))
    return [item["embedding"] for item in items]


def _rate_headers(response: httpx.Response) -> dict[str, str]:
    """Header di rate limit, anche quando OpenRouter li mette nel body d'errore."""
    headers = {key.lower(): value for key, value in response.headers.items()}
    if response.status_code != 200:
        try:
            extra = response.json().get("error", {}).get("metadata", {}).get("headers", {})
        except ValueError:
            extra = {}
        for key, value in extra.items():
            headers.setdefault(key.lower(), value)
    return headers


def _note_rate_limit(response: httpx.Response) -> None:
    global _cooldown_until
    headers = _rate_headers(response)
    reset = str(headers.get("x-ratelimit-reset", "")).strip()
    remaining = str(headers.get("x-ratelimit-remaining", "")).strip()
    if remaining == "0" and reset.isdigit():
        _cooldown_until = max(_cooldown_until, float(reset) / 1000.0 + 1.0)


def _wait_for_cooldown() -> None:
    wait = _cooldown_until - time.time()
    if wait > 0:
        time.sleep(wait)


def _embed_batch(texts: list[str], model: str) -> list[list[float]]:
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }
    body = {"model": model, "input": texts}

    last_error = ""
    for attempt in range(RETRIES):
        _wait_for_cooldown()
        try:
            response = httpx.post(API_URL, json=body, headers=headers, timeout=TIMEOUT)
        except httpx.HTTPError as exc:
            last_error = str(exc)
        else:
            if response.status_code == 200:
                _note_rate_limit(response)
                return _parse(response.json(), len(texts))

            last_error = f"HTTP {response.status_code}: {response.text[:300]}"
            if response.status_code not in RETRY_STATUS:
                break
            _note_rate_limit(response)
            if _cooldown_until > time.time():
                continue
            retry_after = response.headers.get("Retry-After", "")
            if retry_after.isdigit():
                time.sleep(min(int(retry_after), 60))
                continue
        if attempt < RETRIES - 1:
            time.sleep(min(2**attempt, MAX_BACKOFF))

    raise EmbeddingError(f"embedding fallito dopo {RETRIES} tentativi: {last_error}")


def embed_texts(
    texts: list[str],
    batch_size: int = config.EMBED_BATCH_SIZE,
    model: str = config.EMBEDDING_MODEL,
) -> list[list[float]]:
    """Embedda i testi a blocchi, preservando l'ordine di input."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        vectors.extend(_embed_batch(list(texts[start : start + batch_size]), model))
    return vectors
