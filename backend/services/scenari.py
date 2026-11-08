"""Scenari "Cosa faccio se...?".

Le risposte sono estratte dal foglio illustrativo con lo stesso retrieval del
chatbot. Se nessun blocco contiene un'ancora dello scenario, il servizio
restituisce un fallback esplicito invece di forzare una citazione poco
pertinente. Le azioni sono testi di sicurezza rivisti, non consigli
personalizzati.
"""
from __future__ import annotations

import json
import re
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


def _trova_ancora(
    testo: str, ancore: list[str]
) -> tuple[int, int, str] | None:
    """Trova la prima ancora, ignorando a capo e spazi multipli."""
    for ancora in ancore:
        pattern = r"\s+".join(re.escape(parte) for parte in ancora.split())
        trovata = re.search(pattern, testo, re.IGNORECASE)
        if trovata:
            return trovata.start(), trovata.end(), ancora
    return None


def _contiene_ancora(testo: str, ancore: list[str]) -> bool:
    return _trova_ancora(testo, ancore) is not None


def _inizio_estratto(testo: str, posizione: int, max_indietro: int = 120) -> int:
    """Trova un inizio leggibile prima dell'ancora."""
    if posizione <= max_indietro:
        return 0

    inizio = posizione - max_indietro
    for separatore in (". ", "\n"):
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
    trovata = _trova_ancora(testo, ancore)
    if trovata is None:
        return finestra_frasi(
            testo,
            parole_chiave=ancore,
            max_frasi=3,
            max_caratteri=max_caratteri,
        )

    posizione, _, ancora_trovata = trovata
    inizio = _inizio_estratto(testo, posizione)
    fine = min(len(testo), inizio + max_caratteri)
    if fine < len(testo):
        for separatore in (". ", "\n", "; "):
            confine_fine = testo.rfind(separatore, posizione, fine)
            if confine_fine != -1:
                fine = confine_fine + len(separatore)
                break

    estratto = testo[inizio:fine].strip()
    estratto_normalizzato = re.sub(r"\s+", " ", estratto.lower())
    if ancora_trovata.lower() not in estratto_normalizzato:
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
    ancore_negative = scenario.get("ancore_negative", [])
    blocco = next(
        (
            risultato
            for risultato in risultati
            if _contiene_ancora(risultato["testo"], scenario["ancore"])
            and not _contiene_ancora(risultato["testo"], ancore_negative)
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
