"""Configurazione condivisa: percorsi, ambiente e origini CORS."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
INDEX_DIR = BASE_DIR / "index"

CATALOGO_FILE = DATA_DIR / "catalogo_farmaci.json"
FARMACI_FILE = DATA_DIR / "farmaci.json"
BLOCCHI_FILE = INDEX_DIR / "blocchi.json"
INDEX_META_FILE = INDEX_DIR / "index_meta.json"

MARKDOWN_DIR = DATA_DIR / "markdown"


def _csv_env(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


FRONTEND_ORIGINS = _csv_env("FRONTEND_ORIGINS", "http://localhost:3000")
