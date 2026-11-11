"""Scarica i PDF dei fogli illustrativi e ne estrae il testo pagina per pagina."""

from __future__ import annotations

import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable

import httpx

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) aifa-rag/0.1"}
TIMEOUT = 120
BACKOFF_BASE = 0.5


class FetchStatus(str, Enum):
    OK = "ok"
    SKIPPED = "skipped"
    NOT_FOUND = "not_found"
    INVALID = "invalid"
    ERROR = "error"


@dataclass
class ExtractResult:
    drug_id: str
    status: FetchStatus
    text_path: Path | None = None
    pdf_path: Path | None = None
    http_status: int | None = None
    pages: int = 0
    error: str | None = None


def fetch_pdf(url: str, retries: int = 3) -> tuple[int, bytes | None]:
    """Scarica un PDF e ne valida il magic number.

    Ritorna ``(http_status, body)``; ``body`` è ``None`` quando la risposta non
    è un PDF (404, HTML con 200, errore di rete dopo i retry).
    """
    status = 0
    for attempt in range(retries):
        try:
            resp = httpx.get(url, headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)
        except httpx.HTTPError:
            status = 0
        else:
            status = resp.status_code
            if status == 200:
                return 200, resp.content if resp.content.startswith(b"%PDF") else None
            if status == 404:
                return 404, None
        if attempt < retries - 1:
            time.sleep(BACKOFF_BASE * 2**attempt)
    return status, None


def extract_pages(pdf_bytes: bytes) -> list[str]:
    """Estrae il testo con ``pdftotext -layout`` leggendo il PDF da stdin."""
    proc = subprocess.run(
        ["pdftotext", "-layout", "-", "-"],
        input=pdf_bytes,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"pdftotext fallito: {proc.stderr.decode('utf-8', 'replace')[:200]}")
    text = proc.stdout.decode("utf-8", errors="replace")
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(data)
    tmp.replace(path)


def fetch_and_extract(
    row: dict,
    text_dir: Path,
    pdf_dir: Path | None = None,
    refresh: bool = False,
) -> ExtractResult:
    drug_id = row["drug_id"]
    text_path = text_dir / f"{drug_id}.txt"

    if text_path.exists() and not refresh:
        return ExtractResult(drug_id, FetchStatus.SKIPPED, text_path=text_path)

    url = (row.get("link_fi") or "").strip()
    if not url:
        return ExtractResult(drug_id, FetchStatus.ERROR, error="link_fi mancante")

    status, body = fetch_pdf(url)
    if status == 404:
        return ExtractResult(drug_id, FetchStatus.NOT_FOUND, http_status=404)
    if body is None:
        return ExtractResult(drug_id, FetchStatus.INVALID, http_status=status)

    try:
        pages = extract_pages(body)
    except Exception as exc:  # noqa: BLE001 - il fallimento va registrato, non propagato
        return ExtractResult(drug_id, FetchStatus.ERROR, http_status=status, error=str(exc))

    pdf_path = None
    if pdf_dir is not None:
        pdf_path = pdf_dir / f"{drug_id}.pdf"
        _write_atomic(pdf_path, body)

    _write_atomic(text_path, "\f".join(pages).encode("utf-8"))
    return ExtractResult(
        drug_id,
        FetchStatus.OK,
        text_path=text_path,
        pdf_path=pdf_path,
        http_status=status,
        pages=len(pages),
    )


def run_fetch(
    rows: Iterable[dict],
    text_dir: Path,
    pdf_dir: Path | None = None,
    workers: int = 6,
    limit: int | None = None,
    failures_path: Path | None = None,
) -> list[ExtractResult]:
    rows = list(rows)
    if limit is not None:
        rows = rows[:limit]

    results: list[ExtractResult] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(fetch_and_extract, row, text_dir, pdf_dir): row for row in rows
        }
        for future in as_completed(futures):
            results.append(future.result())

    if failures_path is not None:
        failures = [
            {
                "drug_id": r.drug_id,
                "status": r.status.value,
                "http_status": r.http_status,
                "error": r.error,
            }
            for r in results
            if r.status in {FetchStatus.NOT_FOUND, FetchStatus.INVALID, FetchStatus.ERROR}
        ]
        failures_path.parent.mkdir(parents=True, exist_ok=True)
        failures_path.write_text(
            "\n".join(json.dumps(f, ensure_ascii=False) for f in failures) + "\n",
            encoding="utf-8",
        )

    return results
