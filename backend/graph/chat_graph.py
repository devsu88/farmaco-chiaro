"""Grafo LangGraph del chatbot.

Flusso:
    riscrivi query (con storico) -> domanda meta? -> risposta conversazionale
                                 -> recupera -> genera
                                            -> espandi -> recupera -> genera | fallback
    genera -> se "non trovato" -> fallback sul markdown completo

La sessione è stateless: la history arriva dal client e viene usata per
riscrivere i follow-up e per rispondere alle domande sulla conversazione.
Non c'è MemorySaver, quindi due sessioni non possono mescolarsi.
"""
from __future__ import annotations

import logging
import re
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from app import farmaci
from app.farmaci import tieni_primo_foglio
from app.json_utils import parse_json_object
from app.llm import CHAT_MODEL, build_llm
from services.citazioni import (
    arricchisci_fonti,
    estrai_estratto,
    filtra_fonti,
    fonte_da_blocco,
    valida_fonte,
)
from services.retrieval import espandi_sinonimi
from tools.markdown_tool import carica_markdown, cerca_nel_markdown, cerca_testo

logger = logging.getLogger(__name__)


class ChatState(TypedDict, total=False):
    messaggi: list[dict]
    farmaco_id: str
    query_riscritta: str
    domanda_meta: bool
    query_espansa: str
    candidati_retrieval: list[dict]
    risposta_finale: str
    fonti_citate: list[dict]
    informazione_trovata: bool
    fallback_usato: bool


SYSTEM_PROMPT = """Sei un assistente specializzato nella lettura di fogli illustrativi farmaci (AIFA).

Regole fondamentali:
1. RISPONDI SOLO usando le informazioni presenti nel contesto fornito.
2. NON inventare dosaggi, indicazioni, controindicazioni o consigli medici.
3. Se l'informazione non è nel contesto, dillo esplicitamente: "Non ho trovato questa informazione nel foglio illustrativo".
4. Ogni risposta deve citare la fonte: documento, sezione e paragrafo.
5. Non dare consigli medici personalizzati (es. "puoi prenderlo in gravidanza", "dosaggio per tuo figlio").
6. Rispondi in italiano, in modo chiaro e semplice. Per domande semplici usa 1-3 frasi; non ripetere tutto il contesto.
7. Quando citi, usa il valore ID del blocco fornito nel contesto e riporta la frase più specifica che risponde alla domanda.

Formato output richiesto (JSON):
{
  "risposta": "testo della risposta in italiano semplice",
  "fonti": [
    {
      "blocco_id": "id del blocco se disponibile",
      "documento": "nome documento",
      "sezione": "nome sezione",
      "paragrafo": "numero paragrafo",
      "testo_evidenziato": "span esatto di testo citato dal foglio"
    }
  ],
  "informazione_trovata": true
}
"""

QUERY_EXPANSION_PROMPT = """Data questa domanda dell'utente su un farmaco, aggiungi al massimo 5 sinonimi o termini tecnici utili per la ricerca nel foglio illustrativo AIFA.

Regole:
- Mantieni la domanda originale all'inizio.
- Aggiungi solo sinonimi o parole chiave pertinenti alla domanda.
- NON elencare sezioni del foglio (posologia, controindicazioni, effetti indesiderati, gravidanza, interazioni, avvertenze).
- Rispondi con una sola riga, niente spiegazioni.

Esempi:
- "mal di testa bambino" → "mal di testa bambino, cefalea, dolore alla testa, bambini"
- "quante compresse al giorno" → "quante compresse al giorno, dose, dosaggio, posologia"
- "posso in gravidanza" → "posso in gravidanza, gravidanza, allattamento"

Domanda utente: {query}"""

REWRITE_PROMPT = """Riscrivi l'ultima domanda dell'utente come domanda autonoma e completa, usando il contesto della conversazione.

Farmaco selezionato: {farmaco}

Conversazione:
{history}

Ultima domanda: {query}

Regole:
- Se la domanda è già autonoma, restituiscila quasi identica.
- Se è un follow-up ("e se...", "e per...", "posso lo stesso?"), esplicita l'argomento e il farmaco.
- Se la domanda riguarda un'altra persona (sorella, fratello, madre, amico, parente), esplicita che chiedi se quella persona può prendere il farmaco prescritto all'utente.
- Non rispondere alla domanda.
- Rispondi solo con la domanda riscritta, senza virgolette né spiegazioni."""

META_PROMPT = """Rispondi alla domanda dell'utente sulla conversazione usando SOLO lo storico fornito.

Regole:
- Non citare il foglio illustrativo e non aggiungere informazioni mediche nuove.
- Se l'utente chiede se ha già parlato di un argomento, rispondi sì/no e riassumi cosa era stato detto.
- Se chiede di ripetere o riassumere, fallo in modo breve.
- Rispondi in italiano, massimo 3 frasi.

Storico:
{history}

Domanda dell'utente: {query}"""

GENERATION_PROMPT = """Domanda dell'utente: {user_query}

Storico recente della conversazione:
{history}

Contesto trovato nel foglio illustrativo:
{context}

Istruzioni:
- Rispondi usando SOLO il contesto fornito.
- Se il contesto è vuoto o non contiene la risposta, metti "informazione_trovata": false e spiega che l'informazione non è nel foglio.
- Ogni informazione deve avere una fonte con blocco_id (se fornito nel contesto), documento, sezione, paragrafo e testo_evidenziato (span esatto citato).
- Cita la frase più specifica del contesto che risponde alla domanda.
- Se il contesto contiene un'informazione correlata alla domanda (anche un sintomo o una reazione specifica), citala prima di dire che non esiste una sezione specifica.
- Se la domanda riguarda un'altra persona (sorella, amico, parente), combina la regola sulla condivisione del farmaco con l'indicazione clinica presente nel contesto.
- Se il contesto contiene un blocco "Che cos'è ... e a che cosa serve", usalo per verificare se il sintomo è tra le indicazioni; non dire che le indicazioni terapeutiche mancano.
- Rispondi in modo diretto: prima la conclusione (sì/no), poi il motivo.
- Se la risposta combina più informazioni (es. indicazione clinica + regola di condivisione), cita una fonte per ciascuna.
- Riporta al massimo 2 fonti, solo quelle che contengono le informazioni citate nella risposta.
- Ordina le fonti per importanza: la prima deve essere quella che contiene l'informazione principale della risposta.
- Output solo JSON valido, niente testo prima o dopo."""


META_PATTERNS = [
    r"\bti ho (già )?chiesto\b",
    r"\bti avevo chiesto\b",
    r"\bti ho (già )?detto\b",
    r"\bhai (già )?(detto|risposto)\b",
    r"\bcosa (mi )?hai detto\b",
    r"\bdi cosa (abbiamo|stiamo) parlato\b",
    r"\bdomanda precedente\b",
    r"\bte lo avevo chiesto\b",
    r"\bte l'ho chiesto\b",
    r"\bripeti\b",
    r"\briassumi\b",
]


def get_llm():
    return build_llm(model=CHAT_MODEL, temperature=0.2, max_tokens=1200)


def _is_meta_domanda(query: str) -> bool:
    query_lower = query.lower()
    return any(re.search(pattern, query_lower) for pattern in META_PATTERNS)


def _format_history(messaggi: list[dict]) -> str:
    turni = messaggi[:-1][-8:]
    righe = []
    for messaggio in turni:
        ruolo = "Utente" if messaggio.get("ruolo") == "utente" else "Assistente"
        testo = (messaggio.get("testo") or "").strip()
        if testo:
            righe.append(f"{ruolo}: {testo[:800]}")
    return "\n".join(righe) if righe else "(nessuno)"


def _contesto(blocchi: list[dict], query: str = "") -> str:
    query_estesa = espandi_sinonimi(query) if query else ""
    parti = []
    for blocco in blocchi:
        blocco_id = blocco.get("blocco_id") or "n/d"
        estratto = (
            estrai_estratto(blocco["testo"], query_estesa)
            if query_estesa
            else blocco["testo"]
        )
        parti.append(
            f"[Fonte] ID: {blocco_id} | Documento: {blocco['documento']} | Sezione: {blocco['sezione']} | Paragrafo: {blocco['paragrafo']}\n{estratto}"
        )
    return "\n\n".join(parti)


def _genera(
    state: ChatState,
    contesto: str,
    blocchi_fonte: list[dict],
    fallback_usato: bool,
) -> dict:
    user_query = state["messaggi"][-1]["testo"]
    history = _format_history(state["messaggi"])

    prompt = GENERATION_PROMPT.format(
        user_query=user_query,
        history=history,
        context=contesto or "Nessun estratto pertinente trovato nel foglio illustrativo.",
    )

    try:
        risposta = get_llm().invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
    except Exception:
        logger.exception("Errore nella generazione della risposta")
        return {
            "risposta_finale": "Non ho trovato questa informazione nel foglio illustrativo.",
            "fonti_citate": [],
            "informazione_trovata": False,
            "fallback_usato": fallback_usato,
        }

    contenuto = risposta.content if isinstance(risposta.content, str) else str(risposta.content)
    parsed = parse_json_object(contenuto)
    testo_risposta = parsed.get("risposta") or contenuto
    info_trovata = bool(parsed.get("informazione_trovata", bool(blocchi_fonte)))

    fonti: list[dict] = []
    for fonte_modello in parsed.get("fonti") or []:
        if not isinstance(fonte_modello, dict):
            continue
        fonte = valida_fonte(
            fonte_modello,
            blocchi_fonte,
            query=user_query,
            risposta=testo_risposta,
        )
        if fonte is not None:
            fonti.append(fonte)

    if not fonti and blocchi_fonte:
        fonti = [
            fonte_da_blocco(blocco, query=user_query, risposta=testo_risposta)
            for blocco in blocchi_fonte[:3]
        ]

    if not info_trovata:
        fonti = []
    else:
        fonti = filtra_fonti(fonti, testo_risposta)
        fonti = arricchisci_fonti(
            fonti,
            blocchi_fonte,
            testo_risposta,
            query=user_query,
        )

    return {
        "risposta_finale": testo_risposta,
        "fonti_citate": fonti,
        "informazione_trovata": info_trovata,
        "fallback_usato": fallback_usato,
    }


def nodo_riscrivi_query(state: ChatState) -> dict:
    """Rende autonoma la domanda usando lo storico della conversazione."""
    query = state["messaggi"][-1]["testo"]

    if _is_meta_domanda(query):
        return {"query_riscritta": query, "domanda_meta": True}

    # Primo turno: non c'è nulla da riscrivere.
    if len(state["messaggi"]) <= 1:
        return {"query_riscritta": query, "domanda_meta": False}

    farmaco = farmaci.get(state["farmaco_id"])
    nome_farmaco = farmaco.nome if farmaco else state["farmaco_id"]
    history = _format_history(state["messaggi"])

    try:
        risposta = get_llm().invoke(
            [
                SystemMessage(
                    content="Sei un assistente che riscrive domande di follow-up."
                ),
                HumanMessage(
                    content=REWRITE_PROMPT.format(
                        farmaco=nome_farmaco,
                        history=history,
                        query=query,
                    )
                ),
            ]
        )
        riscritta = (
            risposta.content if isinstance(risposta.content, str) else str(risposta.content)
        ).strip()
    except Exception:
        logger.warning("Riscrittura query fallita, uso la domanda originale", exc_info=True)
        riscritta = query

    return {
        "query_riscritta": riscritta or query,
        "domanda_meta": False,
    }


def nodo_genera_meta(state: ChatState) -> dict:
    """Risponde a domande sulla conversazione, senza usare il foglio."""
    query = state["messaggi"][-1]["testo"]
    history = _format_history(state["messaggi"])

    try:
        risposta = get_llm().invoke(
            [
                SystemMessage(content="Rispondi solo sulla base della conversazione."),
                HumanMessage(
                    content=META_PROMPT.format(history=history, query=query)
                ),
            ]
        )
        testo = (
            risposta.content if isinstance(risposta.content, str) else str(risposta.content)
        ).strip()
    except Exception:
        logger.exception("Errore nella risposta conversazionale")
        testo = "Non riesco a rileggere la conversazione in questo momento."

    return {
        "risposta_finale": testo,
        "fonti_citate": [],
        "informazione_trovata": True,
        "fallback_usato": False,
    }


def nodo_retrieval(state: ChatState) -> dict:
    """Prima ricerca: usa la domanda riscritta, senza espansione LLM."""
    query = state.get("query_riscritta") or state["messaggi"][-1]["testo"]
    candidati = cerca_testo(
        query, state["farmaco_id"], limite=5, query_intento=query
    )
    return {"candidati_retrieval": candidati, "fallback_usato": False}


def nodo_espandi_query(state: ChatState) -> dict:
    """Espansione usata se la ricerca originale è debole o vuota."""
    query = state.get("query_riscritta") or state["messaggi"][-1]["testo"]
    try:
        risposta = get_llm().invoke(
            [
                SystemMessage(content="Sei un assistente che espande query di ricerca."),
                HumanMessage(content=QUERY_EXPANSION_PROMPT.format(query=query)),
            ]
        )
        espansa = risposta.content if isinstance(risposta.content, str) else str(risposta.content)
        espansa = espansa.strip()
    except Exception:
        logger.warning("Query expansion fallita, uso la query originale", exc_info=True)
        espansa = query
    return {"query_espansa": espansa or query}


def nodo_retrieval_espanso(state: ChatState) -> dict:
    query_riferimento = (
        state.get("query_riscritta") or state["messaggi"][-1]["testo"]
    )
    query = state.get("query_espansa") or query_riferimento
    candidati = cerca_testo(
        query,
        state["farmaco_id"],
        limite=5,
        query_intento=query_riferimento,
    )
    return {"candidati_retrieval": candidati, "fallback_usato": False}


def nodo_genera_risposta(state: ChatState) -> dict:
    candidati = state.get("candidati_retrieval", [])
    blocchi_contesto = candidati[:5]
    query = state.get("query_riscritta") or state["messaggi"][-1]["testo"]
    return _genera(
        state,
        _contesto(blocchi_contesto, query=query),
        blocchi_contesto,
        False,
    )


def nodo_fallback(state: ChatState) -> dict:
    farmaco_id = state["farmaco_id"]
    query = state.get("query_riscritta") or state["messaggi"][-1]["testo"]
    try:
        chunks = cerca_nel_markdown(query, farmaco_id, limite=3)
        if chunks:
            return _genera(state, _contesto(chunks, query=query), chunks, True)

        markdown = carica_markdown(farmaco_id, tipo="FI")
        contenuto = tieni_primo_foglio(markdown["contenuto"])
        estratto = estrai_estratto(
            contenuto,
            espandi_sinonimi(query),
            max_caratteri=6000,
        )
        contesto = (
            "Contenuto completo del foglio illustrativo (estratto):\n"
            + estratto
        )
        return _genera(state, contesto, [], True)
    except Exception:
        logger.exception("Fallback fallito per farmaco=%s", farmaco_id)
        return {
            "risposta_finale": "Non ho trovato questa informazione nel foglio illustrativo.",
            "fonti_citate": [],
            "informazione_trovata": False,
            "fallback_usato": True,
        }


def dopo_riscrittura(state: ChatState) -> str:
    return "meta" if state.get("domanda_meta") else "recupera"


def dopo_recupero(state: ChatState) -> str:
    candidati = state.get("candidati_retrieval") or []
    if not candidati:
        return "espandi"
    # Se il match è debole, vale la pena espandere la query con l'LLM.
    if candidati[0].get("score", 0) < 2.5:
        return "espandi"
    return "genera"


def dopo_recupero_espanso(state: ChatState) -> str:
    return "genera" if state.get("candidati_retrieval") else "fallback"


def dopo_generazione(state: ChatState) -> str:
    return "fine" if state.get("informazione_trovata") else "fallback"


def build_graph():
    builder = StateGraph(ChatState)
    builder.add_node("riscrivi", nodo_riscrivi_query)
    builder.add_node("meta", nodo_genera_meta)
    builder.add_node("recupera", nodo_retrieval)
    builder.add_node("espandi", nodo_espandi_query)
    builder.add_node("recupera_espanso", nodo_retrieval_espanso)
    builder.add_node("genera", nodo_genera_risposta)
    builder.add_node("fallback", nodo_fallback)

    builder.set_entry_point("riscrivi")
    builder.add_conditional_edges(
        "riscrivi",
        dopo_riscrittura,
        {"meta": "meta", "recupera": "recupera"},
    )
    builder.add_edge("meta", END)
    builder.add_conditional_edges(
        "recupera",
        dopo_recupero,
        {"genera": "genera", "espandi": "espandi"},
    )
    builder.add_edge("espandi", "recupera_espanso")
    builder.add_conditional_edges(
        "recupera_espanso",
        dopo_recupero_espanso,
        {"genera": "genera", "fallback": "fallback"},
    )
    builder.add_conditional_edges(
        "genera",
        dopo_generazione,
        {"fine": END, "fallback": "fallback"},
    )
    builder.add_edge("fallback", END)
    return builder.compile()


chat_graph = build_graph()


def run_chat(messaggi: list[dict], farmaco_id: str, sessione_id: str) -> dict:
    """Esegue il grafo e restituisce la risposta con le fonti."""
    initial_state: ChatState = {
        "messaggi": messaggi,
        "farmaco_id": farmaco_id,
        "query_riscritta": "",
        "domanda_meta": False,
        "query_espansa": "",
        "candidati_retrieval": [],
        "risposta_finale": "",
        "fonti_citate": [],
        "informazione_trovata": False,
        "fallback_usato": False,
    }

    result = chat_graph.invoke(initial_state)
    return {
        "risposta": result.get("risposta_finale", "Errore nella generazione della risposta."),
        "fonti": result.get("fonti_citate", []),
        "sessione_id": sessione_id,
        "fallback_usato": result.get("fallback_usato", False),
    }
