"""Scarica il manifest AIFA e lo normalizza in una riga per farmaco (AIC6)."""

from __future__ import annotations

import csv
import json
import math
import random
from pathlib import Path
from typing import Iterable

import httpx

from aifa_rag import config

CHUNK_SIZE = 1 << 16


def fetch_manifest(data_dir: Path = config.DATA_DIR) -> Path:
    """Scarica il CSV delle confezioni e restituisce il path locale."""
    data_dir.mkdir(parents=True, exist_ok=True)
    out = data_dir / "confezioni_fornitura.csv"
    tmp = out.with_name(out.name + ".part")
    url = config.MANIFEST_URLS["confezioni"]

    with httpx.stream("GET", url, timeout=120, follow_redirects=True) as resp:
        resp.raise_for_status()
        with tmp.open("wb") as fh:
            for chunk in resp.iter_bytes(CHUNK_SIZE):
                fh.write(chunk)
    tmp.replace(out)
    return out


def parse_confezioni(csv_path: Path) -> list[dict]:
    """Legge il CSV AIFA (separatore ``;``, campi quotati)."""
    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def _split_principi_attivi(raw: str | None) -> list[str]:
    if not raw:
        return []
    parts = [p.strip() for p in raw.split("/")]
    return [p for p in parts if p and p.upper() not in {"N.D.", "N.D", "ND"}]


def _new_entry(row: dict) -> dict:
    procedura = (row.get("TIPO_PROCEDURA") or "").strip()
    link_fi = (row.get("LINK_FI") or "").strip()
    escluso = procedura in config.EXCLUDED_PROCEDURE or not link_fi
    if procedura in config.EXCLUDED_PROCEDURE:
        motivo = procedura
    elif not link_fi:
        motivo = "senza_link_fi"
    else:
        motivo = None

    return {
        "drug_id": (row.get("COD_FARMACO") or "").strip(),
        "aic": (row.get("CODICE_AIC") or "").strip(),
        "nome": (row.get("DENOMINAZIONE") or "").strip(),
        "principi_attivi": _split_principi_attivi(row.get("PA_ASSOCIATI")),
        "atc": (row.get("CODICE_ATC") or "").strip(),
        "ditta": (row.get("RAGIONE_SOCIALE") or "").strip(),
        "forma": (row.get("FORMA") or "").strip(),
        "procedura": procedura,
        "stato": (row.get("STATO_AMMINISTRATIVO") or "").strip(),
        "link_fi": link_fi,
        "escluso": escluso,
        "motivo_esclusione": motivo,
    }


def build_manifest(rows: list[dict]) -> list[dict]:
    """Raggruppa le confezioni per ``COD_FARMACO`` in una riga per farmaco."""
    by_drug: dict[str, dict] = {}
    for row in rows:
        drug_id = (row.get("COD_FARMACO") or "").strip()
        if not drug_id:
            continue
        entry = by_drug.get(drug_id)
        if entry is None:
            by_drug[drug_id] = _new_entry(row)
            continue
        # Confezioni diverse dello stesso farmaco possono elencare PA in ordine
        # diverso: unisci preservando l'ordine di prima apparizione.
        for pa in _split_principi_attivi(row.get("PA_ASSOCIATI")):
            if pa not in entry["principi_attivi"]:
                entry["principi_attivi"].append(pa)
    return list(by_drug.values())


def write_jsonl(rows: Iterable[dict], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    count = 0
    with tmp.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    tmp.replace(path)
    return count


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _allocate(total: int, sizes: dict[str, int]) -> dict[str, int]:
    """Ripartisce ``total`` proporzionalmente a ``sizes`` (metodo dei resti)."""
    pool = sum(sizes.values())
    if pool == 0 or total <= 0:
        return {key: 0 for key in sizes}
    total = min(total, pool)

    quotas = {key: total * size / pool for key, size in sizes.items()}
    base = {key: math.floor(q) for key, q in quotas.items()}
    remainder = total - sum(base.values())

    order = sorted(
        sizes,
        key=lambda k: (quotas[k] - base[k], sizes[k], k),
        reverse=True,
    )
    for key in order[:remainder]:
        base[key] += 1
    return base


def stratified_sample(
    rows: list[dict],
    n: int,
    seed: int = 42,
    include_names: list[str] | None = None,
) -> list[dict]:
    """Campiona ``n`` farmaci in modo deterministico, stratificando per ATC.

    I farmaci esclusi (omeopatici, importazione parallela, senza FI) non
    vengono mai campionati. ``include_names`` forza l'inclusione per prefisso
    del nome (case-insensitive).
    """
    pool = [row for row in rows if not row.get("escluso")]
    selected: list[dict] = []
    selected_ids: set[str] = set()

    if include_names:
        wanted = [name.strip().upper() for name in include_names if name.strip()]
        for name in wanted:
            for row in pool:
                if row["drug_id"] in selected_ids:
                    continue
                if (row.get("nome") or "").upper().startswith(name):
                    selected.append(row)
                    selected_ids.add(row["drug_id"])
                    break

    remaining = max(0, n - len(selected))
    candidates = [row for row in pool if row["drug_id"] not in selected_ids]
    if remaining and candidates:
        rng = random.Random(seed)
        groups: dict[str, list[dict]] = {}
        for row in candidates:
            atc = (row.get("atc") or "").strip().upper()
            key = atc[0] if atc else "?"
            groups.setdefault(key, []).append(row)

        sizes = {key: len(group) for key, group in groups.items()}
        quotas = _allocate(remaining, sizes)
        for key in sorted(groups):
            take = min(quotas[key], sizes[key])
            if take:
                selected.extend(rng.sample(groups[key], take))

    return selected
