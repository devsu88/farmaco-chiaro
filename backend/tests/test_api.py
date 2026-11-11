from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_e_ready():
    assert client.get("/health").status_code == 200
    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["farmaci"] == 621


def test_lista_farmaci_rimossa():
    assert client.get("/api/farmaci").status_code in {404, 405}


def test_dettaglio_e_documento():
    dettaglio = client.get("/api/farmaci/012745_01")
    assert dettaglio.status_code == 200
    assert dettaglio.json()["nome"] == "TACHIPIRINA 1000 mg compresse"
    assert "sezioni" in dettaglio.json()

    documento = client.get("/api/farmaci/012745_01/documento")
    assert documento.status_code == 200
    assert documento.json()["sezioni"]


def test_dettaglio_inesistente():
    assert client.get("/api/farmaci/nope").status_code == 404


def test_ricerca_restituisce_nome():
    risposta = client.get(
        "/api/search", params={"q": "tachipirina 1000 mg compresse"}
    )
    assert risposta.status_code == 200
    risultati = risposta.json()["risultati"]
    assert risultati
    assert risultati[0]["id"] == "012745_01"


def test_rag_status():
    corpo = client.get("/api/rag/status").json()
    assert corpo["farmaci"] == 621
    assert corpo["mode"] == "bm25"
    assert "qdrant" in corpo


def test_chat_senza_api_key_restituisce_sessione_uuid(monkeypatch):
    monkeypatch.setattr("app.routes.chat.has_valid_api_key", lambda: False)
    risposta = client.post(
        "/api/chat",
        json={
            "farmaco_id": "012745_01",
            "messaggio": "Posso prenderlo con il mal di testa?",
            "storico": [],
        },
    )
    assert risposta.status_code == 200
    body = risposta.json()
    assert body["sessione_id"] != "default"
    assert body["fallback_usato"] is True


def test_simplify_senza_api_key_restituisce_fallback(monkeypatch):
    monkeypatch.setattr("app.routes.simplify.has_valid_api_key", lambda: False)
    risposta = client.post(
        "/api/simplify",
        json={"farmaco_id": "012745_01", "testo": "Testo di prova."},
    )
    assert risposta.status_code == 200
    assert risposta.json()["errore"]
