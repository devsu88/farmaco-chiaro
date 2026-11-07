"""Registro unico dei farmaci.

Questo modulo è l'unica fonte di verità per il mapping
``farmaco_id -> file markdown / titolo documento``. Tutti gli altri moduli
(build index, retrieval, route, fallback) devono passare da qui.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.config import FARMACI_FILE, MARKDOWN_DIR


@dataclass(frozen=True)
class Farmaco:
    id: str
    nome: str
    principio_attivo: str
    file_fi: str
    file_rcp: str
    documento: str

    @property
    def path_fi(self) -> Path:
        return MARKDOWN_DIR / "FI" / self.file_fi

    @property
    def path_rcp(self) -> Path:
        return MARKDOWN_DIR / "RCP" / self.file_rcp


@lru_cache(maxsize=1)
def _load() -> dict[str, Farmaco]:
    if not FARMACI_FILE.exists():
        raise FileNotFoundError(f"Registro farmaci non trovato: {FARMACI_FILE}")

    raw = json.loads(FARMACI_FILE.read_text(encoding="utf-8"))
    registro: dict[str, Farmaco] = {}
    for item in raw:
        farmaco = Farmaco(
            id=item["id"],
            nome=item["nome"],
            principio_attivo=item["principio_attivo"],
            file_fi=item["file_fi"],
            file_rcp=item["file_rcp"],
            documento=item["documento"],
        )
        if farmaco.id in registro:
            raise ValueError(f"Farmaco duplicato nel registro: {farmaco.id}")
        registro[farmaco.id] = farmaco
    return registro


def all() -> list[Farmaco]:
    return list(_load().values())


def get(farmaco_id: str) -> Farmaco | None:
    return _load().get(farmaco_id)


def require(farmaco_id: str) -> Farmaco:
    farmaco = get(farmaco_id)
    if farmaco is None:
        raise KeyError(f"Farmaco non trovato: {farmaco_id}")
    return farmaco


def valida_file() -> list[str]:
    """Restituisce la lista dei file mancanti, senza sollevare eccezioni."""
    mancanti: list[str] = []
    for farmaco in all():
        if not farmaco.path_fi.exists():
            mancanti.append(str(farmaco.path_fi))
        if not farmaco.path_rcp.exists():
            mancanti.append(str(farmaco.path_rcp))
    return mancanti


def tieni_primo_foglio(text: str) -> str:
    """Tiene solo il primo foglio illustrativo di un markdown AIFA.

    I file AIFA contengono più fogli concatenati (una formulazione per volta).
    Indicizzarli tutti faceva pescare al retrieval la formulazione sbagliata.
    """
    lines = text.split("\n")
    inizio_fogli = [
        i
        for i, line in enumerate(lines)
        if line.strip().lower().startswith("foglio illustrativo")
    ]
    if len(inizio_fogli) > 1:
        return "\n".join(lines[: inizio_fogli[1]])
    return text
