from services.citazioni import fonte_da_blocco, valida_fonte

BLOCCO = {
    "blocco_id": "test_sec0",
    "documento": "Foglio illustrativo Test – AIFA",
    "sezione": "Posologia",
    "paragrafo": "1",
    "testo": "La dose raccomandata è 1 compressa fino a 3 volte al giorno.",
}


def test_fonte_da_blocco_e_verificata():
    fonte = fonte_da_blocco(BLOCCO)
    assert fonte["blocco_id"] == "test_sec0"
    assert fonte["verificata"] is True
    assert fonte["testo_evidenziato"] == BLOCCO["testo"]


def test_valida_fonte_accetta_span_reale():
    fonte = valida_fonte(
        {"blocco_id": "test_sec0", "testo_evidenziato": "1 compressa"}, [BLOCCO]
    )
    assert fonte is not None
    assert fonte["verificata"] is True


def test_valida_fonte_rifiuta_span_inventato():
    fonte = valida_fonte(
        {"blocco_id": "test_sec0", "testo_evidenziato": "5 compresse al giorno"},
        [BLOCCO],
    )
    assert fonte is None
