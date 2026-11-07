from graph.chat_graph import dopo_recupero, nodo_retrieval


def test_retrieval_usa_la_query_originale():
    state = {
        "messaggi": [
            {"ruolo": "utente", "testo": "Posso prenderlo se ho il mal di testa?"}
        ],
        "farmaco_id": "tachipirina_1000",
    }
    risultato = nodo_retrieval(state)
    candidati = risultato["candidati_retrieval"]
    assert candidati
    assert candidati[0]["sezione"] == "Che cos’ è Tachipirina e a cosa serve"


def test_senza_candidati_si_espande_la_query():
    assert dopo_recupero({"candidati_retrieval": []}) == "espandi"
    assert dopo_recupero({"candidati_retrieval": [{"blocco_id": "x"}]}) == "genera"
