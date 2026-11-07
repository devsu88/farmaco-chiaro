"""Validazione e affinamento delle citazioni prodotte dal modello."""
from __future__ import annotations

import re
from typing import Any

PAROLE_VUOTE = {
    "della", "delle", "dello", "degli", "questo", "questa", "quello",
    "quella", "sono", "essere", "avere", "anche", "come", "perché", "perche",
    "medicinale", "farmaco", "foglio", "illustrativo", "informazione",
}


def _parole(testo: str) -> set[str]:
    return {
        parola
        for parola in re.findall(r"[a-zA-ZÀ-ÿ]{4,}", testo.lower())
        if parola not in PAROLE_VUOTE
    }


def _frasi_con_offset(testo: str) -> list[tuple[int, int, str]]:
    """Divide in frasi/voci mantenendo gli offset esatti nel testo originale.

    Non spezza a ogni newline: le righe dei PDF sono spesso andate a capo a
    metà frase. Spezza su punteggiatura e sull'inizio di una nuova voce "- ".
    """
    parti = re.split(r"(?<=[.!?])\s+|\n(?=\s*-\s*)", testo)
    frasi: list[tuple[int, int, str]] = []
    cursore = 0
    for parte in parti:
        if not parte.strip():
            continue
        inizio = testo.find(parte, cursore)
        if inizio == -1:
            inizio = testo.find(parte)
        if inizio == -1:
            continue
        fine = inizio + len(parte)
        cursore = fine
        if len(parte.strip()) >= 25:
            frasi.append((inizio, fine, parte.strip()))
    return frasi


def affina_span(
    testo_blocco: str,
    span: str,
    query: str = "",
    risposta: str = "",
    max_caratteri: int = 500,
) -> str:
    """Restringe uno span troppo lungo alla frase più pertinente.

    Il modello a volte restituisce l'intero blocco. Per evidenziare in modo
    preciso scegliamo la frase con più parole in comune con domanda e risposta,
    includendo la frase precedente/successiva solo se resta breve.
    """
    span = (span or "").strip()
    if not span:
        return span
    if len(span) <= 300 and span != testo_blocco.strip():
        return span

    parole_contesto = _parole(f"{query} {risposta}")
    frasi = _frasi_con_offset(testo_blocco)
    if not frasi:
        return span[:max_caratteri]

    migliori = sorted(
        frasi,
        key=lambda item: len(parole_contesto & _parole(item[2])),
        reverse=True,
    )
    if not migliori:
        return span[:max_caratteri]

    inizio, fine, _ = migliori[0]
    indice = frasi.index(migliori[0])

    # Aggiungi una frase adiacente solo se condivide parole con domanda/risposta
    # e il risultato resta breve. Così "prescritto soltanto per lei" e "non lo
    # dia ad altre persone" possono restare nella stessa citazione.
    for vicino in (indice - 1, indice + 1):
        if 0 <= vicino < len(frasi):
            v_inizio, v_fine, v_testo = frasi[vicino]
            condivide = bool(_parole(v_testo) & parole_contesto)
            nuovo_inizio = min(inizio, v_inizio)
            nuovo_fine = max(fine, v_fine)
            if condivide and nuovo_fine - nuovo_inizio <= max_caratteri:
                inizio, fine = nuovo_inizio, nuovo_fine

    raffinato = testo_blocco[inizio:fine].strip()
    return raffinato or span[:max_caratteri]


def estrai_estratto(testo: str, query: str, max_caratteri: int = 1800) -> str:
    """Estrae dal blocco il passaggio più pertinente alla domanda.

    I blocchi lunghi (es. "Condizioni a cui prestare attenzione") contengono
    decine di avvertenze. Passare l'intero blocco al modello disperde
    l'informazione utile; passiamo invece la finestra di frasi più pertinente.
    """
    if len(testo) <= max_caratteri:
        return testo

    frasi = _frasi_con_offset(testo)
    if not frasi:
        return testo[:max_caratteri]

    parole_query = _parole(query)
    if not parole_query:
        return testo[:max_caratteri]

    punteggi = [
        (len(parole_query & _parole(frase)), indice)
        for indice, (_, _, frase) in enumerate(frasi)
    ]
    punteggi.sort(reverse=True)
    if not punteggi or punteggi[0][0] == 0:
        return testo[:max_caratteri]

    indice_migliore = punteggi[0][1]
    inizio, fine, _ = frasi[indice_migliore]

    # Allarga la finestra alle frasi contigue, se restano nel limite.
    for direzione in (-1, 1):
        indice = indice_migliore + direzione
        while 0 <= indice < len(frasi):
            f_inizio, f_fine, _ = frasi[indice]
            nuovo_inizio = min(inizio, f_inizio)
            nuovo_fine = max(fine, f_fine)
            if nuovo_fine - nuovo_inizio > max_caratteri:
                break
            inizio, fine = nuovo_inizio, nuovo_fine
            indice += direzione

    return testo[inizio:fine].strip() or testo[:max_caratteri]


def fonte_da_blocco(
    blocco: dict[str, Any],
    query: str = "",
    risposta: str = "",
) -> dict[str, Any]:
    span = affina_span(
        blocco["testo"],
        blocco["testo"],
        query=query,
        risposta=risposta,
    )
    return {
        "blocco_id": blocco.get("blocco_id") or blocco.get("id"),
        "documento": blocco["documento"],
        "sezione": blocco["sezione"],
        "paragrafo": blocco["paragrafo"],
        "testo_evidenziato": span,
        "verificata": True,
    }


def filtra_fonti(fonti: list[dict[str, Any]], risposta: str) -> list[dict[str, Any]]:
    """Tiene solo le fonti che condividono abbastanza contenuto con la risposta.

    Evita di mostrare blocchi del contesto che il modello ha citato solo
    perché presenti, ma che non sostengono davvero la risposta.
    """
    if len(fonti) <= 1:
        return fonti

    parole_risposta = _parole(risposta)
    punteggi = [
        (len(parole_risposta & _parole(fonte.get("testo_evidenziato", ""))), fonte)
        for fonte in fonti
    ]
    migliore = max((punteggio for punteggio, _ in punteggi), default=0)
    soglia = max(2, int(migliore * 0.45))

    filtrate = [fonte for punteggio, fonte in punteggi if punteggio >= soglia]
    return filtrate or fonti[:1]


def valida_fonte(
    fonte: dict[str, Any],
    blocchi: list[dict[str, Any]],
    query: str = "",
    risposta: str = "",
) -> dict[str, Any] | None:
    """Restituisce una fonte normalizzata solo se è ancorata a un blocco reale."""
    span = (fonte.get("testo_evidenziato") or "").strip()
    if not span:
        return None

    blocco_id = fonte.get("blocco_id")
    candidati = [
        b
        for b in blocchi
        if blocco_id and (b.get("blocco_id") == blocco_id or b.get("id") == blocco_id)
    ]
    if not candidati:
        candidati = blocchi

    for blocco in candidati:
        testo = blocco.get("testo", "")
        if span.lower() in testo.lower():
            span_raffinato = affina_span(
                testo,
                span,
                query=query,
                risposta=risposta,
            )
            return {
                "blocco_id": blocco.get("blocco_id") or blocco.get("id"),
                "documento": blocco.get("documento", fonte.get("documento", "")),
                "sezione": blocco.get("sezione", fonte.get("sezione", "")),
                "paragrafo": blocco.get("paragrafo", fonte.get("paragrafo", "")),
                "testo_evidenziato": span_raffinato,
                "verificata": True,
            }
    return None
