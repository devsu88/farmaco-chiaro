"""Identità della release esposta da /health."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.version import COMMIT_SHA

client = TestClient(app)


def test_health_resta_compatibile_e_espone_la_release():
    risposta = client.get("/health")
    assert risposta.status_code == 200
    corpo = risposta.json()
    assert corpo["status"] == "healthy"
    assert corpo["commit"] == COMMIT_SHA
    assert corpo["built_at"]
    assert corpo["commit"]


def test_commit_non_e_mai_vuoto():
    assert COMMIT_SHA.strip()
