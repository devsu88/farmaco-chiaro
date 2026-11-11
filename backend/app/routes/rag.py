"""Stato del RAG e keepalive del cluster Qdrant."""
from __future__ import annotations

import json

from fastapi import APIRouter

from app import farmaci
from app.config import INDEX_META_FILE, QDRANT_COLLECTION, QDRANT_URL, RETRIEVAL_MODE
from services import vector_store

router = APIRouter()


def _meta() -> dict:
    if not INDEX_META_FILE.exists():
        return {}
    try:
        return json.loads(INDEX_META_FILE.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}


@router.get("/rag/status")
def rag_status() -> dict:
    """Conteggi e disponibilità dei servizi di retrieval."""
    meta = _meta()
    disponibile = vector_store.is_available()
    return {
        "mode": RETRIEVAL_MODE,
        "farmaci": len(farmaci.all()),
        "index": {
            "count": meta.get("count"),
            "collection": meta.get("collection", QDRANT_COLLECTION),
            "model": meta.get("model"),
            "dim": meta.get("dim"),
        },
        "qdrant": {
            "url_configured": bool(QDRANT_URL),
            "available": disponibile,
            "count": vector_store.count() if disponibile else 0,
        },
    }


@router.get("/rag/keepalive")
def rag_keepalive() -> dict:
    """Tocca il cluster Qdrant per evitare la sospensione del free tier."""
    count = vector_store.count()
    return {"ok": count > 0, "qdrant_count": count}


@router.post("/rag/keepalive")
def rag_keepalive_post() -> dict:
    return rag_keepalive()
