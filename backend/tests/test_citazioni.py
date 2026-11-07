from services.citazioni import (
    affina_span,
    estrai_estratto,
    filtra_fonti,
    fonte_da_blocco,
    valida_fonte,
)

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


def test_affina_span_restituisce_la_frase_pertinente():
    blocco = (
        "Foglio illustrativo: informazioni per il paziente\n\n"
        "- Conservi questo foglio. Potrebbe aver bisogno di leggerlo di nuovo.\n"
        "- Questo medicinale è stato prescritto soltanto per lei. "
        "Non lo dia ad altre persone, anche se i sintomi della malattia sono "
        "uguali ai suoi, perché potrebbe essere pericoloso.\n"
        "- Se ha qualsiasi dubbio, si rivolga al medico."
    )
    span = affina_span(
        blocco,
        blocco,
        query="Posso darlo a un mio parente con gli stessi sintomi?",
        risposta="No, non deve darlo ad altre persone con gli stessi sintomi.",
    )
    assert "Non lo dia ad altre persone" in span
    assert len(span) < len(blocco)


def test_estrai_estratto_trova_la_parte_pertinente():
    blocco = "\n\n".join(
        [
            "Reazioni allergiche comuni: eruzioni cutanee e prurito.",
            "Dolore toracico nel contesto di reazioni allergiche, "
            "che può essere un sintomo di infarto cardiaco (sindrome di Kounis).",
            "Conservare il medicinale fuori dalla portata dei bambini.",
        ]
    )
    estratto = estrai_estratto(blocco, "ho problemi al cuore", max_caratteri=200)
    assert "Kounis" in estratto
    assert "bambini" not in estratto


def test_filtra_fonti_scarta_le_fonti_poco_pertinenti():
    fonti = [
        {
            "testo_evidenziato": "Non lo dia ad altre persone con gli stessi sintomi.",
        },
        {
            "testo_evidenziato": "Conservi il medicinale fuori dalla vista dei bambini.",
        },
    ]
    filtrate = filtra_fonti(fonti, "Non deve darlo ad altre persone con gli stessi sintomi.")
    assert filtrate == fonti[:1]
