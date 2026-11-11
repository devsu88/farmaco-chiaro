"""Test della scheda condivisibile per il caregiver."""
from __future__ import annotations

import pytest

from services.scheda import scheda

FARMACI = ["012745_01", "004763_01", "026089_01", "025669_01", "020766_02"]


def test_scheda_contiene_le_informazioni_essenziali():
    risultato = scheda("012745_01")
    assert risultato["nome"] == "TACHIPIRINA 1000 mg compresse"
    assert risultato["principio_attivo"] == "PARACETAMOLO"
    for chiave in (
        "a_cosa_serve",
        "come_si_prende",
        "cosa_non_fare",
        "quando_medico",
        "dose_dimenticata",
    ):
        assert risultato[chiave].strip()


@pytest.mark.parametrize("farmaco_id", FARMACI)
def test_scheda_riporta_le_fonti_e_il_disclaimer(farmaco_id):
    risultato = scheda(farmaco_id)
    assert len(risultato["fonti"]) >= 4
    assert "non sostituisce" in risultato["disclaimer"].lower()


def test_scheda_non_contiene_dati_personali():
    risultato = scheda("004763_01")
    assert "paziente" not in risultato
    assert "utente" not in risultato


def test_scheda_farmaco_inesistente():
    with pytest.raises(KeyError):
        scheda("farmaco_inesistente")


@pytest.mark.parametrize("farmaco_id", FARMACI)
def test_scheda_segnala_la_regola_della_dose_dimenticata(farmaco_id):
    risultato = scheda(farmaco_id)
    assert risultato["dose_dimenticata_trovata"] is True
    assert "dose doppia" in risultato["dose_dimenticata"].lower()
