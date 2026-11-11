"""Genera ``data/report.md`` dai risultati della pipeline."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from aifa_rag import config


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _percent(part: int, total: int) -> str:
    return f"{(100 * part / total):.1f}%" if total else "n/d"


def collect_stats() -> dict:
    data = config.DATA_DIR
    sample = _jsonl(data / "sample.jsonl")
    failures = _jsonl(data / "fetch_failures.jsonl")
    markdown = list(config.MARKDOWN_DIR.glob("*/*.md"))
    chunks = _jsonl(config.CHUNKS_FILE)
    sections = _jsonl(config.SECTIONS_FILE)
    documento = _jsonl(config.DOCUMENTO_FILE)
    registry = (
        json.loads(config.FARMACI_FILE.read_text(encoding="utf-8"))
        if config.FARMACI_FILE.exists()
        else []
    )

    # Fogli (drug_id, foglio) duplicati: la deduplica ne tiene uno solo.
    per_foglio: dict[tuple[str, str], set[str]] = defaultdict(set)
    for path in markdown:
        per_foglio[(path.parent.name, path.stem)].add(path.stem)
    duplicate_keys = 0
    for row in chunks:
        per_foglio[(row["drug_id"], row.get("foglio", ""))].add(row["farmaco_id"])
    duplicate_keys = sum(1 for ids in per_foglio.values() if len(ids) > 1)

    with_chunks = {row["drug_id"] for row in chunks if row.get("drug_id")}
    without_chunks = sorted(
        {
            row.get("drug_id", "")
            for row in sample
            if row.get("drug_id") and row.get("drug_id") not in with_chunks
        }
    )

    eval_report = None
    eval_path = data / "eval_report.json"
    if eval_path.exists():
        eval_report = json.loads(eval_path.read_text(encoding="utf-8"))

    control_path = data / "control_queries.md"
    control_queries = (
        control_path.read_text(encoding="utf-8").strip() if control_path.exists() else ""
    )

    tokens = [chunk.get("n_tokens", 0) for chunk in chunks]
    return {
        "sample": len(sample),
        "failures": failures,
        "failure_status": Counter(f.get("status", "?") for f in failures),
        "markdown": len(markdown),
        "chunks": chunks,
        "tokens": tokens,
        "sections": sections,
        "documento": documento,
        "registry": registry,
        "duplicate_keys": duplicate_keys,
        "without_chunks": without_chunks,
        "eval": eval_report,
        "control_queries": control_queries,
    }


def render(stats: dict) -> str:
    chunks = stats["chunks"]
    tokens = stats["tokens"]
    lines = [
        "# Farmaco Chiaro — RAG AIFA",
        "",
        "Generato da `aifa_rag.report` sugli artefatti in `data/rag/`.",
        "",
        "## Raccolta",
        "",
        "| Metrica | Valore |",
        "| --- | --- |",
        f"| Farmaci campionati | {stats['sample']} |",
        f"| Fallimenti di fetch | {len(stats['failures'])} |",
    ]
    for status, count in sorted(stats["failure_status"].items()):
        lines.append(f"| Fallimenti `{status}` | {count} |")

    lines += [
        "",
        "## Dataset",
        "",
        "| Metrica | Valore |",
        "| --- | --- |",
        f"| Fogli illustrativi (Markdown) | {stats['markdown']} |",
        f"| Fogli nel registro | {len(stats['registry'])} |",
        f"| Fogli duplicati risolti | {stats['duplicate_keys']} |",
        f"| Chunk totali | {len(chunks)} |",
        f"| Blocchi documento | {len(stats['documento'])} |",
        f"| Sezioni H2 | {len(stats['sections'])} |",
        f"| Farmaci campionati senza chunk | {len(stats['without_chunks'])} |",
    ]
    if tokens:
        lines += [
            f"| Token max (stima) | {max(tokens)} |",
            f"| Token medi (stima) | {sum(tokens) // len(tokens)} |",
            f"| Chunk oltre il hard max | {sum(1 for t in tokens if t > config.CHUNK_MAX_TOKENS)} |",
        ]

    evaluation = stats["eval"]
    if evaluation:
        lines += [
            "",
            "## Valutazione (densa)",
            "",
            "| Metrica | Valore |",
            "| --- | --- |",
            f"| Domande | {evaluation['n']} |",
            f"| recall@{evaluation['k']} | {evaluation['recall_at_k']:.3f} |",
            f"| MRR | {evaluation['mrr']:.3f} |",
            f"| Fallimenti | {len(evaluation['failures'])} |",
        ]
        if evaluation["failures"]:
            lines += ["", "### Domande senza hit atteso", ""]
            for failure in evaluation["failures"]:
                lines.append(f"- {failure['question']}")

    if stats["without_chunks"]:
        lines += ["", "## Farmaci campionati senza contenuto", ""]
        lines += [f"- `{drug_id}`" for drug_id in stats["without_chunks"]]

    if stats["control_queries"]:
        lines += ["", "## Query di controllo", "", stats["control_queries"]]

    lines += [
        "",
        "## Modello",
        "",
        f"- Embedding: `{config.EMBEDDING_MODEL}`",
        f"- Collezione Qdrant: `{config.QDRANT_COLLECTION}`",
        f"- Server: `{config.QDRANT_URL}`",
    ]
    return "\n".join(lines) + "\n"


def write_report(path: Path | None = None) -> Path:
    path = path or config.DATA_DIR / "report.md"
    path.write_text(render(collect_stats()), encoding="utf-8")
    return path
