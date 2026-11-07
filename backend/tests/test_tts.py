import io
import struct
import uuid
import wave

from fastapi.testclient import TestClient

from app.main import app
from services.tts import _pcm_to_wav

client = TestClient(app)


def test_pcm_to_wav_produce_un_wav_valido():
    pcm = b"\x00\x00" * 100
    wav = _pcm_to_wav(pcm, rate=44100, channels=1)
    assert wav[:4] == b"RIFF"
    assert wav[8:12] == b"WAVE"
    # dimensione RIFF = 36 + dati
    assert struct.unpack("<I", wav[4:8])[0] == 36 + len(pcm)


def test_pcm_to_wav_riduce_la_frequenza():
    pcm = b"\x00\x00" * 44100
    wav = _pcm_to_wav(pcm, rate=44100, channels=1, target_rate=16000)
    with wave.open(io.BytesIO(wav), "rb") as letto:
        assert letto.getframerate() == 16000
        assert letto.getnframes() == 16000


def test_tts_senza_api_key_restituisce_503(monkeypatch):
    monkeypatch.setattr("services.tts.has_valid_api_key", lambda: False)
    risposta = client.post(
        "/api/tts",
        json={"testo": f"Testo unico {uuid.uuid4()}"},
    )
    assert risposta.status_code == 503
