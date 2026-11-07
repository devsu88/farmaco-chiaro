from services.documento import documento


def test_documento_tachipirina_citabile():
    risultato = documento("tachipirina_1000")
    assert risultato["documento"].startswith("Foglio illustrativo Tachipirina")
    assert risultato["sezioni"]
    blocchi = [
        blocco
        for sezione in risultato["sezioni"]
        for blocco in sezione["blocchi"]
    ]
    assert blocchi
    assert all(blocco["blocco_id"] for blocco in blocchi)
    assert all(blocco["testo"].strip() for blocco in blocchi)
