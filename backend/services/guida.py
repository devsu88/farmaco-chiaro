"""Modalità guidata "Una cosa alla volta".

Ogni schermata è una domanda precisa ("a cosa serve?", "come si prende?",
"cosa non fare?", "quando chiamare il medico?"). I blocchi vengono recuperati
con lo stesso retrieval del chatbot (ibrido BM25 + Qdrant in produzione, BM25
nei test) e poi ridotti a una finestra breve. Nessun testo viene inventato:
la citazione resta una sottostringa esatta del blocco originale.

Le euristiche sui titoli restano solo come fallback quando il retrieval non
trova un passaggio con le parole chiave attese.
"""
from __future__ import annotations

import re
from typing import Any

from app import farmaci
from services.citazioni import (
    conta_parole_chiave,
    finestra_ancorata,
    finestra_dose,
    finestra_frasi,
)
from services.retrieval import blocchi_per_farmaco, cerca

MAX_CARATTERI_SCHERMATA = 550
MAX_FRASI_SCHERMATA = 3

# Parole che indicano davvero il contenuto cercato. Servono sia a scegliere il
# blocco giusto (i titoli del PDF a volte sono sbagliati o fuori ordine) sia a
# verificare che la finestra estratta contenga l'informazione.
INDICAZIONE_RICHIESTA = (
    "indicato per",
    "indicata per",
    "è indicato",
    "è indicata",
    "viene utilizzato",
    "viene utilizzata",
    "è utilizzato",
    "è utilizzata",
    "essere utilizzato",
    "essere utilizzata",
    "essere utilizzati",
    "essere utilizzate",
    "è usato",
    "è usata",
    "sono usati",
    "sono usate",
    "si usa per",
    "serve per",
    "serve a",
    "allevia",
    "riduce",
    "per il trattamento",
    "per la prevenzione",
    "trattamento sintomatico",
    "per alleviare",
    "per ridurre",
    "per curare",
    "sintomi di",
    "cura di",
)
INDICAZIONE = (
    "indicato",
    "indicata",
    "utilizzato",
    "utilizzata",
    "usato",
    "usata",
    "serve",
    "allevia",
    "riduce",
    "trattamento",
    "sintomi",
    "dolore",
    "febbre",
    "infezione",
    "infiammazione",
    "prevenire",
    "prevenzione",
    "terapia",
)
DOSE = (
    "dose",
    "dosaggio",
    "mg",
    "ml",
    "compressa",
    "compresse",
    "capsule",
    "gocce",
    "supposte",
    "bustine",
    "siringa",
    "ogni",
    "ore",
    "giorno",
    "adulti",
    "bambini",
    "bambino",
)
NON_FARE = (
    "non usi",
    "non prenda",
    "non deve",
    "non devono",
    "non somministri",
    "non usare",
    "allergico",
    "allergica",
    "allergia",
    "controindicazioni",
    "controindicato",
)
MEDICO = (
    "medico",
    "farmacista",
    "infermiere",
    "immediatamente",
    "pronto soccorso",
    "112",
    "interrompa",
    "contatti",
    "contattare",
    "rivolga",
    "chiami",
    "consulti",
)

# Ogni schermata dichiara come scegliere il blocco sorgente e quali parole
# privilegiare nella finestra di frasi. L'ordine è l'ordine del percorso.
SCHERMATE: list[dict[str, Any]] = [
    {
        "id": "a_cosa_serve",
        "titolo": "A cosa serve",
        "icona": "info",
        "descrizione": "Per che cosa è indicato questo medicinale.",
        "query": (
            "a cosa serve il medicinale indicazioni terapeutiche per quali "
            "disturbi sintomi viene utilizzato"
        ),
        "finestra": "indicazione",
        "sezione": ("che cos", "a cosa serve", "indicazioni"),
        "paragrafo": (),
        "parole": INDICAZIONE,
        "contenuto": INDICAZIONE,
        "richiede": INDICAZIONE_RICHIESTA,
    },
    {
        "id": "come_si_prende",
        "titolo": "Come si prende",
        "icona": "compressa",
        "descrizione": "La dose e gli intervalli indicati nel foglio.",
        "finestra": "dose",
        "query": (
            "come si prende la dose quante compresse quante gocce ogni quante "
            "ore al giorno posologia"
        ),
        "sezione": (),
        "paragrafo": (
            "come prendere",
            "come usare",
            "come assumere",
            "posologia",
            "modo di somministrazione",
        ),
        "parole": DOSE,
        "contenuto": DOSE,
        "richiede": DOSE,
    },
    {
        "id": "cosa_non_fare",
        "titolo": "Cosa non fare",
        "icona": "divieto",
        "descrizione": "Le situazioni in cui non deve prendere il medicinale.",
        "query": (
            "quando non devo prendere il medicinale controindicazioni allergia "
            "non prenda non usi"
        ),
        "sezione": (),
        "paragrafo": (
            "non prenda",
            "non usi",
            "non dia",
            "non somministri",
            "non assuma",
            "controindicazioni",
        ),
        "parole": NON_FARE,
        "contenuto": NON_FARE,
        "richiede": NON_FARE,
    },
    {
        "id": "quando_medico",
        "titolo": "Quando chiamare il medico",
        "icona": "telefono",
        "descrizione": "I segnali per cui serve un professionista.",
        "query": (
            "quando devo chiamare il medico effetti indesiderati gravi "
            "interrompere il trattamento pronto soccorso"
        ),
        "sezione": (),
        "paragrafo": (
            "effetti indesiderati",
            "se prende più",
            "avvertenze e precauzioni",
            "durante il trattamento",
            "condizioni a cui",
        ),
        "parole": MEDICO,
        "contenuto": MEDICO,
        "richiede": MEDICO,
    },
]


def _inizio_pulito(testo: str) -> bool:
    """Scarta le finestre che iniziano a metà frase."""
    testo = testo.lstrip()
    return bool(testo) and (
        testo[0].isupper() or testo.startswith(("-", "•", "−"))
    )


def _punteggio_blocco(blocco: dict[str, Any], schermata: dict[str, Any]) -> int:
    sezione = (blocco.get("sezione") or "").lower()
    paragrafo = (blocco.get("paragrafo") or "").lower()
    punteggio = 0
    if any(chiave in sezione for chiave in schermata["sezione"]):
        punteggio += 5
    if any(chiave in paragrafo for chiave in schermata["paragrafo"]):
        punteggio += 4
    # Il contenuto conta più del titolo: nei PDF AIFA capita che le sezioni
    # siano accorpate o etichettate male.
    if conta_parole_chiave(
        f"{sezione} {paragrafo} {blocco.get('testo', '')}",
        schermata["contenuto"],
    ):
        punteggio += 3
    return punteggio


def _candidati(
    blocchi: list[dict[str, Any]],
    schermata: dict[str, Any],
) -> list[tuple[int, dict[str, Any]]]:
    return [
        (punteggio, blocco)
        for blocco in blocchi
        if (punteggio := _punteggio_blocco(blocco, schermata)) > 0
    ]


def _prima_frase(testo: str, limite: int = 150) -> str:
    frase = re.split(r"(?<=[.!?])\s+", testo.strip(), maxsplit=1)[0]
    if len(frase) > limite:
        frase = frase[: limite - 1].rstrip() + "…"
    return frase


def _frase_riepilogo(testo: str, parole_chiave: tuple[str, ...]) -> str:
    """Sceglie la frase più rappresentativa, non solo la prima."""
    frasi = [frase.strip() for frase in re.split(r"(?<=[.!?])\s+", testo) if frase.strip()]
    if not frasi:
        return ""
    if not parole_chiave:
        return _prima_frase(frasi[0])
    migliore = max(
        frasi,
        key=lambda frase: conta_parole_chiave(frase, parole_chiave),
    )
    return _prima_frase(migliore)


def _costruisci_schermata(
    schermata: dict[str, Any],
    blocco: dict[str, Any],
) -> dict[str, Any]:
    if schermata.get("finestra") == "dose":
        testo = finestra_dose(
            blocco["testo"],
            max_frasi=MAX_FRASI_SCHERMATA,
            max_caratteri=MAX_CARATTERI_SCHERMATA,
        ) or finestra_frasi(
            blocco["testo"],
            parole_chiave=schermata["parole"],
            max_frasi=MAX_FRASI_SCHERMATA,
            max_caratteri=MAX_CARATTERI_SCHERMATA,
        )
    elif schermata.get("finestra") == "indicazione":
        testo = finestra_ancorata(
            blocco["testo"],
            schermata["richiede"],
            max_frasi=MAX_FRASI_SCHERMATA,
            max_caratteri=MAX_CARATTERI_SCHERMATA,
        ) or finestra_frasi(
            blocco["testo"],
            parole_chiave=schermata["parole"],
            max_frasi=MAX_FRASI_SCHERMATA,
            max_caratteri=MAX_CARATTERI_SCHERMATA,
        )
    else:
        testo = finestra_frasi(
            blocco["testo"],
            parole_chiave=schermata["parole"],
            max_frasi=MAX_FRASI_SCHERMATA,
            max_caratteri=MAX_CARATTERI_SCHERMATA,
        )
    fonte = {
        "blocco_id": blocco["blocco_id"],
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


def _scegli_semantica(
    farmaco_id: str,
    specifica: dict[str, Any],
    blocchi: list[dict[str, Any]],
    usati: set[str],
) -> dict[str, Any] | None:
    """Sceglie il blocco più pertinente per la domanda della schermata."""
    risultati = list(enumerate(cerca(specifica["query"], farmaco_id, limite=8)))
    visti = {blocco["blocco_id"] for _, blocco in risultati}
    # Il retrieval può non restituire la sezione ovvia (titoli AIFA anomali):
    # la aggiungiamo in coda, senza togliere priorità ai risultati semantici.
    extra = [
        blocco
        for _, blocco in _candidati(blocchi, specifica)
        if blocco["blocco_id"] not in visti
    ]
    candidati = risultati + [
        (len(risultati) + offset, blocco) for offset, blocco in enumerate(extra)
    ]

    proposte = []
    for rank, blocco in candidati:
        proposta = _costruisci_schermata(specifica, blocco)
        parole = conta_parole_chiave(proposta["testi"][0], specifica["richiede"])
        proposte.append(
            (
                parole > 0,
                _punteggio_blocco(blocco, specifica),
                parole,
                _inizio_pulito(proposta["testi"][0]),
                -rank,
                blocco["blocco_id"] not in usati,
                len(blocco["testo"]),
                proposta,
            )
        )

    valide = [proposta for proposta in proposte if proposta[0]]
    if not valide:
        return None

    # La finestra deve contenere l'informazione attesa; poi contano la
    # pertinenza strutturale (titolo), la qualità della finestra e la posizione
    # nel ranking semantico.
    return max(
        valide,
        key=lambda item: (item[1], item[2], item[3], item[4], item[5], item[6]),
    )[7]


def _scegli_deterministica(
    blocchi: list[dict[str, Any]],
    specifica: dict[str, Any],
    usati: set[str],
) -> dict[str, Any] | None:
    """Fallback sui titoli, se il retrieval non trova il passaggio atteso."""
    proposte = []
    for punteggio, blocco in _candidati(blocchi, specifica):
        proposta = _costruisci_schermata(specifica, blocco)
        proposte.append(
            (
                conta_parole_chiave(proposta["testi"][0], specifica["richiede"]),
                punteggio,
                blocco["blocco_id"] not in usati,
                blocco,
                proposta,
            )
        )
    valide = [proposta for proposta in proposte if proposta[0] > 0]
    if not valide:
        return None
    return max(
        valide,
        key=lambda item: (item[1], item[0], item[2], len(item[3]["testo"])),
    )[4]


def guida(farmaco_id: str) -> dict[str, Any]:
    """Restituisce il percorso guidato in quattro schermate."""
    farmaco = farmaci.require(farmaco_id)
    blocchi = blocchi_per_farmaco(farmaco_id)
    if not blocchi:
        raise KeyError(f"Documento non indicizzato per {farmaco_id}")

    schermate: list[dict[str, Any]] = []
    usati: set[str] = set()
    for specifica in SCHERMATE:
        scelta = _scegli_semantica(farmaco_id, specifica, blocchi, usati)
        if scelta is None:
            scelta = _scegli_deterministica(blocchi, specifica, usati)
        if scelta is None:
            continue
        usati.add(scelta["fonti"][0]["blocco_id"])
        schermate.append(scelta)

    if not schermate:
        raise KeyError(f"Nessuna schermata disponibile per {farmaco_id}")

    per_id = {specifica["id"]: specifica for specifica in SCHERMATE}
    return {
        "farmaco_id": farmaco_id,
        "nome": farmaco.nome,
        "principio_attivo": farmaco.principio_attivo,
        "documento": farmaco.documento,
        "schermate": schermate,
        "riepilogo": [
            _frase_riepilogo(
                schermata["testi"][0],
                per_id[schermata["id"]]["parole"],
            )
            for schermata in schermate
        ],
    }
