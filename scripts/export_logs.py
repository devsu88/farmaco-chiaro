#!/usr/bin/env python3
"""Esporta i log runtime di Vercel in JSONL normalizzato.

Percorso per il piano Hobby, dove i Log Drains non sono disponibili e i log
restano visibili solo per un'ora. Usa la CLI già autenticata (o la variabile
``VERCEL_TOKEN``) e scrive gli eventi nel formato letto da
``scripts/log_report.py``.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from log_report import normalize_record, parse_lines, record_key  # noqa: E402


def build_command(
    since: str, limit: int, project: str = "", scope: str = ""
) -> list[str]:
    command = ["vercel", "logs", "--json", "--since", since, "--limit", str(limit)]
    if project:
        command += ["--project", project]
    if scope:
        command += ["--scope", scope]
    return command


def export_logs(
    since: str = "50m",
    limit: int = 10000,
    project: str = "",
    scope: str = "",
    runner=subprocess.run,
) -> list[dict]:
    """Esegue `vercel logs` e restituisce gli eventi strutturati, senza duplicati."""
    result = runner(
        build_command(since, limit, project, scope),
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            (result.stderr or "").strip()
            or f"vercel logs è uscito con codice {result.returncode}"
        )

    events: list[dict] = []
    seen: set = set()
    for line in (result.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        event = normalize_record(record)
        if event is None:
            continue
        key = record_key(event)
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
        events.append(event)
    return events


def write_events(events: list[dict], output: str | Path, append: bool = False) -> int:
    """Scrive gli eventi in JSONL; con `append` salta quelli già presenti."""
    if str(output) == "-":
        for event in events:
            print(json.dumps(event, ensure_ascii=False))
        return len(events)

    path = Path(output)
    seen: set = set()
    if append and path.exists():
        for event in parse_lines(path.read_text(encoding="utf-8").splitlines()):
            key = record_key(event)
            if key is not None:
                seen.add(key)

    written = 0
    with path.open("a" if append else "w", encoding="utf-8") as handle:
        for event in events:
            key = record_key(event)
            if key is not None:
                if key in seen:
                    continue
                seen.add(key)
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            written += 1
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Esporta i log Vercel in JSONL per scripts/log_report.py",
        epilog="Autenticazione: `vercel login` oppure la variabile VERCEL_TOKEN.",
    )
    parser.add_argument("--since", default="50m", help="finestra, es. 50m o 1h")
    parser.add_argument("--limit", type=int, default=10000)
    parser.add_argument("--output", default="-", help="file JSONL o - per stdout")
    parser.add_argument("--append", action="store_true", help="aggiunge al file")
    parser.add_argument("--project", default=os.getenv("VERCEL_PROJECT", ""))
    parser.add_argument("--scope", default=os.getenv("VERCEL_SCOPE", ""))
    args = parser.parse_args(argv)

    try:
        events = export_logs(
            since=args.since,
            limit=args.limit,
            project=args.project,
            scope=args.scope,
        )
    except RuntimeError as exc:
        print(f"export fallito: {exc}", file=sys.stderr)
        return 2

    written = write_events(events, args.output, append=args.append)
    if str(args.output) != "-":
        print(f"{written} eventi scritti in {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
