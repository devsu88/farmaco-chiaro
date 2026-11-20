"""Unit test dello sliding window usato dagli endpoint costosi."""
from __future__ import annotations

from app.rate_limit import Limit, SlidingWindowLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def avanza(self, secondi: float) -> None:
        self.now += secondi


def test_consente_fino_al_limite_poi_rifiuta():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(clock=clock)
    limit = Limit(2, 60)

    assert limiter.hit("k", limit) == (True, 0, 1)
    assert limiter.hit("k", limit) == (True, 0, 0)

    consentito, retry_after, rimanenti = limiter.hit("k", limit)
    assert consentito is False
    assert retry_after >= 1
    assert rimanenti == 0


def test_riapre_dopo_la_finestra():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(clock=clock)
    limit = Limit(1, 60)

    assert limiter.hit("k", limit)[0] is True
    assert limiter.hit("k", limit)[0] is False

    clock.avanza(61)
    assert limiter.hit("k", limit)[0] is True


def test_chiavi_separate_non_si_influenzano():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(clock=clock)
    limit = Limit(1, 60)

    assert limiter.hit("chat:1.1.1.1", limit)[0] is True
    assert limiter.hit("chat:2.2.2.2", limit)[0] is True
    assert limiter.hit("chat:1.1.1.1", limit)[0] is False
    assert limiter.hit("tts:1.1.1.1", limit)[0] is True


def test_reset_azzera_la_finestra():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(clock=clock)
    limit = Limit(1, 60)

    assert limiter.hit("k", limit)[0] is True
    limiter.reset()
    assert limiter.hit("k", limit)[0] is True
