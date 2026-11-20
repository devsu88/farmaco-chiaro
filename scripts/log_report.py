#!/usr/bin/env python3
"""Aggrega i log JSON di Farmaco Chiaro.

Legge JSONL da un file o da stdin e produce latenza, status, 429, 5xx, token
per modello e costo stimato. Le soglie opzionali fanno uscire con codice 1,
così il comando può essere usato in un job di budget.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

TOKEN_FIELDS = ("prompt_tokens", "completion_tokens", "total_tokens")


def parse_lines(lines) -> list[dict]:
    events: list[dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _int(value) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _float(value) -> float:
    try:
        return max(0.0, float(value or 0))
    except (TypeError, ValueError):
        return 0.0


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((p / 100) * (len(ordered) - 1)))))
    return round(ordered[index], 1)


def summarize(
    events: list[dict],
    usd_per_1m_input: float = 0.0,
    usd_per_1m_output: float = 0.0,
) -> dict:
    http = [event for event in events if event.get("event") == "http_request"]
    durations = [
        _float(event["duration_ms"])
        for event in http
        if "duration_ms" in event
    ]
    statuses = Counter(
        str(_int(event["status"]))
        for event in http
        if "status" in event
    )

    models: dict[str, dict[str, int]] = defaultdict(lambda: {field: 0 for field in TOKEN_FIELDS})
    without_usage = 0
    for event in events:
        if event.get("event") not in {"chat_completed", "simplify_completed"}:
            continue
        model = str(event.get("model") or "unknown")
        prompt = _int(event.get("prompt_tokens"))
        completion = _int(event.get("completion_tokens"))
        total = _int(event.get("total_tokens")) or prompt + completion
        models[model]["prompt_tokens"] += prompt
        models[model]["completion_tokens"] += completion
        models[model]["total_tokens"] += total
        if total == 0:
            without_usage += 1

    token_totals = {
        field: sum(model[field] for model in models.values())
        for field in TOKEN_FIELDS
    }
    cost = (
        token_totals["prompt_tokens"] / 1_000_000 * usd_per_1m_input
        + token_totals["completion_tokens"] / 1_000_000 * usd_per_1m_output
    )

    return {
        "events": len(events),
        "requests": len(http),
        "statuses": dict(sorted(statuses.items())),
        "rate_limited": sum(1 for event in http if _int(event.get("status")) == 429),
        "errors_5xx": sum(1 for event in http if _int(event.get("status")) >= 500),
        "p50_ms": percentile(durations, 50),
        "p95_ms": percentile(durations, 95),
        "cache_hits": sum(
            1
            for event in events
            if event.get("event") == "simplify_completed" and event.get("cached") is True
        ),
        "models": dict(sorted(models.items())),
        "tokens": token_totals,
        "events_without_usage": without_usage,
        "estimated_cost_usd": round(cost, 6),
    }


def threshold_failures(
    summary: dict,
    max_tokens: int | None = None,
    max_errors: int | None = None,
    max_429: int | None = None,
) -> list[str]:
    failures: list[str] = []
    if max_tokens is not None and summary["tokens"]["total_tokens"] > max_tokens:
        failures.append(
            f"token totali {summary['tokens']['total_tokens']} > soglia {max_tokens}"
        )
    if max_errors is not None and summary["errors_5xx"] > max_errors:
        failures.append(f"errori 5xx {summary['errors_5xx']} > soglia {max_errors}")
    if max_429 is not None and summary["rate_limited"] > max_429:
        failures.append(f"429 {summary['rate_limited']} > soglia {max_429}")
    return failures


def _load(path: str):
    if path == "-":
        return sys.stdin
    return Path(path).read_text(encoding="utf-8").splitlines()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report dei log JSON di Farmaco Chiaro")
    parser.add_argument("logs", nargs="?", default="-", help="file JSONL o - per stdin")
    parser.add_argument("--json", action="store_true", help="output JSON")
    parser.add_argument("--max-tokens", type=int)
    parser.add_argument("--max-errors", type=int)
    parser.add_argument("--max-429", type=int)
    parser.add_argument("--usd-per-1m-input", type=float, default=0.0)
    parser.add_argument("--usd-per-1m-output", type=float, default=0.0)
    args = parser.parse_args(argv)

    events = parse_lines(_load(args.logs))
    summary = summarize(
        events,
        usd_per_1m_input=args.usd_per_1m_input,
        usd_per_1m_output=args.usd_per_1m_output,
    )

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"eventi: {summary['events']} (http: {summary['requests']})")
        print(f"status: {summary['statuses']}")
        print(f"latenza: p50={summary['p50_ms']} ms p95={summary['p95_ms']} ms")
        print(f"429: {summary['rate_limited']} | 5xx: {summary['errors_5xx']}")
        print(f"cache hit: {summary['cache_hits']}")
        for model, tokens in summary["models"].items():
            print(
                f"  {model}: prompt={tokens['prompt_tokens']} "
                f"completion={tokens['completion_tokens']} "
                f"total={tokens['total_tokens']}"
            )
        print(f"token totali: {summary['tokens']['total_tokens']}")
        print(f"eventi senza usage: {summary['events_without_usage']}")
        print(f"costo stimato: {summary['estimated_cost_usd']} USD")

    failures = threshold_failures(
        summary,
        max_tokens=args.max_tokens,
        max_errors=args.max_errors,
        max_429=args.max_429,
    )
    for failure in failures:
        print(f"soglia superata: {failure}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
