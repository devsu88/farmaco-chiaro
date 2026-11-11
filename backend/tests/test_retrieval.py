from services.retrieval import _fuse_rrf, cerca, cerca_farmaci, reset_cache, tokenizza


def test_tokenizza_rimuove_stopword():
    termini = tokenizza("Posso prendere questo farmaco per il mal di testa?")
    assert "mal" in termini
    assert "testa" in termini
    assert "per" not in termini


def test_cerca_tachipirina_mal_di_testa():
    risultati = cerca("mal di testa", "012745_01", limite=5)
    assert risultati
    assert all("blocco_id" in r for r in risultati)
    assert any("testa" in r["testo"].lower() for r in risultati)


def test_cerca_farmaci_restituisce_nome_leggibile():
    risultati = cerca_farmaci("tachipirina 1000 mg compresse")
    assert risultati
    primo = risultati[0]
    assert primo["id"] == "012745_01"
    assert primo["nome"] == "TACHIPIRINA 1000 mg compresse"
    assert primo["principio_attivo"] == "PARACETAMOLO"


def test_cerca_farmaci_query_vuota():
    assert cerca_farmaci("   ") == []


def test_intento_gravidanza_preferisce_blocchi_specifici():
    risultati = cerca("Posso prenderla se sono incinta?", "004763_01", limite=5)
    assert risultati
    titoli = " ".join(r["paragrafo"].lower() for r in risultati)
    assert "gravidanza" in titoli
    assert "trimestre" in titoli


def test_i_blocchi_non_contengono_il_footer_legale():
    risultati = cerca("gravidanza", "004763_01", limite=5)
    assert risultati
    for risultato in risultati:
        assert "Agenzia non può essere ritenuta responsabile" not in risultato["testo"]


def test_fusione_rrf_combina_bm25_e_denso():
    bm25 = [
        {"blocco_id": "004763_01_2_07", "score_bm25": 4.0, "score_dense": 0},
        {"blocco_id": "004763_01_2_06", "score_bm25": 2.0, "score_dense": 0},
    ]
    denso = [
        {"blocco_id": "004763_01_2_07", "score_dense": 0.9},
        {"blocco_id": "004763_01_2_05", "score_dense": 0.8},
    ]
    risultati = _fuse_rrf(bm25, denso, limite=3)
    assert risultati[0]["blocco_id"] == "004763_01_2_07"
    assert {r["blocco_id"] for r in risultati} == {
        "004763_01_2_07",
        "004763_01_2_06",
        "004763_01_2_05",
    }
    assert all("score_rrf" in r for r in risultati)


def test_cerca_usa_il_semantico_come_primario(monkeypatch):
    sentinella = {
        "blocco_id": "012745_01_1_00",
        "farmaco_id": "012745_01",
        "documento": "Foglio illustrativo",
        "sezione": "Indicazioni",
        "paragrafo": "Indicazioni",
        "testo": "Indicato per il dolore.",
        "score": 1.0,
    }
    chiamate = []

    def fake_dense(query, farmaco_id, limite):
        chiamate.append((query, farmaco_id, limite))
        return [sentinella]

    monkeypatch.setattr("services.retrieval.RETRIEVAL_MODE", "semantic")
    monkeypatch.setattr("services.retrieval._dense_results", fake_dense)

    assert cerca("mal di testa", "012745_01", limite=3) == [sentinella]
    assert chiamate[0][1] == "012745_01"
    # La query semantica usa i sinonimi clinici (testa -> cefalea).
    assert "cefalea" in chiamate[0][0]


def test_cerca_ripiega_su_bm25_senza_semantico(monkeypatch):
    monkeypatch.setattr("services.retrieval.RETRIEVAL_MODE", "semantic")
    monkeypatch.setattr("services.retrieval._dense_results", lambda *a, **k: [])
    risultati = cerca("alcol", "020766_02", limite=3)
    assert risultati
    assert all("blocco_id" in risultato for risultato in risultati)


def test_cerca_farmaci_fonde_semantica_e_parole_chiave(monkeypatch):
    monkeypatch.setattr("services.retrieval.RETRIEVAL_MODE", "semantic")
    monkeypatch.setattr(
        "services.vector_store.query_dense",
        lambda *a, **k: [{"farmaco_id": "049580_01", "score_dense": 0.9}],
    )

    risultati = cerca_farmaci("tachipirina 1000 mg compresse")
    ids = [risultato["id"] for risultato in risultati]
    assert ids[0] == "012745_01"
    assert "049580_01" in ids
    semantico = next(r for r in risultati if r["id"] == "049580_01")
    assert "semantica" in semantico["motivo"]


def test_cerca_farmaci_semantica_aggiunge_farmaci_non_lessicali(monkeypatch):
    monkeypatch.setattr("services.retrieval.RETRIEVAL_MODE", "semantic")
    monkeypatch.setattr("services.retrieval._farmaci_lessicali", lambda query: [])
    monkeypatch.setattr(
        "services.vector_store.query_dense",
        lambda *a, **k: [{"farmaco_id": "025669_01", "score_dense": 0.8}],
    )
    assert [r["id"] for r in cerca_farmaci("qualcosa")] == ["025669_01"]


def test_reset_cache_ricarica_gli_artefatti():
    assert cerca("alcol", "020766_02", limite=1)
    reset_cache()
    assert cerca("alcol", "020766_02", limite=1)
