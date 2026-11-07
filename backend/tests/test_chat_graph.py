from graph.chat_graph import (
    _is_meta_domanda,
    dopo_generazione,
    dopo_recupero,
    dopo_riscrittura,
    nodo_retrieval,
)


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
    assert (
        dopo_recupero({"candidati_retrieval": [{"blocco_id": "x", "score": 3.0}]})
        == "genera"
    )
    assert (
        dopo_recupero({"candidati_retrieval": [{"blocco_id": "x", "score": 1.0}]})
        == "espandi"
    )


def test_riconosce_domande_sulla_conversazione():
    assert _is_meta_domanda("ti ho già chiesto sullo stomaco?")
    assert _is_meta_domanda("riassumi la conversazione")
    assert not _is_meta_domanda("posso prenderlo con il mal di testa?")


def test_dopo_riscrittura_e_dopo_generazione():
    assert dopo_riscrittura({"domanda_meta": True}) == "meta"
    assert dopo_riscrittura({"domanda_meta": False}) == "recupera"
    assert dopo_generazione({"informazione_trovata": True}) == "fine"
    assert dopo_generazione({"informazione_trovata": False}) == "fallback"
