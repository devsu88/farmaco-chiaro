"""Scheda condivisibile: composizione deterministica per il caregiver."""
from __future__ import annotations

from typing import Any

from app import farmaci
from services.guida import guida
from services.scenari import risolvi_scenario

DISCLAIMER = (
    "Questa scheda aiuta a capire il foglio illustrativo e non sostituisce "
    "il medico o il farmacista. In caso di dubbio o di sintomi gravi rivolgersi "
    "a un professionista sanitario."
)


def scheda(farmaco_id: str) -> dict[str, Any]:
    """Compone la scheda del farmaco riusando guida e scenari."""
    farmaco = farmaci.require(farmaco_id)
    percorso = guida(farmaco_id)
    per_id = {schermata["id"]: schermata for schermata in percorso["schermate"]}

    sezioni = {
        "a_cosa_serve": per_id.get("a_cosa_serve", {}).get("testi", [""])[0],
        "come_si_prende": per_id.get("come_si_prende", {}).get("testi", [""])[0],
        "cosa_non_fare": per_id.get("cosa_non_fare", {}).get("testi", [""])[0],
        "quando_medico": per_id.get("quando_medico", {}).get("testi", [""])[0],
    }

    dimenticanza = risolvi_scenario("dose_dimenticata", farmaco_id)

    fonti = [
        fonte
        for schermata in percorso["schermate"]
        for fonte in schermata["fonti"]
    ]
    fonti.extend(dimenticanza["fonti"])

    return {
        "farmaco_id": farmaco_id,
        "nome": farmaco.nome,
        "principio_attivo": farmaco.principio_attivo,
        "documento": farmaco.documento,
        **sezioni,
        "dose_dimenticata": dimenticanza["risposta"],
        "dose_dimenticata_trovata": dimenticanza["trovato"],
        "fonti": fonti,
        "disclaimer": DISCLAIMER,
    }
