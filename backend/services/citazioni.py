"""Validazione delle citazioni prodotte dal modello."""
from __future__ import annotations

from typing import Any


def fonte_da_blocco(blocco: dict[str, Any]) -> dict[str, Any]:
    return {
        "blocco_id": blocco.get("blocco_id") or blocco.get("id"),
        "documento": blocco["documento"],
        "sezione": blocco["sezione"],
        "paragrafo": blocco["paragrafo"],
        "testo_evidenziato": blocco["testo"],
        "verificata": True,
    }


def valida_fonte(fonte: dict[str, Any], blocchi: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Restituisce una fonte normalizzata solo se è ancorata a un blocco reale.

    La regola è volutamente severa: lo span citato deve essere contenuto nel
    testo del blocco. In caso contrario la fonte viene scartata.
    """
    span = (fonte.get("testo_evidenziato") or "").strip()
    if not span:
        return None

    blocco_id = fonte.get("blocco_id")
    candidati = [b for b in blocchi if blocco_id and (b.get("blocco_id") == blocco_id or b.get("id") == blocco_id)]
    if not candidati:
        candidati = blocchi

    for blocco in candidati:
        testo = blocco.get("testo", "")
        if span.lower() in testo.lower():
            return {
                "blocco_id": blocco.get("blocco_id") or blocco.get("id"),
                "documento": blocco.get("documento", fonte.get("documento", "")),
                "sezione": blocco.get("sezione", fonte.get("sezione", "")),
                "paragrafo": blocco.get("paragrafo", fonte.get("paragrafo", "")),
                "testo_evidenziato": span,
                "verificata": True,
            }
    return None
