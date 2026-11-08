"""Modalità guidata "Una cosa alla volta".

Le schermate sono estratte in modo deterministico dai blocchi del foglio
illustrativo: nessuna chiamata al modello, nessun testo inventato. Ogni
schermata mantiene il riferimento esatto al blocco originale, così il
frontend può evidenziarlo nel pannello AIFA.
"""
from __future__ import annotations

import re
from typing import Any

from app import farmaci
from services.citazioni import finestra_frasi
from services.retrieval import blocchi_per_farmaco

MAX_CARATTERI_SCHERMATA = 550
MAX_FRASI_SCHERMATA = 3

# Ogni schermata dichiara come scegliere il blocco sorgente e quali parole
# privilegiare nella finestra di frasi. L'ordine è l'ordine del percorso.
SCHERMATE: list[dict[str, Any]] = [
    {
        "id": "a_cosa_serve",
        "titolo": "A cosa serve",
        "icona": "info",
        "descrizione": "Per che cosa è indicato questo medicinale.",
        "sezione": ("che cos", "a cosa serve", "indicazioni"),
        "paragrafo": (),
        "parole": (),
    },
    {
        "id": "come_si_prende",
        "titolo": "Come si prende",
        "icona": "compressa",
        "descrizione": "La dose e gli intervalli indicati nel foglio.",
        "sezione": (),
        "paragrafo": ("come prendere",),
        "parole": (
            "compress",
            "mg",
            "dose",
            "giorno",
            "ore",
            "ogni",
            "assuma",
            "adulti",
            "raccomandata",
            "singola",
        ),
    },
    {
        "id": "cosa_non_fare",
        "titolo": "Cosa non fare",
        "icona": "divieto",
        "descrizione": "Le situazioni in cui non deve prendere il medicinale.",
        "sezione": (),
        "paragrafo": ("non prenda", "controindicazioni"),
        "parole": ("non", "allergia", "grave", "fegato", "reni", "eviti"),
    },
    {
        "id": "quando_medico",
        "titolo": "Quando chiamare il medico",
        "icona": "telefono",
        "descrizione": "I segnali per cui serve un professionista.",
        "sezione": (),
        "paragrafo": (
            "effetti indesiderati",
            "se prende più",
            "avvertenze e precauzioni",
            "durante il trattamento",
        ),
        "parole": (
            "medico",
            "farmacista",
            "immediatamente",
            "pronto soccorso",
            "112",
            "grave",
            "reazione",
            "sintomi",
            "contatti",
            "consulti",
            "rivolga",
            "interrompa",
            "chiami",
        ),
    },
]

_TITOLI_PARAGRAFO = {
    "effetti indesiderati": 4,
    "se prende più": 3,
    "come prendere": 3,
    "non prenda": 3,
    "avvertenze e precauzioni": 2,
    "durante il trattamento": 1,
}


def _punteggio_blocco(blocco: dict[str, Any], schermata: dict[str, Any]) -> int:
    sezione = (blocco.get("sezione") or "").lower()
    paragrafo = (blocco.get("paragrafo") or "").lower()
    punteggio = 0
    if any(chiave in sezione for chiave in schermata["sezione"]):
        punteggio += 5
    if any(chiave in paragrafo for chiave in schermata["paragrafo"]):
        punteggio += 4
    for chiave, bonus in _TITOLI_PARAGRAFO.items():
        if chiave in paragrafo:
            punteggio += bonus
    return punteggio


def _scegli_blocco(
    blocchi: list[dict[str, Any]],
    schermata: dict[str, Any],
    escludi: set[str],
) -> dict[str, Any] | None:
    candidati = [
        (punteggio, blocco)
        for blocco in blocchi
        if blocco["id"] not in escludi
        and (punteggio := _punteggio_blocco(blocco, schermata)) > 0
    ]
    if not candidati:
        return None
    candidati.sort(key=lambda item: (item[0], len(item[1]["testo"])), reverse=True)
    return candidati[0][1]


def _prima_frase(testo: str, limite: int = 150) -> str:
    frase = re.split(r"(?<=[.!?])\s+", testo.strip(), maxsplit=1)[0]
    if len(frase) > limite:
        frase = frase[: limite - 1].rstrip() + "…"
    return frase


def _costruisci_schermata(
    schermata: dict[str, Any],
    blocco: dict[str, Any],
) -> dict[str, Any]:
    testo = finestra_frasi(
        blocco["testo"],
        parole_chiave=schermata["parole"],
        max_frasi=MAX_FRASI_SCHERMATA,
        max_caratteri=MAX_CARATTERI_SCHERMATA,
    )
    fonte = {
        "blocco_id": blocco["id"],
        "documento": blocco["documento"],
        "sezione": blocco["sezione"],
        "paragrafo": blocco["paragrafo"],
        "testo_evidenziato": testo,
        "verificata": True,
    }
    return {
        "id": schermata["id"],
        "titolo": schermata["titolo"],
        "icona": schermata["icona"],
        "descrizione": schermata["descrizione"],
        "testi": [testo],
        "fonti": [fonte],
    }


def guida(farmaco_id: str) -> dict[str, Any]:
    """Restituisce il percorso guidato in quattro schermate."""
    farmaco = farmaci.require(farmaco_id)
    blocchi = blocchi_per_farmaco(farmaco_id)
    if not blocchi:
        raise KeyError(f"Documento non indicizzato per {farmaco_id}")

    schermate: list[dict[str, Any]] = []
    usati: set[str] = set()
    for schermata in SCHERMATE:
        blocco = _scegli_blocco(blocchi, schermata, usati)
        if blocco is None:
            continue
        usati.add(blocco["id"])
        schermate.append(_costruisci_schermata(schermata, blocco))

    if not schermate:
        raise KeyError(f"Nessuna schermata disponibile per {farmaco_id}")

    return {
        "farmaco_id": farmaco_id,
        "nome": farmaco.nome,
        "principio_attivo": farmaco.principio_attivo,
        "documento": farmaco.documento,
        "schermate": schermate,
        "riepilogo": [
            _prima_frase(schermata["testi"][0]) for schermata in schermate
        ],
    }
