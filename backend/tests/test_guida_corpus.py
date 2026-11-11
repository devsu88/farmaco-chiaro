"""Qualità della guida su un campione deterministico del corpus.

I test girano in modalità BM25 (vedi conftest): verificano il fallback e la
qualità dell'estrazione senza dipendere da Qdrant o dalla rete.
"""
from __future__ import annotations

import re

from app import farmaci
from services.citazioni import conta_parole_chiave
from services.guida import INDICAZIONE_RICHIESTA, guida

CAMPIONE = [farmaco.id for indice, farmaco in enumerate(farmaci.all()) if indice % 8 == 0]

DOSE = re.compile(
    r"(?:\b\d+(?:[.,]\d+)?(?:\s*[-–]\s*\d+(?:[.,]\d+)?)?\s*"
    r"(?:mg|ml|g|mcg|µg|ui|compress[ae]|capsul[ae]|gocce?|bustine?|suppost[ae]|"
    r"ore|flaconcini?|contenitor[ei]|applicazion[ei]|irrigazion[ei]|fial[ae])"
    r"|\buna?\s+(?:compressa|capsula|goccia|supposta|bustina|applicazione|volta)\b)",
    re.IGNORECASE,
)
DOSE_WORDS = ("dose raccomandata", "dose abituale", "dose usuale", "al giorno")


def _dose_valida(testo: str) -> bool:
    basso = testo.lower()
    return bool(DOSE.search(testo)) or any(parola in basso for parola in DOSE_WORDS)


NON_FARE = ("non usi", "non prenda", "non dia", "non deve", "allergic", "controindic")
MEDICO = ("medico", "farmacista", "pronto soccorso", "112", "interrompa", "contatti")


def _campione() -> list[dict]:
    guide = []
    for farmaco_id in CAMPIONE:
        try:
            guide.append(guida(farmaco_id))
        except KeyError:
            continue
    return guide


def test_il_campione_ha_quasi_sempre_quattro_schermate():
    guide = _campione()
    complete = sum(1 for percorso in guide if len(percorso["schermate"]) == 4)
    assert complete / len(guide) >= 0.90


def test_le_schermate_contengono_linformazione_attesa():
    guide = _campione()
    esiti = {
        "a_cosa_serve": [0, 0],
        "come_si_prende": [0, 0],
        "cosa_non_fare": [0, 0],
        "quando_medico": [0, 0],
    }
    for percorso in guide:
        testi = {s["id"]: s["testi"][0] for s in percorso["schermate"]}
        controlli = {
            "a_cosa_serve": lambda t: bool(
                conta_parole_chiave(t, INDICAZIONE_RICHIESTA)
            ),
            "come_si_prende": _dose_valida,
            "cosa_non_fare": lambda t: any(k in t.lower() for k in NON_FARE),
            "quando_medico": lambda t: any(k in t.lower() for k in MEDICO),
        }
        for schermata_id, controllo in controlli.items():
            testo = testi.get(schermata_id, "")
            if not testo:
                continue
            esiti[schermata_id][0] += 1
            if controllo(testo):
                esiti[schermata_id][1] += 1

    soglie = {
        "a_cosa_serve": 0.95,
        "come_si_prende": 0.85,
        "cosa_non_fare": 0.95,
        "quando_medico": 0.95,
    }
    for schermata_id, (totale, ok) in esiti.items():
        assert ok / totale >= soglie[schermata_id], (
            f"{schermata_id}: {ok}/{totale}"
        )
