"""Campionamento stratificato dei farmaci dal manifest."""

from __future__ import annotations

from pathlib import Path

from aifa_rag.manifest import read_jsonl, stratified_sample, write_jsonl


def run_sample(
    manifest_path: Path,
    n: int,
    out_path: Path,
    include_names: list[str] | None = None,
    seed: int = 42,
) -> int:
    """Seleziona ``n`` farmaci dal manifest e scrive ``out_path``."""
    rows = read_jsonl(manifest_path)
    selected = stratified_sample(rows, n, seed=seed, include_names=include_names or [])
    return write_jsonl(selected, out_path)
