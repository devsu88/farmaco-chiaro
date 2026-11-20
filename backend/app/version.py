"""Identità della build esposta da /health.

Su Vercel ``VERCEL_GIT_COMMIT_SHA`` è il valore autorevole. In locale o in un
container senza quella variabile il campo resta ``unknown``: meglio dire che
non si sa, piuttosto che inventare uno SHA.
"""
from __future__ import annotations

import os


def _env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return "unknown"


COMMIT_SHA = _env("VERCEL_GIT_COMMIT_SHA", "GIT_COMMIT_SHA")
BUILD_TIME = _env("BUILD_TIME")
