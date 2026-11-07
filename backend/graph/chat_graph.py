"""Grafo LangGraph del chatbot.

Flusso:
    espandi query -> recupera blocchi -> genera risposta
                                      -> fallback (markdown completo)

La sessione è stateless: la history arriva dal client e viene usata nel
prompt. Non c'è MemorySaver, quindi due sessioni non possono mescolarsi.
"""
from __future__ import annotations

import logging
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from app.json_utils import parse_json_object
from app.llm import CHAT_MODEL, build_llm
from services.citazioni import fonte_da_blocco, valida_fonte
from tools.markdown_tool import carica_markdown, cerca_nel_markdown, cerca_testo

logger = logging.getLogger(__name__)


class ChatState(TypedDict, total=False):
    messaggi: list[dict]
    farmaco_id: str
    query_espansa: str
    candidati_retrieval: list[dict]
    risposta_finale: str
    fonti_citate: list[dict]
    fallback_usato: bool


SYSTEM_PROMPT = """Sei un assistente specializzato nella lettura di fogli illustrativi farmaci (AIFA).

Regole fondamentali:
1. RISPONDI SOLO usando le informazioni presenti nel contesto fornito.
2. NON inventare dosaggi, indicazioni, controindicazioni o consigli medici.
3. Se l'informazione non è nel contesto, dillo esplicitamente: "Non ho trovato questa informazione nel foglio illustrativo".
4. Ogni risposta deve citare la fonte: documento, sezione e paragrafo.
5. Non dare consigli medici personalizzati (es. "puoi prenderlo in gravidanza", "dosaggio per tuo figlio").
6. Rispondi in italiano, in modo chiaro e semplice.

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

QUERY_EXPANSION_PROMPT = """Data questa domanda dell'utente su un farmaco, riscrivila espandendola con sinonimi e termini tecnici che potrebbero apparire nel foglio illustrativo AIFA.

Esempi:
- "mal di testa bambino" → "mal di testa, cefalea, dolore testa, dosaggio paracetamolo pediatrico, bambini"
- "posologia" → "posologia, dose, dosaggio, quante volte al giorno, ogni quante ore"
- "gravidanza" → "gravidanza, allattamento, fertilità, uso in gravidanza"

Domanda utente: {query}
Rispondi solo con i termini espansi separati da virgola, niente altro."""

GENERATION_PROMPT = """Domanda dell'utente: {user_query}

Storico recente della conversazione:
{history}

Contesto trovato nel foglio illustrativo:
{context}

Istruzioni:
- Rispondi usando SOLO il contesto fornito.
- Se il contesto è vuoto o non contiene la risposta, metti "informazione_trovata": false e spiega che l'informazione non è nel foglio.
- Ogni informazione deve avere una fonte con documento, sezione, paragrafo e testo_evidenziato (span esatto citato).
- Output solo JSON valido, niente testo prima o dopo."""


def get_llm():
    return build_llm(model=CHAT_MODEL, temperature=0.2, max_tokens=1200)


def _format_history(messaggi: list[dict]) -> str:
    turni = messaggi[:-1][-8:]
    righe = []
    for messaggio in turni:
        ruolo = "Utente" if messaggio.get("ruolo") == "utente" else "Assistente"
        testo = (messaggio.get("testo") or "").strip()
        if testo:
            righe.append(f"{ruolo}: {testo[:800]}")
    return "\n".join(righe) if righe else "(nessuno)"


def _contesto(blocchi: list[dict]) -> str:
    parti = []
    for blocco in blocchi:
        parti.append(
            f"[Fonte] Documento: {blocco['documento']} | Sezione: {blocco['sezione']} | Paragrafo: {blocco['paragrafo']}\n{blocco['testo']}"
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
        fonte = valida_fonte(fonte_modello, blocchi_fonte)
        if fonte is not None:
            fonti.append(fonte)

    if not fonti and blocchi_fonte:
        fonti = [fonte_da_blocco(blocco) for blocco in blocchi_fonte[:3]]

    if not info_trovata:
        fonti = []

    return {
        "risposta_finale": testo_risposta,
        "fonti_citate": fonti,
        "fallback_usato": fallback_usato,
    }


def nodo_query_expansion(state: ChatState) -> dict:
    query = state["messaggi"][-1]["testo"]
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


def nodo_retrieval(state: ChatState) -> dict:
    query = state.get("query_espansa") or state["messaggi"][-1]["testo"]
    candidati = cerca_testo(query, state["farmaco_id"], limite=5)
    return {"candidati_retrieval": candidati, "fallback_usato": False}


def nodo_genera_risposta(state: ChatState) -> dict:
    candidati = state.get("candidati_retrieval", [])
    blocchi_contesto = candidati[:3]
    return _genera(state, _contesto(blocchi_contesto), blocchi_contesto, False)


def nodo_fallback(state: ChatState) -> dict:
    farmaco_id = state["farmaco_id"]
    query = state["messaggi"][-1]["testo"]
    try:
        chunks = cerca_nel_markdown(query, farmaco_id, limite=3)
        if chunks:
            return _genera(state, _contesto(chunks), chunks, True)

        markdown = carica_markdown(farmaco_id, tipo="FI")
        contesto = (
            "Contenuto completo del foglio illustrativo (estratto):\n"
            + markdown["contenuto"][:6000]
        )
        return _genera(state, contesto, [], True)
    except Exception:
        logger.exception("Fallback fallito per farmaco=%s", farmaco_id)
        return {
            "risposta_finale": "Non ho trovato questa informazione nel foglio illustrativo.",
            "fonti_citate": [],
            "fallback_usato": True,
        }


def dovrebbe_fare_fallback(state: ChatState) -> str:
    return "fallback" if not state.get("candidati_retrieval") else "genera"


def build_graph():
    builder = StateGraph(ChatState)
    builder.add_node("espandi", nodo_query_expansion)
    builder.add_node("recupera", nodo_retrieval)
    builder.add_node("genera", nodo_genera_risposta)
    builder.add_node("fallback", nodo_fallback)

    builder.set_entry_point("espandi")
    builder.add_edge("espandi", "recupera")
    builder.add_conditional_edges(
        "recupera",
        dovrebbe_fare_fallback,
        {"genera": "genera", "fallback": "fallback"},
    )
    builder.add_edge("genera", END)
    builder.add_edge("fallback", END)
    return builder.compile()


chat_graph = build_graph()


def run_chat(messaggi: list[dict], farmaco_id: str, sessione_id: str) -> dict:
    """Esegue il grafo e restituisce la risposta con le fonti."""
    initial_state: ChatState = {
        "messaggi": messaggi,
        "farmaco_id": farmaco_id,
        "query_espansa": "",
        "candidati_retrieval": [],
        "risposta_finale": "",
        "fonti_citate": [],
        "fallback_usato": False,
    }

    result = chat_graph.invoke(initial_state)
    return {
        "risposta": result.get("risposta_finale", "Errore nella generazione della risposta."),
        "fonti": result.get("fonti_citate", []),
        "sessione_id": sessione_id,
        "fallback_usato": result.get("fallback_usato", False),
    }
