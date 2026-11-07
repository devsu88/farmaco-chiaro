"""Cache persistente su disco per semplificazioni e audio TTS.

I file sono scritti in ``data/cache`` e non vengono committati. La chiave
include il modello e la versione del prompt: cambiando uno dei due, la cache
precedente non viene più usata.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app.config import DATA_DIR

CACHE_ROOT = DATA_DIR / "cache"
SIMPLIFY_DIR = CACHE_ROOT / "simplify"
TTS_DIR = CACHE_ROOT / "tts"

SIMPLIFY_PROMPT_VERSION = "etr-v2-concise"


def _hash(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def chiave_semplificazione(testo: str, modello: str) -> str:
    return _hash(SIMPLIFY_PROMPT_VERSION, modello, testo)


def leggi_semplificazione(testo: str, modello: str) -> dict | None:
    path = SIMPLIFY_DIR / f"{chiave_semplificazione(testo, modello)}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        risultato = payload.get("risultato")
        return risultato if isinstance(risultato, dict) else None
    except (OSError, ValueError):
        return None


def scrivi_semplificazione(testo: str, modello: str, risultato: dict) -> None:
    chiave = chiave_semplificazione(testo, modello)
    payload = {
        "versione": 1,
        "prompt_version": SIMPLIFY_PROMPT_VERSION,
        "modello": modello,
        "creato_il": datetime.now(timezone.utc).isoformat(),
        "input_hash": _hash(testo),
        "risultato": risultato,
    }
    _atomic_write(
        SIMPLIFY_DIR / f"{chiave}.json",
        json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
    )


def svuota_semplificazioni() -> None:
    if not SIMPLIFY_DIR.exists():
        return
    for path in SIMPLIFY_DIR.glob("*.json"):
        try:
            path.unlink()
        except OSError:
            continue


def chiave_tts(testo: str, modello: str, voce: str) -> str:
    return _hash(modello, voce, testo)


def leggi_tts(testo: str, modello: str, voce: str) -> bytes | None:
    path = TTS_DIR / f"{chiave_tts(testo, modello, voce)}.wav"
    if not path.exists():
        return None
    try:
        return path.read_bytes()
    except OSError:
        return None


def scrivi_tts(testo: str, modello: str, voce: str, audio: bytes) -> None:
    chiave = chiave_tts(testo, modello, voce)
    _atomic_write(TTS_DIR / f"{chiave}.wav", audio)
