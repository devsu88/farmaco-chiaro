"""Test del smoke test con un fetch finto: nessuna rete, nessun LLM."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "smoke.py"
spec = importlib.util.spec_from_file_location("smoke_script", SCRIPT)
assert spec and spec.loader
smoke = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = smoke
spec.loader.exec_module(smoke)


def make_fetch(*, old_chat: bool = False, qdrant: bool = True, commit: str = "abc123"):
    def fetch(method: str, url: str, payload: dict | None, timeout: float):
        path = urlparse(url).path
        headers = {"x-request-id": "req-1"}
        if path == "/health":
            return 200, headers, json.dumps({"status": "healthy", "commit": commit}).encode()
        if path == "/api/rag/status":
            body = {
                "farmaci": 621,
                "qdrant": {"available": qdrant},
            }
            return 200, headers, json.dumps(body).encode()
        if path in (
            "/api/farmaco/012745_01",
            "/api/farmaci/012745_01",
            "/farmaco/012745_01",
        ):
            return 200, headers, b"ok"
        if path == "/api/chat":
            if old_chat:
                return 200, headers, b'{"risposta": "vecchia"}'
            message = (payload or {}).get("messaggio", "")
            return (422 if not message or len(message) > 1000 else 200), headers, b"{}"
        return 404, headers, b"{}"

    return fetch


def test_scenario_sano_tutti_verdi():
    results = smoke.run_checks(fetch=make_fetch())
    assert all(result.ok for result in results)
    health = next(result for result in results if result.name == "health")
    assert health.detail == "status=200 commit=abc123"


def test_backend_vecchio_fa_fallire_i_limiti():
    results = smoke.run_checks(fetch=make_fetch(old_chat=True))
    chat = {result.name: result for result in results if result.name.startswith("chat_")}
    assert chat["chat_vuoto"].ok is False
    assert "backend vecchio" in chat["chat_vuoto"].detail
    assert chat["chat_lungo"].ok is False


def test_qdrant_giu_e_un_warning_non_un_errore():
    results = smoke.run_checks(fetch=make_fetch(qdrant=False))
    rag = next(result for result in results if result.name == "rag_status")
    assert rag.ok is True
    assert rag.warning is True
    assert all(result.ok for result in results)


def test_require_commit_fallisce_su_unknown():
    results = smoke.run_checks(fetch=make_fetch(commit="unknown"), require_commit=True)
    health = next(result for result in results if result.name == "health")
    assert health.ok is False
    assert "commit richiesto" in health.detail


def test_senza_require_commit_unknown_e_solo_warning():
    results = smoke.run_checks(fetch=make_fetch(commit="unknown"))
    health = next(result for result in results if result.name == "health")
    assert health.ok is True
    assert health.warning is True


def test_backend_only_usa_il_path_interno_e_salta_la_pagina():
    results = smoke.run_checks(fetch=make_fetch(), backend_only=True)
    names = {result.name for result in results}
    assert "farmaco_page" not in names
    assert "farmaco_api" in names
    assert all(result.ok for result in results)
