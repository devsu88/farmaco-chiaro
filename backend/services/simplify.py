"""Semplificazione ETR: prompt, chunking, merge e cache."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.config import CATALOGO_FILE
from app.farmaci import require
from app.json_utils import parse_json_object

ETR_SYSTEM_PROMPT = """Sei un esperto di linguaggio facile da leggere (ETR - Easy to Read) in italiano.
Il tuo compito è semplificare testi di fogli illustrativi farmaci per renderli comprensibili a persone con disabilità intellettiva lieve, dislessia, afasia o anziani.

Regole ETR:
- Frasi corte (max 15-20 parole)
- Una sola informazione per frase
- Voce attiva, niente subordinate
- Niente termini tecnici senza spiegazione
- Dosaggi e scadenze devono rimanere esatti (non arrotondare, non omettere)
- L'originale resta sempre disponibile a fianco: non nascondere informazioni

Output JSON richiesto (solo JSON, nessun testo prima o dopo):
{
  "una_frase": "cosa serve questo farmaco in una frase",
  "versione_facile": ["frase 1", "frase 2"],
  "glossario": [{"termine": "parola difficile", "spiegazione": "spiegazione semplice"}],
  "domande_farmacista": ["domanda 1", "domanda 2"],
  "entita_verificate": {
    "dosaggi_preservati": true,
    "note": "eventuali note sulla verifica"
  }
}

Non inventare informazioni. Se una sezione non c'è, indicalo.
"""

SEZIONI_UTILI = ["indicazioni", "posologia", "controindicazioni", "avvertenze"]
OCR_ARTIFACTS = {"Ita", "Ag", "rm", "Fa", "del", "enz", "lia", "na", "aco"}

_cache: dict[str, dict[str, Any]] = {}
_CACHE_MAX = 128


def _fallback(motivo: str) -> dict[str, Any]:
    return {
        "una_frase": "Semplificazione non disponibile al momento.",
        "versione_facile": [],
        "glossario": [],
        "domande_farmacista": [],
        "entita_verificate": {"dosaggi_preservati": False, "note": motivo},
        "errore": motivo,
    }


def pulisci_testo(testo: str) -> str:
    righe = []
    for riga in testo.splitlines():
        stripped = riga.strip()
        if stripped in OCR_ARTIFACTS:
            continue
        if re.fullmatch(r"\d{1,3}", stripped):
            continue
        righe.append(riga)
    testo = "\n".join(righe)
    testo = re.sub(r"[ \t]+", " ", testo)
    testo = re.sub(r"\n{3,}", "\n\n", testo)
    return testo.strip()


def _split_long(paragrafo: str, max_chars: int) -> list[str]:
    if len(paragrafo) <= max_chars:
        return [paragrafo]
    frasi = re.split(r"(?<=[.!?])\s+", paragrafo)
    parti: list[str] = []
    corrente = ""
    for frase in frasi:
        if len(frase) > max_chars:
            if corrente:
                parti.append(corrente)
                corrente = ""
            parti.extend(
                frase[i : i + max_chars] for i in range(0, len(frase), max_chars)
            )
        elif len(corrente) + len(frase) + 1 <= max_chars:
            corrente = f"{corrente} {frase}".strip()
        else:
            if corrente:
                parti.append(corrente)
            corrente = frase
    if corrente:
        parti.append(corrente)
    return parti


def _chunk_text(testo: str, max_chars: int = 6000) -> list[str]:
    paragrafi = [p.strip() for p in re.split(r"\n\s*\n", testo) if p.strip()]
    if not paragrafi:
        return [testo]

    chunks: list[str] = []
    corrente = ""
    for paragrafo in paragrafi:
        for parte in _split_long(paragrafo, max_chars):
            if len(corrente) + len(parte) + 2 <= max_chars:
                corrente = f"{corrente}\n\n{parte}".strip()
            else:
                if corrente:
                    chunks.append(corrente)
                corrente = parte
    if corrente:
        chunks.append(corrente)
    return chunks or [testo]


def _chiama_modello(llm: Any, testo: str, indice: int, totale: int) -> dict[str, Any]:
    contesto_parte = ""
    if totale > 1:
        contesto_parte = f"\nQuesta è la parte {indice + 1} di {totale} del testo. Semplifica solo questa parte.\n"

    prompt = f"""Semplifica il seguente testo di foglio illustrativo in linguaggio facile da leggere (ETR).
{contesto_parte}
Testo originale:
{testo}

Rispondi solo con il JSON richiesto."""

    try:
        risposta = llm.invoke(
            [SystemMessage(content=ETR_SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
    except Exception as exc:  # pragma: no cover - dipende dal provider
        return _fallback(f"Errore modello: {type(exc).__name__}: {str(exc)[:150]}")

    contenuto = risposta.content if isinstance(risposta.content, str) else str(risposta.content)
    risultato = parse_json_object(contenuto)
    if not risultato or not risultato.get("una_frase"):
        return _fallback("Il modello non ha restituito un JSON valido")

    risultato.setdefault("versione_facile", [])
    risultato.setdefault("glossario", [])
    risultato.setdefault("domande_farmacista", [])
    risultato.setdefault(
        "entita_verificate", {"dosaggi_preservati": False, "note": "non verificato"}
    )
    return risultato


def _dedupe(items: list[str]) -> list[str]:
    visti: set[str] = set()
    risultato: list[str] = []
    for item in items:
        chiave = item.strip().lower()
        if chiave and chiave not in visti:
            visti.add(chiave)
            risultato.append(item.strip())
    return risultato


def _merge(risultati: list[dict[str, Any]], totale_parti: int) -> dict[str, Any]:
    if len(risultati) == 1:
        return risultati[0]

    una_frase = next((r.get("una_frase") for r in risultati if r.get("una_frase")), "")
    versione_facile: list[str] = []
    glossario: list[dict[str, str]] = []
    domande: list[str] = []
    dosaggi_ok = True
    note: list[str] = []

    for risultato in risultati:
        versione_facile.extend(risultato.get("versione_facile") or [])
        domande.extend(risultato.get("domande_farmacista") or [])
        for voce in risultato.get("glossario") or []:
            if isinstance(voce, dict) and voce.get("termine"):
                glossario.append(voce)
        entita = risultato.get("entita_verificate") or {}
        if not entita.get("dosaggi_preservati", False):
            dosaggi_ok = False
        if entita.get("note"):
            note.append(str(entita["note"]))
        if risultato.get("errore"):
            note.append(str(risultato["errore"]))

    glossario_unico: list[dict[str, str]] = []
    visti: set[str] = set()
    for voce in glossario:
        termine = str(voce.get("termine", "")).strip()
        if termine and termine.lower() not in visti:
            visti.add(termine.lower())
            glossario_unico.append(
                {"termine": termine, "spiegazione": str(voce.get("spiegazione", ""))}
            )

    return {
        "una_frase": una_frase,
        "versione_facile": _dedupe(versione_facile),
        "glossario": glossario_unico,
        "domande_farmacista": _dedupe(domande),
        "entita_verificate": {
            "dosaggi_preservati": dosaggi_ok,
            "note": f"Semplificato in {totale_parti} parti. " + " ".join(note),
        },
    }


def semplifica(testo: str, llm: Any, max_chars: int = 6000) -> dict[str, Any]:
    """Semplifica un testo, gestendo automaticamente testi lunghi."""
    testo = pulisci_testo(testo)
    if not testo:
        return _fallback("Testo da semplificare vuoto")

    modello = getattr(llm, "model_name", "") or ""
    chiave = hashlib.sha256(f"{modello}:{testo}".encode()).hexdigest()
    if chiave in _cache:
        return _cache[chiave]

    chunks = _chunk_text(testo, max_chars=max_chars)
    risultati = [_chiama_modello(llm, chunk, i, len(chunks)) for i, chunk in enumerate(chunks)]
    risultato = _merge(risultati, len(chunks))

    if len(_cache) >= _CACHE_MAX:
        _cache.clear()
    _cache[chiave] = risultato
    return risultato


def testo_da_catalogo(farmaco_id: str, sezione: str) -> str:
    """Estrae il testo dal catalogo preview per la semplificazione."""
    require(farmaco_id)
    if not CATALOGO_FILE.exists():
        raise FileNotFoundError("Catalogo farmaci non trovato")

    catalogo = json.loads(CATALOGO_FILE.read_text(encoding="utf-8"))
    farmaco = next((f for f in catalogo if f["id"] == farmaco_id), None)
    if farmaco is None:
        raise KeyError(f"Farmaco non trovato: {farmaco_id}")

    if sezione == "tutta":
        parti = []
        for nome in SEZIONI_UTILI:
            testo = farmaco["sezioni"].get(nome, "")
            if testo:
                parti.append(f"### {nome}\n{testo}")
        return "\n\n".join(parti)

    testo = farmaco["sezioni"].get(sezione, "")
    if not testo:
        raise KeyError(f"Sezione non trovata: {sezione}")
    return testo


def fallback(motivo: str) -> dict[str, Any]:
    """Versione pubblica del fallback strutturato."""
    return _fallback(motivo)


def reset_cache() -> None:
    _cache.clear()
