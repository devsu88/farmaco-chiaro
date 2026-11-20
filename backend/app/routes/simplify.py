"""Route di semplificazione ETR."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.llm import SIMPLIFY_MODEL, build_llm, has_valid_api_key
from app.observability import log_event
from app.rate_limit import rate_limit
from app.schemas import SimplifyRequest, SimplifyResponse
from services import cache
from services.simplify import (
    fallback,
    pulisci_testo,
    semplifica,
    testo_da_documento,
)

router = APIRouter()


@router.get("/simplify/status")
def simplify_status() -> dict:
    """Stato del servizio di semplificazione (utile al frontend)."""
    return {
        "disponibile": has_valid_api_key(),
        "modello": SIMPLIFY_MODEL,
    }


@router.post(
    "/simplify",
    response_model=SimplifyResponse,
    dependencies=[Depends(rate_limit("simplify"))],
)
def simplify(req: SimplifyRequest, request: Request) -> dict:
    """Semplifica una sezione del foglio illustrativo o un testo arbitrario."""
    if req.testo is not None:
        testo = req.testo
    else:
        try:
            testo = testo_da_documento(req.farmaco_id, req.sezione)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        if not testo:
            raise HTTPException(
                status_code=404,
                detail="Sezione non disponibile per questo foglio illustrativo",
            )

    testo = pulisci_testo(testo)

    if not req.forza:
        cached = cache.leggi_semplificazione(testo, SIMPLIFY_MODEL)
        if cached is not None:
            log_event(
                request,
                "simplify_completed",
                farmaco_id=req.farmaco_id,
                sezione=req.sezione,
                cached=True,
                errore=None,
                model=SIMPLIFY_MODEL,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
            )
            return {**cached, "cached": True}

    if not has_valid_api_key():
        log_event(
            request,
            "simplify_completed",
            farmaco_id=req.farmaco_id,
            sezione=req.sezione,
            cached=False,
            errore="api_key",
            model=SIMPLIFY_MODEL,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
        )
        return fallback("API key OpenRouter mancante o non valida")

    llm = build_llm(model=SIMPLIFY_MODEL, temperature=0.2, max_tokens=2000)
    risultato = semplifica(testo, llm, forza=req.forza)
    usage = risultato.get("usage") or {}
    log_event(
        request,
        "simplify_completed",
        farmaco_id=req.farmaco_id,
        sezione=req.sezione,
        cached=False,
        errore=risultato.get("errore"),
        model=SIMPLIFY_MODEL,
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),
    )
    return risultato
