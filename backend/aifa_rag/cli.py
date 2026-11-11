"""Entry point CLI della pipeline AIFA FI → RAG."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from aifa_rag import config
from aifa_rag.chunk import (
    build_chunks,
    document_rows,
    section_rows,
    write_chunks,
)
from aifa_rag.evaluate import evaluate, load_qa
from aifa_rag.fetch import run_fetch
from aifa_rag.index import build_index
from aifa_rag.manifest import (
    build_manifest,
    fetch_manifest,
    parse_confezioni,
    read_jsonl,
    write_jsonl,
)
from aifa_rag.markdown import split_leaflets, write_markdown
from aifa_rag.query import expand_result, format_result, load_sections, search
from aifa_rag.report import write_report
from aifa_rag.sample import run_sample
from aifa_rag.store import VectorStore


def cmd_fetch_manifest(args: argparse.Namespace) -> None:
    csv_path = fetch_manifest(config.DATA_DIR)
    rows = parse_confezioni(csv_path)
    manifest = build_manifest(rows)
    out = config.DATA_DIR / "manifest.jsonl"
    n = write_jsonl(manifest, out)
    print(f"{len(rows)} confezioni -> {n} farmaci -> {out}")


def cmd_sample(args: argparse.Namespace) -> None:
    names = [n for n in (args.include_names or "").split(",") if n.strip()]
    out = config.DATA_DIR / "sample.jsonl"
    n = run_sample(
        config.DATA_DIR / "manifest.jsonl",
        args.n,
        out,
        include_names=names,
        seed=args.seed,
    )
    print(f"{n} farmaci campionati -> {out}")


def cmd_fetch(args: argparse.Namespace) -> None:
    rows = read_jsonl(config.DATA_DIR / "sample.jsonl")
    pdf_dir = config.DATA_DIR / "pdf" if args.keep_pdf else None
    results = run_fetch(
        rows,
        config.RAG_DIR / "text",
        pdf_dir=pdf_dir,
        workers=args.workers,
        limit=args.limit,
        failures_path=config.DATA_DIR / "fetch_failures.jsonl",
    )
    counts = Counter(r.status.value for r in results)
    print(f"risultati: {dict(counts)}")
    print(f"pagine estratte: {sum(r.pages for r in results)}")


def cmd_markdown(args: argparse.Namespace) -> None:
    rows = read_jsonl(config.DATA_DIR / "sample.jsonl")
    text_dir = config.RAG_DIR / "text"

    written = 0
    missing = 0
    empty = 0
    for row in rows:
        text_path = text_dir / f"{row['drug_id']}.txt"
        if not text_path.exists():
            missing += 1
            continue
        pages = text_path.read_text(encoding="utf-8").split("\f")
        leaflets = split_leaflets(pages)
        if not leaflets:
            empty += 1
            continue
        fetched_at = datetime.fromtimestamp(
            text_path.stat().st_mtime, tz=timezone.utc
        ).isoformat(timespec="seconds")
        for index, leaflet in enumerate(leaflets, start=1):
            write_markdown(
                leaflet,
                row,
                config.MARKDOWN_DIR,
                index,
                source_url=row.get("link_fi", ""),
                fetched_at=fetched_at,
            )
            written += 1

    print(f"fogli scritti: {written} | testi mancanti: {missing} | senza fogli: {empty}")


def _select_leaflets(md_dir: Path) -> list[tuple[Path, list]]:
    """Sceglie un solo file per ``(drug_id, foglio)``.

    Alcuni farmaci hanno due file con lo stesso titolo di foglio (duplicati
    AIFA). Teniamo quello con più chunk, che è il più completo.
    """
    by_key: dict[tuple[str, str], list[tuple[Path, list]]] = {}
    for path in sorted(md_dir.glob("*/*.md")):
        chunks = build_chunks(path)
        if not chunks:
            continue
        key = (chunks[0].drug_id, chunks[0].foglio)
        by_key.setdefault(key, []).append((path, chunks))
    return [
        max(items, key=lambda item: len(item[1])) for items in by_key.values()
    ]


def cmd_chunk(args: argparse.Namespace) -> None:
    chosen = _select_leaflets(config.MARKDOWN_DIR)
    chunks = []
    sections: list[dict] = []
    for path, leaflet_chunks in chosen:
        chunks.extend(leaflet_chunks)
        sections.extend(section_rows(path))

    n = write_chunks(chunks, config.CHUNKS_FILE)
    write_jsonl(sections, config.SECTIONS_FILE)
    print(
        f"{n} chunk -> {config.CHUNKS_FILE} | "
        f"{len(sections)} sezioni -> {config.SECTIONS_FILE} | "
        f"{len(chosen)} fogli"
    )


def _farmaco_paths() -> list[Path]:
    """Percorsi Markdown dei fogli selezionati, dedotti da ``chunks.jsonl``."""
    farmaci = {
        row["farmaco_id"]
        for row in read_jsonl(config.CHUNKS_FILE)
        if row.get("farmaco_id")
    }
    paths = []
    for farmaco_id in sorted(farmaci):
        drug_id, _, leaflet = farmaco_id.rpartition("_")
        path = config.MARKDOWN_DIR / drug_id / f"{leaflet}.md"
        if path.exists():
            paths.append(path)
    return paths


def cmd_document(args: argparse.Namespace) -> None:
    rows: list[dict] = []
    for path in _farmaco_paths():
        rows.extend(document_rows(path))
    write_jsonl(rows, config.DOCUMENTO_FILE)
    print(f"{len(rows)} blocchi documento -> {config.DOCUMENTO_FILE}")


def cmd_registry(args: argparse.Namespace) -> None:
    by_farmaco: dict[str, list[dict]] = {}
    for row in read_jsonl(config.CHUNKS_FILE):
        by_farmaco.setdefault(row["farmaco_id"], []).append(row)

    registry: list[dict] = []
    for farmaco_id, items in sorted(by_farmaco.items()):
        first = items[0]
        registrazione = {
            "id": farmaco_id,
            "drug_id": first["drug_id"],
            "leaflet": farmaco_id.rpartition("_")[2],
            "nome": first.get("foglio") or first.get("nome", ""),
            "principio_attivo": ", ".join(first.get("principi_attivi") or []),
            "principi_attivi": list(first.get("principi_attivi") or []),
            "atc": first.get("atc", ""),
            "documento": f"Foglio illustrativo {first.get('foglio', '')}".strip(),
            "source_url": first.get("source_url", ""),
            "n_chunks": len(items),
        }
        registry.append(registrazione)

    config.FARMACI_FILE.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{len(registry)} farmaci -> {config.FARMACI_FILE}")


def cmd_dataset(args: argparse.Namespace) -> None:
    """Rigenera chunk, sezioni, documento e registro in un solo passaggio."""
    cmd_chunk(args)
    cmd_document(args)
    cmd_registry(args)


def cmd_index(args: argparse.Namespace) -> None:
    n = build_index(
        config.CHUNKS_FILE,
        config.EMBEDDING_DIR,
        config.QDRANT_URL,
        batch_size=args.batch_size,
        api_key=config.QDRANT_API_KEY,
        collection=config.QDRANT_COLLECTION,
        meta_path=config.INDEX_META_FILE,
    )
    print(f"{n} chunk indicizzati -> {config.QDRANT_URL} ({config.QDRANT_COLLECTION})")


def _filters(drug: str | None, section: str | None, tipo: str | None) -> dict[str, str] | None:
    filters = {}
    if drug:
        filters["drug_id"] = drug
    if section:
        filters["sezione_key"] = section
    if tipo:
        filters["tipo"] = tipo
    return filters or None


def _load_index() -> VectorStore:
    return VectorStore.open(
        config.QDRANT_URL,
        config.QDRANT_COLLECTION,
        config.QDRANT_API_KEY,
    )


def cmd_query(args: argparse.Namespace) -> None:
    index = _load_index()
    hits = search(
        index,
        args.question,
        k=args.k,
        filters=_filters(args.drug, args.sezione, args.tipo),
    )
    sections = load_sections(config.SECTIONS_FILE) if args.expand else {}

    if not hits:
        print("nessun risultato")
        return
    for hit in hits:
        shown = dict(hit)
        if args.expand:
            shown["testo"] = expand_result(hit, sections)
        print(format_result(shown))
        print()


def cmd_eval(args: argparse.Namespace) -> None:
    qa = load_qa(config.EVAL_DIR / "qa.jsonl")
    index = _load_index()
    report = evaluate(index, qa, k=args.k)

    out = config.DATA_DIR / "eval_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"domande: {report['n']} | k: {report['k']}")
    print(f"recall@{report['k']}: {report['recall_at_k']:.3f}")
    print(f"MRR: {report['mrr']:.3f}")
    print(f"fallimenti: {len(report['failures'])} -> {out}")
    for failure in report["failures"][:10]:
        print(f"  - {failure['question']}")


def cmd_report(args: argparse.Namespace) -> None:
    path = write_report()
    print(f"report -> {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aifa_rag")
    sub = parser.add_subparsers(dest="command", required=True)

    p_manifest = sub.add_parser("fetch-manifest", help="scarica e normalizza il CSV AIFA")
    p_manifest.set_defaults(func=cmd_fetch_manifest)

    p_sample = sub.add_parser("sample", help="campiona N farmaci dal manifest")
    p_sample.add_argument("--n", type=int, default=500)
    p_sample.add_argument("--seed", type=int, default=42)
    p_sample.add_argument("--include-names", default="", help="nomi separati da virgola")
    p_sample.set_defaults(func=cmd_sample)

    p_fetch = sub.add_parser("fetch", help="scarica i PDF ed estrae il testo")
    p_fetch.add_argument("--workers", type=int, default=6)
    p_fetch.add_argument("--limit", type=int, default=None)
    p_fetch.add_argument("--keep-pdf", action="store_true")
    p_fetch.add_argument("--refresh", action="store_true")
    p_fetch.set_defaults(func=cmd_fetch)

    p_markdown = sub.add_parser("markdown", help="converte i testi in Markdown strutturato")
    p_markdown.set_defaults(func=cmd_markdown)

    p_chunk = sub.add_parser("chunk", help="genera chunk e sezioni dai Markdown")
    p_chunk.set_defaults(func=cmd_chunk)

    p_document = sub.add_parser("document", help="genera i blocchi del documento originale")
    p_document.set_defaults(func=cmd_document)

    p_registry = sub.add_parser("registry", help="genera il registro dei fogli")
    p_registry.set_defaults(func=cmd_registry)

    p_dataset = sub.add_parser("dataset", help="esegue chunk + document + registry")
    p_dataset.set_defaults(func=cmd_dataset)

    p_index = sub.add_parser("index", help="calcola gli embedding e popola l'indice")
    p_index.add_argument("--batch-size", type=int, default=32)
    p_index.set_defaults(func=cmd_index)

    p_query = sub.add_parser("query", help="interroga l'indice")
    p_query.add_argument("question")
    p_query.add_argument("-k", "--k", dest="k", type=int, default=5)
    p_query.add_argument("--drug", default=None, help="filtra per drug_id")
    p_query.add_argument("--sezione", "--section", dest="sezione", default=None)
    p_query.add_argument("--tipo", default=None, help="filtra per tipo (FI)")
    p_query.add_argument("--expand", action="store_true", help="mostra la sezione H2 intera")
    p_query.set_defaults(func=cmd_query)

    p_eval = sub.add_parser("eval", help="valuta il retrieval su eval/qa.jsonl")
    p_eval.add_argument("-k", "--k", dest="k", type=int, default=5)
    p_eval.set_defaults(func=cmd_eval)

    p_report = sub.add_parser("report", help="genera data/report.md")
    p_report.set_defaults(func=cmd_report)

    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
