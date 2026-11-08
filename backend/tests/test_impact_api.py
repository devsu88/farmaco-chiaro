"""Test HTTP dei nuovi endpoint: guida, scenari e scheda."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_guida_endpoint():
    risposta = client.get("/api/farmaci/plasil/guida")
    assert risposta.status_code == 200
    body = risposta.json()
    assert len(body["schermate"]) == 4
    assert body["schermate"][0]["fonti"]


def test_guida_farmaco_inesistente_404():
    assert client.get("/api/farmaci/nope/guida").status_code == 404


def test_elenco_scenari_endpoint():
    risposta = client.get("/api/scenari")
    assert risposta.status_code == 200
    assert len(risposta.json()["scenari"]) == 4


def test_scenario_endpoint():
    risposta = client.post(
        "/api/scenari/alcol",
        json={"farmaco_id": "tachipirina_1000"},
    )
    assert risposta.status_code == 200
    body = risposta.json()
    assert body["trovato"] is True
    assert body["azione"]


def test_scenario_inesistente_404():
    risposta = client.post(
        "/api/scenari/nope",
        json={"farmaco_id": "tachipirina_1000"},
    )
    assert risposta.status_code == 404


def test_scheda_endpoint():
    risposta = client.get("/api/farmaci/moment/scheda")
    assert risposta.status_code == 200
    body = risposta.json()
    assert body["nome"] == "Moment"
    assert body["fonti"]
