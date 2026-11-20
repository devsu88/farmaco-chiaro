"""Lettura e somma dell'usage restituito dal provider LLM.

LangChain espone `usage_metadata` con `input_tokens`/`output_tokens`; alcuni
provider usano `prompt_tokens`/`completion_tokens`. Se manca tutto, i campi
restano a zero: il report li tratta come "usage non disponibile".
"""
from __future__ import annotations

from typing import Any

FIELDS = ("prompt_tokens", "completion_tokens", "total_tokens")


def _int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def empty_usage() -> dict[str, int]:
    return {field: 0 for field in FIELDS}


def usage_from_message(message: Any) -> dict[str, int]:
    usage = getattr(message, "usage_metadata", None) or {}
    prompt = _int(usage.get("input_tokens", usage.get("prompt_tokens", 0)))
    completion = _int(usage.get("output_tokens", usage.get("completion_tokens", 0)))
    total = _int(usage.get("total_tokens", 0)) or prompt + completion
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
    }


def merge_usage(
    base: dict[str, int] | None, extra: dict[str, int] | None
) -> dict[str, int]:
    base = base or {}
    extra = extra or {}
    return {
        field: _int(base.get(field)) + _int(extra.get(field))
        for field in FIELDS
    }
