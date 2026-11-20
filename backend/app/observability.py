"""Request id, durata e log strutturati.

I log sono righe JSON su stdout: Vercel le raccoglie e restano parsabili senza
aggiungere un formatter globale. Non si registra mai il contenuto dei messaggi,
del testo o delle risposte.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("app.observability")

HOT_PATHS = {"/api/chat", "/api/simplify", "/api/tts"}
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
STRUCTURED_LOGGERS = {"app.observability"}


class StructuredFormatter(logging.Formatter):
    """Riga JSON pura per i log strutturati, formato normale per gli altri.

    Vercel incapsula ogni riga in un record suo: se il messaggio è già JSON,
    chi esporta i log non deve rimuovere un prefisso per leggerlo.
    """

    def format(self, record: logging.LogRecord) -> str:
        if record.name in STRUCTURED_LOGGERS:
            message = record.getMessage()
            if record.exc_info:
                message += "\n" + self.formatException(record.exc_info)
            return message
        return super().format(record)


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format=LOG_FORMAT)
    for handler in logging.getLogger().handlers:
        handler.setFormatter(StructuredFormatter(LOG_FORMAT))



def client_hash(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded else ""
    if not ip and request.client:
        ip = request.client.host
    return hashlib.sha256((ip or "unknown").encode("utf-8")).hexdigest()[:12]


def log_event(request: Request, event: str, **fields) -> None:
    payload = {
        "event": event,
        "request_id": getattr(request.state, "request_id", None),
        **fields,
    }
    logger.info(json.dumps(payload, ensure_ascii=False, default=str))


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Assegna X-Request-ID e logga gli endpoint caldi o gli errori."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            logger.exception(
                json.dumps(
                    {
                        "event": "http_request",
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status": 500,
                        "duration_ms": duration_ms,
                        "client_hash": client_hash(request),
                    }
                )
            )
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        response.headers["x-request-id"] = request_id

        if request.url.path in HOT_PATHS or response.status_code >= 500:
            logger.info(
                json.dumps(
                    {
                        "event": "http_request",
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status": response.status_code,
                        "duration_ms": duration_ms,
                        "client_hash": client_hash(request),
                    }
                )
            )
        return response
