"""Documento originale citabile, costruito dagli stessi blocchi dell'indice."""
from __future__ import annotations

from app import farmaci
from services.retrieval import blocchi_per_farmaco


def documento(farmaco_id: str) -> dict:
    """Restituisce sezioni e blocchi del foglio illustrativo.

    Il frontend usa ``blocco_id`` per evidenziare la fonte citata dalla chat:
    documento, semplificazione e retrieval condividono così la stessa fonte.
    """
    farmaco = farmaci.require(farmaco_id)
    blocchi = blocchi_per_farmaco(farmaco_id)

    sezioni: list[dict] = []
    indice_sezioni: dict[str, dict] = {}
    for blocco in blocchi:
        titolo = blocco["sezione"]
        sezione = indice_sezioni.get(titolo)
        if sezione is None:
            sezione = {"titolo": titolo, "blocchi": []}
            indice_sezioni[titolo] = sezione
            sezioni.append(sezione)
        sezione["blocchi"].append(
            {
                "blocco_id": blocco["id"],
                "paragrafo": blocco["paragrafo"],
                "testo": blocco["testo"],
            }
        )

    return {
        "farmaco_id": farmaco_id,
        "documento": farmaco.documento,
        "sezioni": sezioni,
    }
