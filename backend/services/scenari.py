"""Scenari "Cosa faccio se...?".

Le risposte sono estratte dal foglio illustrativo con lo stesso retrieval del
chatbot. Se nessun blocco contiene un'ancora dello scenario, il servizio
restituisce un fallback esplicito invece di forzare una citazione poco
pertinente. Le azioni sono testi di sicurezza rivisti, non consigli
personalizzati.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app import farmaci
from app.config import SCENARI_FILE
from services.citazioni import finestra_frasi
from services.retrieval import cerca


@lru_cache(maxsize=1)
def _scenari() -> list[dict[str, Any]]:
    data = json.loads(SCENARI_FILE.read_text(encoding="utf-8"))
    return data["scenari"]


def elenco_scenari() -> list[dict[str, Any]]:
    """Restituisce i metadati degli scenari disponibili."""
    return [
        {
            "id": scenario["id"],
            "titolo": scenario["titolo"],
            "icona": scenario["icona"],
            "descrizione": scenario["descrizione"],
            "urgenza": scenario["urgenza"],
        }
        for scenario in _scenari()
    ]


def _trova_scenario(scenario_id: str) -> dict[str, Any]:
    for scenario in _scenari():
        if scenario["id"] == scenario_id:
            return scenario
    raise KeyError(f"Scenario non trovato: {scenario_id}")


def _contiene_ancora(testo: str, ancore: list[str]) -> bool:
    testo_lower = testo.lower()
    return any(ancora in testo_lower for ancora in ancore)


def _inizio_estratto(testo: str, posizione: int, max_indietro: int = 120) -> int:
    """Trova un inizio leggibile prima dell'ancora."""
    if posizione <= max_indietro:
        return 0

    inizio = posizione - max_indietro
    for separatore in ("  ", "\n", ". "):
        confine = testo.rfind(separatore, inizio, posizione)
        if confine != -1:
            return confine + len(separatore)

    for indice in range(posizione - 1, inizio, -1):
        if testo[indice].isupper() and (
            indice == 0 or testo[indice - 1].isspace()
        ):
            return indice

    while inizio < posizione and not testo[inizio].isspace():
        inizio += 1
    return inizio


def _estratto_ancorato(
    testo: str,
    ancore: list[str],
    max_caratteri: int = 500,
) -> str:
    """Estrae la porzione di testo che contiene l'ancora dello scenario.

    Le ancore più lunghe sono frasi ("non prenda una dose doppia"); quelle
    corte sono parole. Partiamo dall'ancora e allarghiamo indietro fino a un
    confine leggibile, poi chiudiamo alla frase successiva.
    """
    testo_lower = testo.lower()
    posizione = -1
    ancora_trovata = ""
    for ancora in sorted(ancore, key=len, reverse=True):
        indice = testo_lower.find(ancora)
        if indice != -1:
            posizione = indice
            ancora_trovata = ancora
            break

    if posizione == -1:
        return finestra_frasi(
            testo,
            parole_chiave=ancore,
            max_frasi=3,
            max_caratteri=max_caratteri,
        )

    inizio = _inizio_estratto(testo, posizione)
    fine = min(len(testo), inizio + max_caratteri)
    if fine < len(testo):
        for separatore in (". ", "\n", "; "):
            confine_fine = testo.rfind(separatore, posizione, fine)
            if confine_fine != -1:
                fine = confine_fine + len(separatore)
                break

    estratto = testo[inizio:fine].strip()
    if ancora_trovata and ancora_trovata.lower() not in estratto.lower():
        return finestra_frasi(
            testo,
            parole_chiave=ancore,
            max_frasi=3,
            max_caratteri=max_caratteri,
        )
    return estratto


def risolvi_scenario(scenario_id: str, farmaco_id: str) -> dict[str, Any]:
    """Risponde a uno scenario per un farmaco, citando il foglio."""
    farmaci.require(farmaco_id)
    scenario = _trova_scenario(scenario_id)

    risultati = cerca(scenario["query"], farmaco_id, limite=5)
    blocco = next(
        (
            risultato
            for risultato in risultati
            if _contiene_ancora(risultato["testo"], scenario["ancore"])
        ),
        None,
    )

    if blocco is None:
        return {
            "scenario_id": scenario_id,
            "farmaco_id": farmaco_id,
            "titolo": scenario["titolo"],
            "risposta": scenario["fallback_risposta"],
            "azione": scenario["azione"],
            "urgenza": scenario["urgenza"],
            "trovato": False,
            "fonti": [],
        }

    risposta = _estratto_ancorato(
        blocco["testo"],
        scenario["ancore"],
        max_caratteri=500,
    )
    fonte = {
        "blocco_id": blocco["blocco_id"],
        "documento": blocco["documento"],
        "sezione": blocco["sezione"],
        "paragrafo": blocco["paragrafo"],
        "testo_evidenziato": risposta,
        "verificata": True,
    }

    return {
        "scenario_id": scenario_id,
        "farmaco_id": farmaco_id,
        "titolo": scenario["titolo"],
        "risposta": risposta,
        "azione": scenario["azione"],
        "urgenza": scenario["urgenza"],
        "trovato": True,
        "fonti": [fonte],
    }
