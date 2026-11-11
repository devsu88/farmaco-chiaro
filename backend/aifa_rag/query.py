"""Ricerca semantica sull'indice vettoriale locale."""

from __future__ import annotations

import json
from pathlib import Path

from aifa_rag.embeddings import embed_texts


def search(
    index,
    query: str,
    k: int = 5,
    filters: dict[str, str] | None = None,
) -> list[dict]:
    """Embedda la domanda e restituisce i chunk più simili con score coseno."""
    return index.search(embed_texts([query])[0], k=k, filters=filters)


def format_result(hit: dict) -> str:
    """Formatta un risultato con farmaco, sezione, pagina e URL."""
    title = hit.get("heading_path") or " — ".join(
        part
        for part in (hit.get("nome"), hit.get("sezione_titolo"), hit.get("sottosezione_titolo"))
        if part
    )
    score = hit.get("score")
    score_text = f"score {score:.2f}" if isinstance(score, (int, float)) else "score n/d"
    return (
        f"{title} ({score_text}, pag. {hit.get('pagina', '?')})\n"
        f"{hit.get('testo', '')}\n"
        f"{hit.get('source_url', '')}"
    )


def load_sections(path: Path) -> dict[str, str]:
    """Carica ``sections.jsonl`` per l'espansione small-to-big."""
    sections: dict[str, str] = {}
    if not path.exists():
        return sections
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        sections[row["parent_id"]] = row["testo"]
    return sections


def expand_result(chunk: dict, sections: dict[str, str]) -> str:
    """Restituisce la sezione H2 intera che contiene il chunk."""
    return sections.get(chunk.get("parent_id", ""), chunk.get("testo", ""))
