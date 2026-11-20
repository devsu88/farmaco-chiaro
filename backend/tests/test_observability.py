"""Request id e log strutturati: header presente, JSON parsabile, no contenuti."""
from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_ogni_risposta_ha_un_request_id():
    risposta = client.get("/health")
    assert risposta.status_code == 200
    assert risposta.headers.get("x-request-id")


def test_endpoint_caldo_logga_json_senza_contenuto(monkeypatch, caplog):
    monkeypatch.setattr("app.routes.chat.has_valid_api_key", lambda: False)
    caplog.set_level(logging.INFO, logger="app.observability")

    segreto = "TESTO-CHE-NON-DEVE-FINIRE-NEI-LOG"
    risposta = client.post(
        "/api/chat",
        json={
            "farmaco_id": "012745_01",
            "messaggio": segreto,
            "storico": [],
        },
        headers={"x-forwarded-for": "203.0.113.9"},
    )
    assert risposta.status_code == 200

    eventi = []
    for record in caplog.records:
        if record.name != "app.observability":
            continue
        try:
            eventi.append(json.loads(record.getMessage()))
        except json.JSONDecodeError:
            continue

    http_request = next(evento for evento in eventi if evento["event"] == "http_request")
    assert http_request["path"] == "/api/chat"
    assert http_request["status"] == 200
    assert isinstance(http_request["duration_ms"], (int, float))
    assert http_request["request_id"] == risposta.headers["x-request-id"]
    assert http_request["client_hash"] != "203.0.113.9"
    assert "203.0.113.9" not in json.dumps(eventi)
    assert segreto not in json.dumps(eventi)


def test_rate_limit_logga_un_evento(monkeypatch, caplog):
    from app.rate_limit import LIMITS, Limit, limiter

    monkeypatch.setattr("app.routes.chat.has_valid_api_key", lambda: False)
    monkeypatch.setitem(LIMITS, "chat", Limit(1, 60))
    limiter.reset()
    caplog.set_level(logging.INFO, logger="app.observability")

    client.post("/api/chat", json={"farmaco_id": "012745_01", "messaggio": "x", "storico": []})
    seconda = client.post(
        "/api/chat", json={"farmaco_id": "012745_01", "messaggio": "x", "storico": []}
    )
    assert seconda.status_code == 429

    eventi = []
    for record in caplog.records:
        if record.name != "app.observability":
            continue
        try:
            eventi.append(json.loads(record.getMessage()))
        except json.JSONDecodeError:
            continue

    rate_limited = next(evento for evento in eventi if evento["event"] == "rate_limited")
    assert rate_limited["bucket"] == "chat"
    assert rate_limited["retry_after"] >= 1
