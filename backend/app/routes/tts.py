"""Route di sintesi vocale per la versione facile."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.observability import log_event
from app.rate_limit import rate_limit
from services.tts import TTSError, sintetizza

router = APIRouter()


class TTSRequest(BaseModel):
    testo: str = Field(min_length=1, max_length=5000)
    voce: str | None = Field(default=None, max_length=64)


@router.post("/tts", dependencies=[Depends(rate_limit("tts"))])
def tts(req: TTSRequest, request: Request) -> Response:
    """Sintetizza la versione facile e restituisce un WAV."""
    try:
        audio = sintetizza(req.testo, voce=req.voce)
    except TTSError as exc:
        log_event(
            request,
            "tts_failed",
            chars=len(req.testo),
            voce=req.voce,
            status=exc.status_code,
        )
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    log_event(request, "tts_completed", chars=len(req.testo), voce=req.voce)

    return Response(
        content=audio,
        media_type="audio/wav",
        headers={
            "Content-Disposition": 'inline; filename="versione-facile.wav"',
            "Cache-Control": "private, max-age=3600",
        },
    )
