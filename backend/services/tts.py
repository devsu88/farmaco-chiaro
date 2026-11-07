"""Sintesi vocale server-side via OpenRouter (HeyGen Voice Turbo).

OpenRouter espone ``POST /api/v1/audio/speech``. HeyGen restituisce PCM
grezzo: lo convertiamo in WAV per poterlo riprodurre direttamente nel browser.
L'audio viene messo in cache su disco, così riascoltare la stessa versione
non richiama il provider.
"""
from __future__ import annotations

import array
import io
import os
import re
import sys
import wave

import httpx

from app.llm import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, has_valid_api_key
from services import cache

TTS_MODEL = os.getenv("TTS_MODEL", "heygen/heygen-voice-1-turbo:free")
TTS_VOICE = os.getenv("TTS_VOICE", "nadine")
TTS_TIMEOUT = int(os.getenv("TTS_TIMEOUT", "90"))
TTS_MAX_CHARS = int(os.getenv("TTS_MAX_CHARS", "5000"))
# Il PCM di HeyGen arriva a 44.1 kHz: per la voce 16 kHz è più che
# sufficiente e riduce di ~2,7 volte la dimensione del WAV.
TTS_SAMPLE_RATE = int(os.getenv("TTS_SAMPLE_RATE", "16000"))
TTS_CACHE_MODEL = f"{TTS_MODEL}@{TTS_SAMPLE_RATE}"


class TTSError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _resample_pcm(pcm: bytes, source_rate: int, target_rate: int) -> bytes:
    """Riduce la frequenza di campionamento di PCM 16 bit mono."""
    if source_rate == target_rate or source_rate <= 0 or target_rate <= 0:
        return pcm

    campioni = array.array("h")
    campioni.frombytes(pcm)
    if sys.byteorder != "little":
        campioni.byteswap()

    rapporto = source_rate / target_rate
    nuova_lunghezza = int(len(campioni) / rapporto)
    if nuova_lunghezza <= 0:
        return pcm

    ridotti = array.array(
        "h",
        (
            campioni[min(int(i * rapporto), len(campioni) - 1)]
            for i in range(nuova_lunghezza)
        ),
    )
    if sys.byteorder != "little":
        ridotti.byteswap()
    return ridotti.tobytes()


def _pcm_to_wav(
    pcm: bytes,
    rate: int = 44100,
    channels: int = 1,
    target_rate: int | None = None,
) -> bytes:
    if channels == 1 and target_rate and target_rate != rate:
        pcm = _resample_pcm(pcm, rate, target_rate)
        rate = target_rate

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)  # PCM 16 bit
        wav.setframerate(rate)
        wav.writeframes(pcm)
    return buffer.getvalue()


def _audio_params(content_type: str) -> tuple[int, int]:
    rate = re.search(r"rate=(\d+)", content_type)
    channels = re.search(r"channels=(\d+)", content_type)
    return (
        int(rate.group(1)) if rate else 44100,
        int(channels.group(1)) if channels else 1,
    )


def sintetizza(testo: str, voce: str | None = None) -> bytes:
    """Restituisce un WAV pronto per il browser."""
    testo = testo.strip()
    if not testo:
        raise TTSError("Testo da leggere vuoto", status_code=400)
    if len(testo) > TTS_MAX_CHARS:
        raise TTSError(
            f"Testo troppo lungo: massimo {TTS_MAX_CHARS} caratteri",
            status_code=413,
        )

    voce = voce or TTS_VOICE
    cached = cache.leggi_tts(testo, TTS_CACHE_MODEL, voce)
    if cached is not None:
        return cached

    if not has_valid_api_key():
        raise TTSError("API key OpenRouter non configurata", status_code=503)

    payload = {
        "model": TTS_MODEL,
        "input": testo,
        "voice": voce,
        "response_format": "pcm",
    }

    try:
        risposta = httpx.post(
            f"{OPENROUTER_BASE_URL}/audio/speech",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=TTS_TIMEOUT,
        )
    except httpx.HTTPError:
        raise TTSError("Servizio di sintesi vocale non raggiungibile")

    if risposta.status_code != 200:
        try:
            dettaglio = risposta.json().get("error", {}).get("message", "")
        except ValueError:
            dettaglio = ""
        raise TTSError(
            f"OpenRouter TTS ha risposto {risposta.status_code}"
            + (f": {str(dettaglio)[:200]}" if dettaglio else "")
        )

    rate, channels = _audio_params(risposta.headers.get("content-type", ""))
    audio = _pcm_to_wav(
        risposta.content,
        rate=rate,
        channels=channels,
        target_rate=TTS_SAMPLE_RATE,
    )
    cache.scrivi_tts(testo, TTS_CACHE_MODEL, voce, audio)
    return audio
