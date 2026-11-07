from services.retrieval import cerca, cerca_farmaci, tokenizza


def test_tokenizza_rimuove_stopword():
    termini = tokenizza("Posso prendere questo farmaco per il mal di testa?")
    assert "mal" in termini
    assert "testa" in termini
    assert "per" not in termini


def test_cerca_tachipirina_mal_di_testa():
    risultati = cerca("mal di testa", "tachipirina_1000", limite=5)
    assert risultati
    assert all("blocco_id" in r for r in risultati)
    assert any("testa" in r["testo"].lower() for r in risultati)


def test_cerca_farmaci_restituisce_nome_leggibile():
    risultati = cerca_farmaci("paracetamolo")
    assert risultati
    primo = risultati[0]
    assert primo["id"] == "tachipirina_1000"
    assert primo["nome"] == "Tachipirina 1000 mg"
    assert primo["principio_attivo"] == "paracetamolo"


def test_intento_gravidanza_preferisce_blocchi_specifici():
    risultati = cerca("Posso prenderla se sono incinta?", "aspirina_500", limite=3)
    assert risultati
    titoli = " ".join(r["paragrafo"].lower() for r in risultati)
    assert "gravidanza" in titoli
    assert "trimestre" in titoli


def test_i_blocchi_non_contengono_il_footer_legale():
    risultati = cerca("gravidanza", "aspirina_500", limite=5)
    assert risultati
    for risultato in risultati:
        assert "Agenzia non può essere ritenuta responsabile" not in risultato["testo"]


def test_intento_condivisione_trova_il_blocco_giusto():
    risultati = cerca(
        "Posso dare il farmaco ad un mio parente che soffre lo stesso problema?",
        "plasil",
        limite=3,
    )
    assert risultati
    assert risultati[0]["blocco_id"] == "plasil_sec0"
    assert "Non lo dia ad altre persone" in risultati[0]["testo"]


def test_intento_condivisione_riconosce_i_familiari():
    risultati = cerca(
        "quindi se mia sorella soffre di mal di denti può prenderlo?",
        "augmentin",
        limite=5,
    )
    assert risultati
    assert risultati[0]["blocco_id"] == "augmentin_sec0"
    assert any(r["blocco_id"] == "augmentin_sec2" for r in risultati)
