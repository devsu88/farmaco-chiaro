"""Limiti di input e rate limit sugli endpoint costosi.

I test sono deterministici: non chiamano OpenRouter e forzano
`RETRIEVAL_MODE=bm25` tramite `conftest.py`.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
FARMACO = "012745_01"


@pytest.fixture(autouse=True)
def _senza_provider(monkeypatch):
    """Nessun test di questo file deve chiamare OpenRouter."""
    monkeypatch.setattr("app.routes.chat.has_valid_api_key", lambda: False)
    monkeypatch.setattr("app.routes.simplify.has_valid_api_key", lambda: False)


def _chat(**overrides):
    payload = {
        "farmaco_id": FARMACO,
        "messaggio": "Posso prenderlo con il mal di testa?",
        "storico": [],
    }
    payload.update(overrides)
    return payload


def test_messaggio_troppo_lungo_rifiutato():
    risposta = client.post("/api/chat", json=_chat(messaggio="x" * 1001))
    assert risposta.status_code == 422


def test_storico_troppo_lungo_rifiutato():
    storico = [{"ruolo": "utente", "testo": "domanda"} for _ in range(11)]
    risposta = client.post("/api/chat", json=_chat(storico=storico))
    assert risposta.status_code == 422


def test_messaggio_storico_troppo_lungo_rifiutato():
    storico = [{"ruolo": "utente", "testo": "x" * 2001}]
    risposta = client.post("/api/chat", json=_chat(storico=storico))
    assert risposta.status_code == 422


def test_messaggio_di_soli_spazi_rifiutato():
    risposta = client.post("/api/chat", json=_chat(messaggio="   "))
    assert risposta.status_code == 422


def test_testo_simplify_troppo_lungo_rifiutato():
    risposta = client.post(
        "/api/simplify",
        json={"farmaco_id": FARMACO, "testo": "x" * 12001},
    )
    assert risposta.status_code == 422


def test_ricerca_troppo_lunga_rifiutata():
    risposta = client.get("/api/search", params={"q": "x" * 201})
    assert risposta.status_code == 422


def test_corpo_troppo_grande_rifiutato(monkeypatch):
    monkeypatch.setattr("app.config.MAX_REQUEST_BYTES", 10)
    risposta = client.post("/api/chat", json=_chat())
    assert risposta.status_code == 413


def test_richiesta_normale_non_viene_rifiutata(monkeypatch):
    monkeypatch.setattr("app.routes.chat.has_valid_api_key", lambda: False)
    risposta = client.post("/api/chat", json=_chat())
    assert risposta.status_code == 200


def test_rate_limit_chat_restituisce_429(monkeypatch):
    from app.rate_limit import LIMITS, Limit, limiter

    monkeypatch.setitem(LIMITS, "chat", Limit(1, 60))
    limiter.reset()

    prima = client.post("/api/chat", json=_chat())
    seconda = client.post("/api/chat", json=_chat())

    assert prima.status_code != 429
    assert seconda.status_code == 429
    assert seconda.headers["retry-after"].isdigit()
    assert "Troppe richieste" in seconda.json()["detail"]


def test_rate_limit_separa_le_chiavi(monkeypatch):
    from app.rate_limit import LIMITS, Limit, limiter

    monkeypatch.setitem(LIMITS, "chat", Limit(1, 60))
    limiter.reset()

    headers_a = {"x-forwarded-for": "203.0.113.1"}
    headers_b = {"x-forwarded-for": "203.0.113.2"}

    assert client.post("/api/chat", json=_chat(), headers=headers_a).status_code != 429
    assert client.post("/api/chat", json=_chat(), headers=headers_b).status_code != 429
    assert client.post("/api/chat", json=_chat(), headers=headers_a).status_code == 429
