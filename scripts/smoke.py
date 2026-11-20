#!/usr/bin/env python3
"""Smoke test di produzione senza chiamate valide all'LLM.

Verifica la release, il dataset, la pagina farmaco e i limiti di input. Le
uniche richieste a /api/chat sono volutamente invalide (422), quindi non
consumano quota del provider.
"""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

DEFAULT_BASE_URL = "https://farmaco-chiaro.vercel.app"
DEFAULT_TIMEOUT = 15.0
FARMACO = "012745_01"


@dataclass
class Result:
    name: str
    ok: bool
    detail: str = ""
    warning: bool = False


def _request(method: str, url: str, payload: dict | None, timeout: float):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, _headers(response.headers), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, _headers(exc.headers), exc.read()


def _headers(raw) -> dict[str, str]:
    return {key.lower(): value for key, value in raw.items()}


def _json(body: bytes) -> dict:
    try:
        value = json.loads(body or b"{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def run_checks(
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    require_commit: bool = False,
    backend_only: bool = False,
    fetch=_request,
) -> list[Result]:
    base = base_url.rstrip("/")
    results: list[Result] = []

    def get(path: str):
        return fetch("GET", base + path, None, timeout)

    def post(path: str, payload: dict):
        return fetch("POST", base + path, payload, timeout)

    # 1. Release identity.
    try:
        status, _, body = get("/health")
        data = _json(body)
        commit = str(data.get("commit", "unknown"))
        unknown = commit == "unknown"
        ok = status == 200 and data.get("status") == "healthy"
        detail = f"status={status} commit={commit}"
        if require_commit and unknown:
            ok = False
            detail += " (commit richiesto)"
        results.append(Result("health", ok, detail, warning=unknown and ok))
    except Exception as exc:
        results.append(Result("health", False, f"{type(exc).__name__}: {exc}"))

    # 2. Dataset and Qdrant.
    try:
        status, _, body = get("/api/rag/status")
        data = _json(body)
        qdrant = data.get("qdrant") or {}
        farmaci = int(data.get("farmaci") or 0)
        available = bool(qdrant.get("available"))
        results.append(
            Result(
                "rag_status",
                status == 200 and farmaci > 0,
                f"status={status} farmaci={farmaci} qdrant={available}",
                warning=not available,
            )
        )
    except Exception as exc:
        results.append(Result("rag_status", False, f"{type(exc).__name__}: {exc}"))

    # 3-4. Public app routes (or the internal backend route in --backend mode).
    farmaco_path = (
        f"/api/farmaci/{FARMACO}" if backend_only else f"/api/farmaco/{FARMACO}"
    )
    checks = [("farmaco_api", farmaco_path)]
    if not backend_only:
        checks.append(("farmaco_page", f"/farmaco/{FARMACO}"))
    for name, path in checks:
        try:
            status, _, _ = get(path)
            results.append(Result(name, status == 200, f"status={status}"))
        except Exception as exc:
            results.append(Result(name, False, f"{type(exc).__name__}: {exc}"))

    # 5. Request id on a normal response.
    try:
        status, headers, _ = get("/api/rag/status")
        request_id = headers.get("x-request-id", "")
        results.append(
            Result(
                "request_id",
                status == 200 and bool(request_id),
                f"x-request-id={request_id or 'assente'}",
            )
        )
    except Exception as exc:
        results.append(Result("request_id", False, f"{type(exc).__name__}: {exc}"))

    # 6-7. Input limits: invalid requests only, no LLM call.
    for name, message in (("chat_vuoto", ""), ("chat_lungo", "x" * 1001)):
        try:
            status, _, _ = post(
                "/api/chat",
                {"farmaco_id": FARMACO, "messaggio": message, "storico": []},
            )
            detail = f"status={status}"
            if status == 200:
                detail += " (backend vecchio: nessun limite)"
            results.append(Result(name, status == 422, detail))
        except Exception as exc:
            results.append(Result(name, False, f"{type(exc).__name__}: {exc}"))

    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke test di Farmaco Chiaro")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--require-commit",
        action="store_true",
        help="fallisce se /health non espone il commit SHA",
    )
    parser.add_argument(
        "--backend",
        action="store_true",
        help="verifica un backend locale: usa /api/farmaci e salta la pagina",
    )
    args = parser.parse_args(argv)

    results = run_checks(
        base_url=args.base_url,
        timeout=args.timeout,
        require_commit=args.require_commit,
        backend_only=args.backend,
    )

    for result in results:
        mark = "FAIL" if not result.ok else ("warn" if result.warning else "ok")
        print(f"[{mark}] {result.name}: {result.detail}")

    failures = [result for result in results if not result.ok]
    if failures:
        print(f"\n{len(failures)} check falliti su {len(results)}")
        return 1
    print(f"\n{len(results)} check superati")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
