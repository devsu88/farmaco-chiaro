"""Test del report dai log, senza rete."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "log_report.py"
spec = importlib.util.spec_from_file_location("log_report_script", SCRIPT)
assert spec and spec.loader
report = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = report
spec.loader.exec_module(report)

EVENTS = [
    {"event": "http_request", "status": 200, "duration_ms": 100},
    {"event": "http_request", "status": 200, "duration_ms": 200},
    {"event": "http_request", "status": 200, "duration_ms": 300},
    {"event": "http_request", "status": 429, "duration_ms": 400},
    {"event": "http_request", "status": 500, "duration_ms": 500},
    {"event": "chat_completed", "model": "model-a", "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    {"event": "chat_completed", "model": "model-b", "prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
    {"event": "simplify_completed", "model": "model-a", "cached": True, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    {"event": "simplify_completed", "model": "model-a", "cached": False, "prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
]


def test_parse_ignora_righe_non_json():
    events = report.parse_lines(["", "non json", '{"event": "x"}', "[1,2]"])
    assert events == [{"event": "x"}]


def test_summarize_latenza_status_e_token():
    summary = report.summarize(EVENTS, usd_per_1m_input=1.0, usd_per_1m_output=2.0)

    assert summary["events"] == len(EVENTS)
    assert summary["requests"] == 5
    assert summary["statuses"] == {"200": 3, "429": 1, "500": 1}
    assert summary["rate_limited"] == 1
    assert summary["errors_5xx"] == 1
    assert summary["p50_ms"] == 300.0
    assert summary["p95_ms"] == 500.0
    assert summary["cache_hits"] == 1
    assert summary["tokens"] == {
        "prompt_tokens": 35,
        "completion_tokens": 20,
        "total_tokens": 55,
    }
    assert summary["models"]["model-a"] == {
        "prompt_tokens": 15,
        "completion_tokens": 10,
        "total_tokens": 25,
    }
    assert summary["events_without_usage"] == 1
    assert summary["estimated_cost_usd"] == 0.000075


def test_soglie():
    summary = report.summarize(EVENTS)
    assert report.threshold_failures(summary) == []
    assert len(report.threshold_failures(summary, max_tokens=10)) == 1
    assert len(report.threshold_failures(summary, max_errors=0)) == 1
    assert len(report.threshold_failures(summary, max_429=0)) == 1


def test_report_vuoto_non_esplode():
    summary = report.summarize([])
    assert summary["requests"] == 0
    assert summary["p50_ms"] == 0.0
    assert summary["tokens"]["total_tokens"] == 0
