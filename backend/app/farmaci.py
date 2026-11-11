"""Registro unico dei fogli illustrativi indicizzati.

L'unità è il foglio illustrativo, non il prodotto AIFA: un farmaco può avere
più formulazioni (es. Tachipirina compresse, supposte, sciroppo). L'id è
``{drug_id}_{leaflet}``, es. ``012745_01``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

from app.config import CHUNKS_FILE, DOCUMENTO_FILE, FARMACI_FILE, SECTIONS_FILE


@dataclass(frozen=True)
class Farmaco:
    id: str
    nome: str
    principio_attivo: str
    principi_attivi: tuple[str, ...]
    documento: str
    drug_id: str
    leaflet: str
    atc: str
    n_chunks: int


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
            principio_attivo=item.get("principio_attivo", ""),
            principi_attivi=tuple(item.get("principi_attivi") or []),
            documento=item.get("documento", ""),
            drug_id=item.get("drug_id", ""),
            leaflet=item.get("leaflet", ""),
            atc=item.get("atc", ""),
            n_chunks=int(item.get("n_chunks", 0)),
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
    """Restituisce gli artefatti mancanti o vuoti, senza sollevare eccezioni."""
    mancanti: list[str] = []
    for path in (CHUNKS_FILE, SECTIONS_FILE, DOCUMENTO_FILE, FARMACI_FILE):
        if not path.exists() or path.stat().st_size == 0:
            mancanti.append(str(path))
    return mancanti


def reset_cache() -> None:
    _load.cache_clear()
