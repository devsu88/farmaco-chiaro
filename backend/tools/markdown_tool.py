"""Tool di accesso ai markdown FI.

Il modulo è un adapter sottile sopra ``app.farmaci`` (registro) e
``services.retrieval`` (indice). Non contiene più mapping id -> file duplicati.
"""
from __future__ import annotations

import re
from typing import Any

from app import farmaci
from app.farmaci import tieni_primo_foglio
from services import retrieval


def carica_markdown(farmaco_id: str, tipo: str = "FI") -> dict[str, Any]:
    """Carica l'intero markdown di un foglio illustrativo o di una RCP."""
    farmaco = farmaci.get(farmaco_id)
    if farmaco is None:
        raise FileNotFoundError(f"Farmaco non trovato: {farmaco_id}")

    tipo_norm = tipo.upper()
    path = farmaco.path_fi if tipo_norm == "FI" else farmaco.path_rcp
    if not path.exists():
        raise FileNotFoundError(f"Markdown non trovato: {path}")

    content = path.read_text(encoding="utf-8")
    return {
        "farmaco_id": farmaco_id,
        "tipo": tipo_norm,
        "documento": farmaco.documento,
        "contenuto": content,
        "lunghezza_caratteri": len(content),
    }


def cerca_testo(query: str, farmaco_id: str, limite: int = 5) -> list[dict[str, Any]]:
    """Ricerca BM25 sui blocchi indicizzati del farmaco."""
    return retrieval.cerca(query, farmaco_id, limite=limite)


def estrai_paragrafo(blocco_id: str) -> dict[str, Any] | None:
    """Estrae un blocco specifico per ID per citazione precisa."""
    blocco = retrieval.trova_blocco(blocco_id)
    if blocco is None:
        return None
    return {
        "blocco_id": blocco["id"],
        "sezione": blocco["sezione"],
        "paragrafo": blocco["paragrafo"],
        "documento": blocco["documento"],
        "testo": blocco["testo"],
        "offset_inizio": blocco["offset_inizio"],
        "offset_fine": blocco["offset_fine"],
    }


def get_blocco_da_offset(
    farmaco_id: str, offset_inizio: int, offset_fine: int
) -> dict[str, Any] | None:
    """Trova il blocco che contiene un intervallo di offset specifico."""
    return retrieval.trova_blocco_per_offset(farmaco_id, offset_inizio, offset_fine)


def _chunk_markdown(contenuto: str) -> list[dict[str, str]]:
    """Divide il markdown in chunk per sezione/sottosezione."""
    chunks: list[dict[str, str]] = []
    sezione = "Introduzione"
    paragrafo = "1"
    righe: list[str] = []

    def flush() -> None:
        nonlocal righe
        testo = "\n".join(righe).strip()
        if testo:
            chunks.append(
                {"sezione": sezione, "paragrafo": paragrafo, "testo": testo}
            )
        righe = []

    for riga in contenuto.splitlines():
        stripped = riga.strip()
        if stripped.startswith("## ") and not stripped.startswith("### "):
            flush()
            sezione = stripped.replace("## ", "").strip()
            paragrafo = "1"
            continue
        if stripped.startswith("### "):
            flush()
            paragrafo = stripped.replace("### ", "").strip()
            continue
        righe.append(riga)
    flush()
    return chunks


def cerca_nel_markdown(
    query: str, farmaco_id: str, limite: int = 3
) -> list[dict[str, Any]]:
    """Fallback: cerca i chunk più pertinenti nel markdown completo."""
    markdown = carica_markdown(farmaco_id, tipo="FI")
    termini = retrieval.tokenizza(query)
    chunks = _chunk_markdown(tieni_primo_foglio(markdown["contenuto"]))

    scored: list[tuple[float, dict[str, str]]] = []
    for chunk in chunks:
        testo_lower = chunk["testo"].lower()
        punteggio = 0.0
        for termine in termini:
            occorrenze = len(re.findall(re.escape(termine), testo_lower))
            if occorrenze:
                punteggio += 1.0 + min(occorrenze, 10) * 0.1
        if punteggio > 0:
            scored.append((punteggio, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    risultati: list[dict[str, Any]] = []
    for punteggio, chunk in scored[:limite]:
        risultati.append(
            {
                "blocco_id": None,
                "documento": markdown["documento"],
                "sezione": chunk["sezione"],
                "paragrafo": chunk["paragrafo"],
                "testo": chunk["testo"],
                "score": round(punteggio, 4),
            }
        )
    return risultati
