"""Test degli scenari "Cosa faccio se...?"."""
from __future__ import annotations

import re

import pytest

from services.scenari import elenco_scenari, risolvi_scenario


def test_elenco_scenari_contiene_i_quattro_della_demo():
    ids = [scenario["id"] for scenario in elenco_scenari()]
    assert ids == [
        "dose_dimenticata",
        "dose_doppia",
        "reazione_avversa",
        "alcol",
    ]


def test_dimenticanza_augmentin_cita_la_regola_della_dose():
    risultato = risolvi_scenario("dose_dimenticata", "augmentin")
    assert risultato["trovato"] is True
    assert "dose" in risultato["risposta"].lower()
    assert risultato["fonti"]
    assert risultato["azione"]


def test_alcol_moment_trova_il_paragrafo_sull_alcol():
    risultato = risolvi_scenario("alcol", "moment")
    assert risultato["trovato"] is True
    assert "alcool" in risultato["risposta"].lower()
    assert risultato["fonti"][0]["blocco_id"] == "moment_sec5"


def test_reazione_avversa_contiene_un_indicazione_di_urgenza():
    risultato = risolvi_scenario("reazione_avversa", "moment")
    assert risultato["urgenza"] in {"contatta_medico", "emergenza"}
    assert risultato["azione"]


def test_ogni_fonte_e_ancorata_a_un_blocco_reale():
    from services.retrieval import blocchi_per_farmaco

    testi = {blocco["id"]: blocco["testo"] for blocco in blocchi_per_farmaco("plasil")}
    risultato = risolvi_scenario("dose_doppia", "plasil")
    for fonte in risultato["fonti"]:
        assert fonte["testo_evidenziato"] in testi[fonte["blocco_id"]]


@pytest.mark.parametrize("farmaco_id", ["augmentin", "aspirina_500", "plasil"])
def test_dimenticanza_riporta_la_regola_della_dose(farmaco_id):
    risultato = risolvi_scenario("dose_dimenticata", farmaco_id)
    assert risultato["trovato"] is True
    assert "non prenda una dose doppia" in risultato["risposta"].lower()


def test_alcol_plasil_non_cita_un_farmaco_qualsiasi():
    risultato = risolvi_scenario("alcol", "plasil")
    assert risultato["trovato"] is True
    assert "consumare alcol" in risultato["risposta"].lower()
    assert "rifampicina" not in risultato["risposta"].lower()


def test_scenario_inesistente():
    with pytest.raises(KeyError):
        risolvi_scenario("scenario_inesistente", "plasil")


@pytest.mark.parametrize(
    "farmaco_id",
    ["tachipirina_1000", "aspirina_500", "augmentin", "moment", "plasil"],
)
def test_dose_doppia_non_usa_il_blocco_della_dimenticanza(farmaco_id):
    risultato = risolvi_scenario("dose_doppia", farmaco_id)
    assert risultato["trovato"] is True
    testo = risultato["risposta"].lower()
    assert "dimenticanza" not in testo
    assert "compensare" not in testo
    assert any(
        ancora in testo
        for ancora in ("se prende più", "di quanto deve", "overdose")
    )


@pytest.mark.parametrize(
    "farmaco_id",
    ["tachipirina_1000", "aspirina_500", "augmentin", "moment", "plasil"],
)
def test_reazione_avversa_non_cita_l_introduzione(farmaco_id):
    risultato = risolvi_scenario("reazione_avversa", farmaco_id)
    assert risultato["trovato"] is True
    assert risultato["fonti"][0]["blocco_id"] != f"{farmaco_id}_sec0"
    testo = risultato["risposta"].lower()
    assert any(
        parola in testo
        for parola in (
            "reazione",
            "allerg",
            "difficoltà",
            "pronto soccorso",
            "interrompa",
            "contatti",
            "immediatamente",
        )
    ), farmaco_id


def test_reazione_tachipirina_cita_l_istruzione_di_interrompere():
    risultato = risolvi_scenario("reazione_avversa", "tachipirina_1000")
    testo = re.sub(r"\s+", " ", risultato["risposta"].lower())
    assert "interrompa il trattamento" in testo
    assert "contatti immediatamente" in testo


def test_farmaco_inesistente():
    with pytest.raises(KeyError):
        risolvi_scenario("dose_dimenticata", "farmaco_inesistente")
