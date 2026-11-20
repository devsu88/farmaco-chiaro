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

# semantic = Qdrant come fonte primaria (BM25 solo se Qdrant non risponde);
# bm25 = solo lessicale, usato dai test e come modalità offline.
# La ricerca della home combina comunque sempre le due fonti.
RETRIEVAL_MODE = os.getenv("RETRIEVAL_MODE", "semantic").strip().lower()


def _csv_env(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, value)


FRONTEND_ORIGINS = _csv_env("FRONTEND_ORIGINS", "http://localhost:3000")

# Limiti di input e di richiesta. I default sono pensati per un uso umano
# normale della demo, non per un carico da produzione.
MAX_CHAT_MESSAGE_CHARS = _int_env("MAX_CHAT_MESSAGE_CHARS", 1000)
MAX_CHAT_HISTORY_TURNS = _int_env("MAX_CHAT_HISTORY_TURNS", 10)
MAX_CHAT_HISTORY_MESSAGE_CHARS = _int_env("MAX_CHAT_HISTORY_MESSAGE_CHARS", 2000)
MAX_SIMPLIFY_TEXT_CHARS = _int_env("MAX_SIMPLIFY_TEXT_CHARS", 12000)
MAX_SEARCH_QUERY_CHARS = _int_env("MAX_SEARCH_QUERY_CHARS", 200)
MAX_REQUEST_BYTES = _int_env("MAX_REQUEST_BYTES", 2 * 1024 * 1024)

# Rate limit per IP, in memoria e per istanza. Su più istanze il limite
# effettivo è la somma: è documentato come best-effort.
RATE_LIMIT_WINDOW_SECONDS = _int_env("RATE_LIMIT_WINDOW_SECONDS", 60)
RATE_LIMIT_CHAT = _int_env("RATE_LIMIT_CHAT", 20)
RATE_LIMIT_SIMPLIFY = _int_env("RATE_LIMIT_SIMPLIFY", 20)
RATE_LIMIT_TTS = _int_env("RATE_LIMIT_TTS", 10)
