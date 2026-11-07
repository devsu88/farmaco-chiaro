from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_e_ready():
    assert client.get("/health").status_code == 200
    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["farmaci"] == 5


def test_lista_farmaci():
    risposta = client.get("/api/farmaci")
    assert risposta.status_code == 200
    assert len(risposta.json()) == 5


def test_dettaglio_e_documento():
    dettaglio = client.get("/api/farmaci/tachipirina_1000")
    assert dettaglio.status_code == 200
    assert "sezioni" in dettaglio.json()

    documento = client.get("/api/farmaci/tachipirina_1000/documento")
    assert documento.status_code == 200
    assert documento.json()["sezioni"]


def test_ricerca_restituisce_nome():
    risposta = client.get("/api/search", params={"q": "paracetamolo"})
    assert risposta.status_code == 200
    risultati = risposta.json()["risultati"]
    assert risultati
    assert risultati[0]["nome"] == "Tachipirina 1000 mg"


def test_chat_senza_api_key_restituisce_sessione_uuid(monkeypatch):
    monkeypatch.setattr("app.routes.chat.has_valid_api_key", lambda: False)
    risposta = client.post(
        "/api/chat",
        json={
            "farmaco_id": "tachipirina_1000",
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
        json={"farmaco_id": "tachipirina_1000", "testo": "Testo di prova."},
    )
    assert risposta.status_code == 200
    assert risposta.json()["errore"]
