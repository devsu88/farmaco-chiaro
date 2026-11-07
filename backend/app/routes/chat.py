"""Route del chatbot con retrieval, citazioni e sessioni stateless."""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException

from app.llm import has_valid_api_key
from app.schemas import ChatRequest, ChatResponse
from graph.chat_graph import run_chat

logger = logging.getLogger(__name__)
router = APIRouter()

RUOLI_VALIDI = {"utente", "assistente"}


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """Risponde a una domanda sul farmaco citando i blocchi del foglio."""
    sessione_id = req.sessione_id or str(uuid.uuid4())

    if not has_valid_api_key():
        return ChatResponse(
            risposta="Il chatbot non è disponibile: API key OpenRouter non configurata.",
            fonti=[],
            sessione_id=sessione_id,
            fallback_usato=True,
        )

    messaggi = [
        {"ruolo": m.ruolo, "testo": m.testo}
        for m in req.storico
        if m.ruolo in RUOLI_VALIDI and m.testo.strip()
    ]
    messaggi.append({"ruolo": "utente", "testo": req.messaggio})

    try:
        result = run_chat(
            messaggi=messaggi,
            farmaco_id=req.farmaco_id,
            sessione_id=sessione_id,
        )
    except Exception:
        logger.exception("Errore nella chat per farmaco=%s", req.farmaco_id)
        raise HTTPException(status_code=502, detail="Servizio chat non disponibile")

    return ChatResponse(
        risposta=result["risposta"],
        fonti=result["fonti"],
        sessione_id=result.get("sessione_id", sessione_id),
        fallback_usato=result.get("fallback_usato", False),
    )
