"""Test della modalità guidata "Una cosa alla volta"."""
from __future__ import annotations

import pytest

from services.guida import guida


def test_guida_restituisce_quattro_schermate_in_ordine():
    risultato = guida("tachipirina_1000")
    assert [schermata["id"] for schermata in risultato["schermate"]] == [
        "a_cosa_serve",
        "come_si_prende",
        "cosa_non_fare",
        "quando_medico",
    ]


def test_ogni_schermata_ha_testo_e_fonte_verificabile():
    risultato = guida("tachipirina_1000")

    for schermata in risultato["schermate"]:
        assert schermata["testi"]
        assert schermata["fonti"]
        for fonte in schermata["fonti"]:
            assert fonte["blocco_id"]
            assert fonte["testo_evidenziato"].strip()


def test_la_fonte_e_una_porzione_esatta_del_blocco():
    from services.retrieval import blocchi_per_farmaco

    testi = {blocco["id"]: blocco["testo"] for blocco in blocchi_per_farmaco("plasil")}
    risultato = guida("plasil")

    for schermata in risultato["schermate"]:
        for fonte in schermata["fonti"]:
            assert fonte["testo_evidenziato"] in testi[fonte["blocco_id"]]


def test_come_si_prende_contiene_la_posologia():
    for farmaco_id in ("tachipirina_1000", "aspirina_500", "augmentin", "moment", "plasil"):
        risultato = guida(farmaco_id)
        schermata = next(
            s for s in risultato["schermate"] if s["id"] == "come_si_prende"
        )
        testo = " ".join(schermata["testi"]).lower()
        assert any(
            parola in testo
            for parola in ("dose", "compress", "mg", "giorno", "ore")
        ), farmaco_id


def test_quando_medico_parla_di_sintomi_o_medico():
    risultato = guida("moment")
    schermata = next(s for s in risultato["schermate"] if s["id"] == "quando_medico")
    testo = " ".join(schermata["testi"]).lower()
    assert any(
        parola in testo
        for parola in ("medico", "farmacista", "immediatamente", "sintomi", "grave")
    )


def test_le_schermate_restano_brevi():
    for farmaco_id in ("tachipirina_1000", "aspirina_500", "augmentin", "moment", "plasil"):
        risultato = guida(farmaco_id)
        for schermata in risultato["schermate"]:
            assert len(" ".join(schermata["testi"])) <= 550, (farmaco_id, schermata["id"])


def test_plasil_indicazione_principale():
    risultato = guida("plasil")
    schermata = next(s for s in risultato["schermate"] if s["id"] == "a_cosa_serve")
    assert "antiemetico" in " ".join(schermata["testi"]).lower()


def test_plasil_posologia_adulti():
    risultato = guida("plasil")
    schermata = next(
        s for s in risultato["schermate"] if s["id"] == "come_si_prende"
    )
    assert "singola dose raccomandata è di 10 mg" in " ".join(
        schermata["testi"]
    ).lower()


def test_riepilogo_ha_una_frase_per_schermata():
    risultato = guida("aspirina_500")
    assert len(risultato["riepilogo"]) == 4
    assert all(frase for frase in risultato["riepilogo"])


def test_guida_farmaco_inesistente():
    with pytest.raises(KeyError):
        guida("farmaco_inesistente")
