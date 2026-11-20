"""Route del chatbot con retrieval, citazioni e sessioni stateless."""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from app.llm import CHAT_MODEL, has_valid_api_key
from app.observability import log_event
from app.rate_limit import rate_limit
from app.schemas import ChatRequest, ChatResponse
from graph.chat_graph import run_chat

logger = logging.getLogger(__name__)
router = APIRouter()

RUOLI_VALIDI = {"utente", "assistente"}


@router.post(
    "/chat",
    response_model=ChatResponse,
    dependencies=[Depends(rate_limit("chat"))],
)
def chat(req: ChatRequest, request: Request) -> ChatResponse:
    """Risponde a una domanda sul farmaco citando i blocchi del foglio."""
    sessione_id = req.sessione_id or str(uuid.uuid4())

    if not has_valid_api_key():
        log_event(request, "chat_unavailable", farmaco_id=req.farmaco_id)
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
        log_event(request, "chat_failed", farmaco_id=req.farmaco_id)
        raise HTTPException(status_code=502, detail="Servizio chat non disponibile")

    usage = result.get("usage") or {}
    log_event(
        request,
        "chat_completed",
        farmaco_id=req.farmaco_id,
        fonti=len(result["fonti"]),
        fallback_usato=result.get("fallback_usato", False),
        model=CHAT_MODEL,
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),
    )

    return ChatResponse(
        risposta=result["risposta"],
        fonti=result["fonti"],
        sessione_id=result.get("sessione_id", sessione_id),
        fallback_usato=result.get("fallback_usato", False),
    )
