"""Utility condivise per estrarre JSON dalle risposte del modello."""
from __future__ import annotations

import json


def parse_json_object(testo: str | None) -> dict:
    """Estrae il primo oggetto JSON valido da una risposta LLM.

    Tollera code fence markdown e testo introduttivo. Restituisce ``{}`` se
    non trova nulla di valido.
    """
    testo = (testo or "").strip()
    if not testo:
        return {}

    if testo.startswith("```"):
        parti = testo.split("```")
        if len(parti) > 1:
            testo = parti[1]
        if testo.lstrip().startswith("json"):
            testo = testo.lstrip()[4:]
        testo = testo.strip()

    try:
        valore = json.loads(testo)
        return valore if isinstance(valore, dict) else {}
    except Exception:
        pass

    start = testo.find("{")
    end = testo.rfind("}")
    if start != -1 and end > start:
        try:
            valore = json.loads(testo[start : end + 1])
            return valore if isinstance(valore, dict) else {}
        except Exception:
            return {}
    return {}
