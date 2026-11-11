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
    testo = " ".join(schermata["testi"]).lower()
    assert "nausea" in testo or "vomito" in testo


def test_riepilogo_ha_una_frase_per_schermata():
    risultato = guida("004763_01")
    assert len(risultato["riepilogo"]) == 4
    assert all(frase for frase in risultato["riepilogo"])


def test_tachifenekid_ha_quattro_schermate_corrette():
    risultato = guida("049580_01")
    per_id = {schermata["id"]: schermata["testi"][0] for schermata in risultato["schermate"]}

    assert len(per_id) == 4
    assert "dolore" in per_id["a_cosa_serve"].lower()
    assert "4-6 ore" in per_id["come_si_prende"].lower()
    assert "glicole" not in per_id["come_si_prende"].lower()
    assert "non usi" in per_id["cosa_non_fare"].lower()
    assert "medico" in per_id["quando_medico"].lower()


def test_come_si_prende_parte_dalla_dose_non_dalle_avvertenze():
    risultato = guida("012745_05")
    schermata = next(s for s in risultato["schermate"] if s["id"] == "come_si_prende")
    testo = schermata["testi"][0].lower()
    assert "dose definita" in testo
    assert "insufficienza renale" not in testo


def test_guida_usa_il_retrieval_semantico(monkeypatch):
    chiamate = []

    def fake_cerca(query, farmaco_id, limite=5, **kwargs):
        chiamate.append((query, farmaco_id))
        return []

    monkeypatch.setattr("services.guida.cerca", fake_cerca)
    risultato = guida("012745_01")

    # Anche senza risultati semantici la guida resta completa grazie al fallback.
    assert len(risultato["schermate"]) == 4
    assert len(chiamate) == 4
    assert all(farmaco_id == "012745_01" for _, farmaco_id in chiamate)
    assert any("come si prende" in query for query, _ in chiamate)


def test_guida_farmaco_inesistente():
    with pytest.raises(KeyError):
        guida("farmaco_inesistente")
