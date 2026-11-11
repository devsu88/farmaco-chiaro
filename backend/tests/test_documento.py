from services.documento import documento


def test_documento_tachipirina_citabile():
    risultato = documento("012745_01")
    assert risultato["documento"].startswith("Foglio illustrativo TACHIPIRINA")
    assert risultato["sezioni"]
    blocchi = [
        blocco
        for sezione in risultato["sezioni"]
        for blocco in sezione["blocchi"]
    ]
    assert blocchi
    assert all(blocco["blocco_id"] for blocco in blocchi)
    assert all(blocco["testo"].strip() for blocco in blocchi)


def test_blocco_id_stabile_e_univoco():
    risultato = documento("012745_01")
    ids = [
        blocco["blocco_id"]
        for sezione in risultato["sezioni"]
        for blocco in sezione["blocchi"]
    ]
    assert len(ids) == len(set(ids))
    assert all(blocco_id.startswith("012745_01_") for blocco_id in ids)
