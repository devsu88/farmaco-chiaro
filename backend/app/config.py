"""Configurazione condivisa: percorsi, ambiente e origini CORS."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAG_DIR = DATA_DIR / "rag"

SCENARI_FILE = DATA_DIR / "scenari.json"
CHUNKS_FILE = RAG_DIR / "chunks.jsonl"
SECTIONS_FILE = RAG_DIR / "sections.jsonl"
DOCUMENTO_FILE = RAG_DIR / "documento.jsonl"
FARMACI_FILE = RAG_DIR / "farmaci.json"
INDEX_META_FILE = RAG_DIR / "index_meta.json"

# Qdrant è un servizio esterno: su Vercel i container non hanno disco
# persistente. Se non è raggiungibile, il retrieval degrada a BM25.
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333").strip()
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "").strip()
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "farmaci_v1")
QDRANT_TIMEOUT = float(os.getenv("QDRANT_TIMEOUT", "4"))

# hybrid = BM25 + Qdrant con RRF; bm25 = solo lessicale (CI e fallback).
RETRIEVAL_MODE = os.getenv("RETRIEVAL_MODE", "hybrid").strip().lower()


def _csv_env(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


FRONTEND_ORIGINS = _csv_env("FRONTEND_ORIGINS", "http://localhost:3000")
