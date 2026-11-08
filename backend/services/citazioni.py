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


def _bigrammi(testo: str) -> set[tuple[str, str]]:
    parole = [
        parola
        for parola in re.findall(r"[a-zA-ZÀ-ÿ]{4,}", testo.lower())
        if parola not in PAROLE_VUOTE
    ]
    return set(zip(parole, parole[1:]))


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

    # Espandiamo la query con i sinonimi clinici (denti -> dentali) per
    # scegliere la frase giusta anche quando il foglio usa un termine diverso.
    from services.retrieval import espandi_sinonimi

    query_estesa = espandi_sinonimi(query) if query else query
    parole_query = _parole(query_estesa)
    parole_risposta = _parole(risposta)
    parole_contesto = parole_query | parole_risposta
    frasi = _frasi_con_offset(testo_blocco)
    if not frasi:
        return span[:max_caratteri]

    def punteggio_frase(item: tuple[int, int, str]) -> int:
        parole_frase = _parole(item[2])
        # La pertinenza alla domanda pesa più delle parole comuni alla risposta.
        return 3 * len(parole_query & parole_frase) + len(
            parole_risposta & parole_frase
        )

    migliori = sorted(frasi, key=punteggio_frase, reverse=True)
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


def finestra_frasi(
    testo: str,
    parole_chiave: tuple[str, ...] | list[str] = (),
    max_frasi: int = 4,
    max_caratteri: int = 700,
) -> str:
    """Sceglie una finestra contigua di frasi, adatta alla lettura guidata.

    La finestra resta una sottostringa esatta del blocco, così può essere
    evidenziata nel foglio originale senza ricostruire il testo. Con
    ``parole_chiave`` privilegia le frasi che contengono i termini richiesti;
    senza parole chiave restituisce la prima finestra breve.
    """
    frasi = _frasi_con_offset(testo)
    if not frasi:
        return testo[:max_caratteri].strip()

    parole = [parola.lower() for parola in parole_chiave]
    migliore_testo = ""
    migliore_punteggio = -1
    for inizio_indice in range(len(frasi)):
        for numero in range(1, max_frasi + 1):
            fine_indice = inizio_indice + numero
            if fine_indice > len(frasi):
                break
            inizio = frasi[inizio_indice][0]
            fine = frasi[fine_indice - 1][1]
            if fine - inizio > max_caratteri:
                break
            candidato = testo[inizio:fine].strip()
            punteggio = (
                sum(1 for parola in parole if parola in candidato.lower())
                if parole
                else 0
            )
            if punteggio > migliore_punteggio:
                migliore_punteggio = punteggio
                migliore_testo = candidato

    return migliore_testo or testo[:max_caratteri].strip()


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
    bigrammi_risposta = _bigrammi(risposta)
    punteggi = [
        (len(parole_risposta & _parole(fonte.get("testo_evidenziato", ""))), fonte)
        for fonte in fonti
    ]
    migliore = max((punteggio for punteggio, _ in punteggi), default=0)
    soglia = max(4, int(migliore * 0.6))

    filtrate = [
        fonte
        for punteggio, fonte in punteggi
        if punteggio >= soglia
        or (
            bigrammi_risposta
            & _bigrammi(fonte.get("testo_evidenziato", ""))
        )
    ]
    return filtrate or fonti[:1]


def arricchisci_fonti(
    fonti: list[dict[str, Any]],
    blocchi: list[dict[str, Any]],
    risposta: str,
    query: str = "",
    max_fonti: int = 3,
) -> list[dict[str, Any]]:
    """Aggiunge fonti dal contesto che sostengono la risposta.

    Il modello a volte cita un solo blocco anche quando la risposta combina
    due informazioni (es. indicazione + regola di condivisione). Aggiungiamo
    i blocchi del contesto con forte sovrapposizione con la risposta.
    """
    if len(fonti) >= max_fonti:
        return fonti

    parole_risposta = _parole(risposta)
    if not parole_risposta:
        return fonti

    id_presenti = {fonte.get("blocco_id") for fonte in fonti}
    punteggi_esistenti = [
        len(parole_risposta & _parole(fonte.get("testo_evidenziato", "")))
        for fonte in fonti
    ]
    migliore_esistente = max(punteggi_esistenti, default=0)

    candidate: list[tuple[int, dict[str, Any], str]] = []
    for blocco in blocchi:
        blocco_id = blocco.get("blocco_id") or blocco.get("id")
        if blocco_id in id_presenti:
            continue
        span = affina_span(
            blocco["testo"],
            blocco["testo"],
            query=query,
            risposta=risposta,
        )
        punteggio = len(parole_risposta & _parole(span))
        candidate.append((punteggio, blocco, span))

    if not candidate:
        return fonti

    migliore = max(punteggio for punteggio, _, _ in candidate)
    # Aggiungiamo solo fonti almeno comparabili a quella già citata oppure che
    # condividono una coppia di parole distintiva con la risposta (es.
    # "infezioni dentali"). Evita blocchi generici con sole parole comuni.
    soglia = max(3, int(migliore_esistente * 0.9))
    bigrammi_risposta = _bigrammi(risposta)
    da_aggiungere = [
        (punteggio, blocco, span)
        for punteggio, blocco, span in candidate
        if punteggio >= max(2, soglia)
        or (bigrammi_risposta & _bigrammi(span))
    ]
    if not da_aggiungere and migliore < soglia:
        return fonti

    da_aggiungere.sort(key=lambda item: item[0], reverse=True)
    for punteggio, blocco, span in da_aggiungere:
        if len(fonti) >= max_fonti:
            break
        fonti.append(
            {
                "blocco_id": blocco.get("blocco_id") or blocco.get("id"),
                "documento": blocco["documento"],
                "sezione": blocco["sezione"],
                "paragrafo": blocco["paragrafo"],
                "testo_evidenziato": span,
                "verificata": True,
            }
        )
    return fonti


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
