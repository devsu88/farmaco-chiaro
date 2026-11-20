"""Rate limit in memoria per gli endpoint che chiamano il provider LLM.

Il limite è per IP e per istanza: su più istanze il valore effettivo è la
somma. È un best-effort accettato per la demo; uno store condiviso richiede
una spec successiva.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

from fastapi import HTTPException, Request

from app import config
from app.observability import log_event


@dataclass(frozen=True)
class Limit:
    max_requests: int
    window_seconds: float


LIMITS = {
    "chat": Limit(config.RATE_LIMIT_CHAT, config.RATE_LIMIT_WINDOW_SECONDS),
    "simplify": Limit(config.RATE_LIMIT_SIMPLIFY, config.RATE_LIMIT_WINDOW_SECONDS),
    "tts": Limit(config.RATE_LIMIT_TTS, config.RATE_LIMIT_WINDOW_SECONDS),
}


class SlidingWindowLimiter:
    """Finestra scorrevole thread-safe con clock iniettabile."""

    def __init__(self, clock=time.monotonic) -> None:
        self._clock = clock
        self._events: dict[str, deque[float]] = {}
        self._windows: dict[str, float] = {}
        self._lock = threading.Lock()
        self._hits = 0

    def hit(self, key: str, limit: Limit) -> tuple[bool, int, int]:
        """Registra un hit. Restituisce (consentito, retry_after, rimanenti)."""
        now = self._clock()
        with self._lock:
            events = self._events.setdefault(key, deque())
            self._windows[key] = limit.window_seconds
            cutoff = now - limit.window_seconds
            while events and events[0] <= cutoff:
                events.popleft()

            if len(events) >= limit.max_requests:
                retry_after = max(1, int(events[0] + limit.window_seconds - now) + 1)
                return False, retry_after, 0

            events.append(now)
            self._hits += 1
            if self._hits % 1024 == 0:
                self._purge(now)
            return True, 0, limit.max_requests - len(events)

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
            self._windows.clear()
            self._hits = 0

    def _purge(self, now: float) -> None:
        for key, events in list(self._events.items()):
            cutoff = now - self._windows.get(key, 0)
            while events and events[0] <= cutoff:
                events.popleft()
            if not events:
                self._events.pop(key, None)
                self._windows.pop(key, None)


limiter = SlidingWindowLimiter()


def client_ip(request: Request) -> str:
    """IP del client: primo valore di X-Forwarded-For, altrimenti il peer."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _reject_large_body(request: Request) -> None:
    raw = request.headers.get("content-length")
    if not raw:
        return
    try:
        length = int(raw)
    except ValueError:
        return
    if length > config.MAX_REQUEST_BYTES:
        raise HTTPException(status_code=413, detail="Richiesta troppo grande")


def rate_limit(bucket: str):
    """Dependency FastAPI per un bucket configurato."""

    async def dependency(request: Request) -> None:
        _reject_large_body(request)
        limit = LIMITS[bucket]
        allowed, retry_after, _ = limiter.hit(
            f"{bucket}:{client_ip(request)}", limit
        )
        if not allowed:
            log_event(request, "rate_limited", bucket=bucket, retry_after=retry_after)
            raise HTTPException(
                status_code=429,
                detail="Troppe richieste. Riprova tra qualche secondo.",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit.max_requests),
                },
            )

    return dependency
