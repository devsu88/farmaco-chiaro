"""Route di sintesi vocale per la versione facile."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from services.tts import TTSError, sintetizza

router = APIRouter()


class TTSRequest(BaseModel):
    testo: str = Field(min_length=1, max_length=5000)
    voce: str | None = None


@router.post("/tts")
def tts(req: TTSRequest) -> Response:
    """Sintetizza la versione facile e restituisce un WAV."""
    try:
        audio = sintetizza(req.testo, voce=req.voce)
    except TTSError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    return Response(
        content=audio,
        media_type="audio/wav",
        headers={
            "Content-Disposition": 'inline; filename="versione-facile.wav"',
            "Cache-Control": "private, max-age=3600",
        },
    )
