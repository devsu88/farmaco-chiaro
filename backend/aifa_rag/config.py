"""Configurazione condivisa della pipeline AIFA FI → RAG.

Gli artefatti runtime stanno in ``data/rag/``; la cache degli embedding e i
Markdown intermedi restano fuori da git e servono solo a ricostruire l'indice.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
RAG_DIR = DATA_DIR / "rag"
EVAL_DIR = BASE_DIR / "eval"

CHUNKS_FILE = RAG_DIR / "chunks.jsonl"
SECTIONS_FILE = RAG_DIR / "sections.jsonl"
DOCUMENTO_FILE = RAG_DIR / "documento.jsonl"
FARMACI_FILE = RAG_DIR / "farmaci.json"
INDEX_META_FILE = RAG_DIR / "index_meta.json"
MARKDOWN_DIR = RAG_DIR / "markdown"
EMBEDDING_DIR = RAG_DIR / "embeddings"

# Server Qdrant (cloud o docker locale). Se è un percorso, la pipeline usa la
# modalità embedded di qdrant-client (utile solo nei test).
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "").strip()
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "farmaci_v1")

MANIFEST_URLS: dict[str, str] = {
    "confezioni": "https://drive.aifa.gov.it/farmaci/confezioni_fornitura.csv",
    "pa": "https://drive.aifa.gov.it/farmaci/PA_confezioni.csv",
    "atc": "https://drive.aifa.gov.it/farmaci/atc.csv",
}

# Fallback: il manifest contiene già l'URL completo in LINK_FI.
PDF_URL_TEMPLATE = (
    "https://api.aifa.gov.it/aifa-bdf-eif-be/1.0.0/organizzazione/"
    "{codice_sis}/farmaci/{aic6}/stampati?ts=FI"
)

EXCLUDED_PROCEDURE = frozenset({"Omeopatico", "Importazione Parallela"})

CHUNK_TARGET_TOKENS = 600
CHUNK_MAX_TOKENS = 800
CHUNK_OVERLAP_TOKENS = 80
CHUNK_MIN_CHARS = 40

EMBEDDING_MODEL = "nvidia/nemotron-3-embed-1b:free"
EMBED_BATCH_SIZE = 32
