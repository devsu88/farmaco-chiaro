"""Test della modalità guidata "Una cosa alla volta"."""
from __future__ import annotations

import pytest

from services.guida import guida

FARMACI = ["012745_01", "004763_01", "026089_01", "025669_01", "020766_02"]


def test_guida_restituisce_quattro_schermate_in_ordine():
    risultato = guida("012745_01")
    assert [schermata["id"] for schermata in risultato["schermate"]] == [
        "a_cosa_serve",
        "come_si_prende",
        "cosa_non_fare",
        "quando_medico",
    ]


def test_ogni_schermata_ha_testo_e_fonte_verificabile():
    risultato = guida("012745_01")

    for schermata in risultato["schermate"]:
        assert schermata["testi"]
        assert schermata["fonti"]
        for fonte in schermata["fonti"]:
            assert fonte["blocco_id"]
            assert fonte["testo_evidenziato"].strip()


def test_la_fonte_e_una_porzione_esatta_del_blocco():
    from services.retrieval import blocchi_per_farmaco

    testi = {
        blocco["blocco_id"]: blocco["testo"]
        for blocco in blocchi_per_farmaco("020766_02")
    }
    risultato = guida("020766_02")

    for schermata in risultato["schermate"]:
        for fonte in schermata["fonti"]:
            assert fonte["testo_evidenziato"] in testi[fonte["blocco_id"]]


def test_come_si_prende_contiene_la_posologia():
    for farmaco_id in FARMACI:
        risultato = guida(farmaco_id)
        schermata = next(
            s for s in risultato["schermate"] if s["id"] == "come_si_prende"
        )
        testo = " ".join(schermata["testi"]).lower()
        assert any(
            parola in testo
            for parola in ("dose", "compress", "mg", "giorno", "ore")
        ), farmaco_id


@pytest.mark.parametrize("farmaco_id", FARMACI)
def test_quando_medico_contiene_un_indicazione_operativa(farmaco_id):
    risultato = guida(farmaco_id)
    schermata = next(
        s for s in risultato["schermate"] if s["id"] == "quando_medico"
    )
    testo = " ".join(schermata["testi"]).lower()
    assert any(
        parola in testo
        for parola in (
            "medico",
            "farmacista",
            "immediatamente",
            "pronto soccorso",
            "112",
            "interrompa",
            "contatti",
        )
    ), farmaco_id


def test_riepilogo_contiene_la_dose_principale():
    risultato = guida("020766_02")
    assert "10 mg" in risultato["riepilogo"][1].lower()


@pytest.mark.parametrize("farmaco_id", FARMACI)
def test_le_schermate_restano_brevi(farmaco_id):
    risultato = guida(farmaco_id)
    for schermata in risultato["schermate"]:
        assert len(" ".join(schermata["testi"])) <= 550, (farmaco_id, schermata["id"])


def test_plasil_indicazione_principale():
    risultato = guida("020766_02")
    schermata = next(s for s in risultato["schermate"] if s["id"] == "a_cosa_serve")
    assert "antiemetico" in " ".join(schermata["testi"]).lower()


def test_riepilogo_ha_una_frase_per_schermata():
    risultato = guida("004763_01")
    assert len(risultato["riepilogo"]) == 4
    assert all(frase for frase in risultato["riepilogo"])


def test_guida_farmaco_inesistente():
    with pytest.raises(KeyError):
        guida("farmaco_inesistente")
