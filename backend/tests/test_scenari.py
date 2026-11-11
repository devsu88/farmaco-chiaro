"""Test degli scenari "Cosa faccio se...?"."""
from __future__ import annotations

import pytest

from services.scenari import elenco_scenari, risolvi_scenario

FARMACI = ["012745_01", "004763_01", "026089_01", "025669_01", "020766_02"]


def test_elenco_scenari_contiene_i_quattro_della_demo():
    ids = [scenario["id"] for scenario in elenco_scenari()]
    assert ids == [
        "dose_dimenticata",
        "dose_doppia",
        "reazione_avversa",
        "alcol",
    ]


@pytest.mark.parametrize("farmaco_id", FARMACI)
def test_dimenticanza_trova_la_regola_della_dose(farmaco_id):
    risultato = risolvi_scenario("dose_dimenticata", farmaco_id)
    assert risultato["trovato"] is True
    assert "dose doppia" in risultato["risposta"].lower()
    assert risultato["fonti"]
    assert risultato["azione"]


def test_dose_doppia_moment_trova_il_sovradosaggio():
    risultato = risolvi_scenario("dose_doppia", "025669_01")
    assert risultato["trovato"] is True
    assert risultato["fonti"][0]["blocco_id"] == "025669_01_3_01"
    assert "se ha preso più" in risultato["risposta"].lower()


@pytest.mark.parametrize(
    "farmaco_id", ["012745_01", "004763_01", "026089_01", "020766_02"]
)
def test_dose_doppia_senza_ancora_resta_un_fallback_esplicito(farmaco_id):
    risultato = risolvi_scenario("dose_doppia", farmaco_id)
    assert risultato["trovato"] is False
    assert risultato["fonti"] == []
    assert "non riporta indicazioni specifiche" in risultato["risposta"].lower()


@pytest.mark.parametrize("farmaco_id", FARMACI)
def test_reazione_avversa_contiene_un_indicazione_di_urgenza(farmaco_id):
    risultato = risolvi_scenario("reazione_avversa", farmaco_id)
    assert risultato["trovato"] is True
    assert risultato["urgenza"] in {"contatta_medico", "emergenza"}
    assert risultato["azione"]
    assert risultato["fonti"]
    testo = risultato["risposta"].lower()
    assert any(
        parola in testo
        for parola in (
            "reazione",
            "allerg",
            "interrompa",
            "contatti",
            "immediatamente",
            "pronto soccorso",
        )
    ), farmaco_id


@pytest.mark.parametrize(
    "farmaco_id", ["012745_01", "004763_01", "025669_01", "020766_02"]
)
def test_alcol_trova_il_paragrafo_specifico(farmaco_id):
    risultato = risolvi_scenario("alcol", farmaco_id)
    assert risultato["trovato"] is True
    assert risultato["fonti"]
    assert any(
        parola in risultato["risposta"].lower()
        for parola in ("alcol", "alcool")
    )


def test_alcol_augmentin_senza_ancora_resta_un_fallback_esplicito():
    risultato = risolvi_scenario("alcol", "026089_01")
    assert risultato["trovato"] is False
    assert risultato["fonti"] == []
    assert "non riporta indicazioni specifiche" in risultato["risposta"].lower()


def test_alcol_plasil_non_cita_un_farmaco_qualsiasi():
    risultato = risolvi_scenario("alcol", "020766_02")
    assert risultato["trovato"] is True
    assert "consumare alcol" in risultato["risposta"].lower()
    assert "rifampicina" not in risultato["risposta"].lower()


def test_ogni_fonte_e_ancorata_a_un_blocco_reale():
    from services.retrieval import blocchi_per_farmaco

    testi = {
        blocco["blocco_id"]: blocco["testo"]
        for blocco in blocchi_per_farmaco("020766_02")
    }
    risultato = risolvi_scenario("dose_dimenticata", "020766_02")
    for fonte in risultato["fonti"]:
        assert fonte["testo_evidenziato"] in testi[fonte["blocco_id"]]


def test_reazione_avversa_non_cita_l_introduzione():
    risultato = risolvi_scenario("reazione_avversa", "012745_01")
    assert risultato["fonti"][0]["blocco_id"] != "012745_01_0_00"


def test_reazione_tachipirina_cita_l_istruzione_di_interrompere():
    risultato = risolvi_scenario("reazione_avversa", "012745_01")
    teste = risultato["risposta"].lower()
    assert "interrompa il trattamento" in teste
    assert "contatti" in teste


def test_scenario_inesistente():
    with pytest.raises(KeyError):
        risolvi_scenario("scenario_inesistente", "020766_02")


def test_farmaco_inesistente():
    with pytest.raises(KeyError):
        risolvi_scenario("dose_dimenticata", "farmaco_inesistente")
