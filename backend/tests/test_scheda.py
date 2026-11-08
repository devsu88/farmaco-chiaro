"""Test della scheda condivisibile per il caregiver."""
from __future__ import annotations

import pytest

from services.scheda import scheda


def test_scheda_contiene_le_informazioni_essenziali():
    risultato = scheda("tachipirina_1000")
    assert risultato["nome"] == "Tachipirina 1000 mg"
    assert risultato["principio_attivo"] == "paracetamolo"
    for chiave in (
        "a_cosa_serve",
        "come_si_prende",
        "cosa_non_fare",
        "quando_medico",
        "dose_dimenticata",
    ):
        assert risultato[chiave].strip()


def test_scheda_riporta_le_fonti_e_il_disclaimer():
    risultato = scheda("plasil")
    assert len(risultato["fonti"]) >= 4
    assert "non sostituisce" in risultato["disclaimer"].lower()


def test_scheda_non_contiene_dati_personali():
    risultato = scheda("aspirina_500")
    assert "paziente" not in risultato
    assert "utente" not in risultato


def test_scheda_farmaco_inesistente():
    with pytest.raises(KeyError):
        scheda("farmaco_inesistente")


def test_scheda_segnala_quando_la_dose_dimenticata_e_un_indicazione_generale():
    tachipirina = scheda("tachipirina_1000")
    assert tachipirina["dose_dimenticata_trovata"] is False

    augmentin = scheda("augmentin")
    assert augmentin["dose_dimenticata_trovata"] is True
