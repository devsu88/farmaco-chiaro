"""Test del report dai log, senza rete."""
from __future__ import annotations

import importlib.util
import json
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


VERCEL_ENVELOPE = {
    "type": "log",
    "data": {
        "timestamp": "2026-11-20T18:44:07.838Z",
        "requestId": "req-1",
        "deploymentId": "dpl_1",
        "message": (
            "2026-11-20 18:44:07,837 INFO app.observability "
            '{"event": "http_request", "request_id": "req-1", "status": 422, '
            '"duration_ms": 32.3}'
        ),
    },
}


def test_parse_lines_legge_l_envelope_di_vercel():
    events = report.parse_lines([json.dumps(VERCEL_ENVELOPE)])

    assert events == [
        {
            "event": "http_request",
            "request_id": "req-1",
            "status": 422,
            "duration_ms": 32.3,
            "ts": "2026-11-20T18:44:07.838Z",
        }
    ]


def test_parse_lines_ignora_messaggi_non_strutturati_e_summary():
    startup = {
        "type": "log",
        "data": {"timestamp": "t", "message": "INFO: Uvicorn running on 0.0.0.0:8000"},
    }
    summary = {"type": "summary", "recordsReturned": 0}

    assert report.parse_lines([json.dumps(startup), json.dumps(summary)]) == []


def test_parse_lines_deduplica_gli_export_sovrapposti():
    lines = [json.dumps(VERCEL_ENVELOPE), json.dumps(VERCEL_ENVELOPE)]

    assert len(report.parse_lines(lines)) == 1
