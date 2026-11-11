"""Tool di accesso ai blocchi del foglio illustrativo.

Adapter sottile sopra ``services.retrieval``: non esistono più Markdown a
runtime, solo i blocchi citabili di ``documento.jsonl``.
"""
from __future__ import annotations

from typing import Any

from app import farmaci
from services import retrieval


def carica_documento(farmaco_id: str) -> dict[str, Any]:
    """Restituisce il testo completo del foglio, ricostruito dai suoi blocchi."""
    farmaco = farmaci.get(farmaco_id)
    if farmaco is None:
        raise FileNotFoundError(f"Farmaco non trovato: {farmaco_id}")

    blocchi = retrieval.blocchi_per_farmaco(farmaco_id)
    contenuto = "\n\n".join(blocco["testo"] for blocco in blocchi)
    return {
        "farmaco_id": farmaco_id,
        "tipo": "FI",
        "documento": farmaco.documento,
        "contenuto": contenuto,
        "lunghezza_caratteri": len(contenuto),
    }


def cerca_testo(
    query: str,
    farmaco_id: str,
    limite: int = 5,
    query_intento: str | None = None,
) -> list[dict[str, Any]]:
    """Ricerca ibrida sui blocchi indicizzati del farmaco."""
    return retrieval.cerca(
        query,
        farmaco_id,
        limite=limite,
        query_intento=query_intento,
    )


def estrai_paragrafo(blocco_id: str) -> dict[str, Any] | None:
    """Estrae un blocco specifico per ID, per una citazione precisa."""
    blocco = retrieval.trova_blocco(blocco_id)
    if blocco is None:
        return None
    return {
        "blocco_id": blocco["blocco_id"],
        "sezione": blocco["sezione"],
        "paragrafo": blocco["paragrafo"],
        "documento": blocco["documento"],
        "testo": blocco["testo"],
    }
