"""Test dell'export dei log Vercel, senza rete e senza CLI reale."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "export_logs.py"
spec = importlib.util.spec_from_file_location("export_logs_script", SCRIPT)
assert spec and spec.loader
export = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = export
spec.loader.exec_module(export)

CLI_OUTPUT = "\n".join(
    [
        json.dumps(
            {
                "type": "log",
                "data": {
                    "timestamp": "2026-11-20T18:44:07.838Z",
                    "requestId": "req-1",
                    "message": (
                        "2026-11-20 18:44:07,837 INFO app.observability "
                        '{"event": "http_request", "request_id": "req-1", '
                        '"status": 200, "duration_ms": 10}'
                    ),
                },
            }
        ),
        json.dumps(
            {
                "type": "log",
                "data": {"timestamp": "t", "message": "INFO: Uvicorn running"},
            }
        ),
        json.dumps({"type": "summary", "recordsReturned": 2}),
    ]
)


def _runner(stdout: str = CLI_OUTPUT, returncode: int = 0, stderr: str = ""):
    def run(cmd, **kwargs):  # noqa: ANN001 - fake minimale
        run.cmd = cmd
        run.kwargs = kwargs
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)

    return run


def test_export_normalizza_e_salta_il_summary():
    events = export.export_logs(runner=_runner())

    assert events == [
        {
            "event": "http_request",
            "request_id": "req-1",
            "status": 200,
            "duration_ms": 10,
            "ts": "2026-11-20T18:44:07.838Z",
        }
    ]


def test_comando_usa_finestra_progetto_scope_e_non_espone_il_token():
    runner = _runner(stdout="")
    export.export_logs(
        since="50m", limit=500, project="farmaco-chiaro", scope="team-x", runner=runner
    )

    cmd = runner.cmd
    assert cmd[:3] == ["vercel", "logs", "--json"]
    assert cmd[cmd.index("--since") + 1] == "50m"
    assert cmd[cmd.index("--limit") + 1] == "500"
    assert cmd[cmd.index("--project") + 1] == "farmaco-chiaro"
    assert cmd[cmd.index("--scope") + 1] == "team-x"
    assert "--token" not in cmd


def test_cli_fallita_riporta_lo_stderr():
    with pytest.raises(RuntimeError, match="boom"):
        export.export_logs(runner=_runner(returncode=1, stderr="boom"))


def test_write_events_append_non_duplica(tmp_path):
    path = tmp_path / "logs.jsonl"
    primo = [{"event": "http_request", "ts": "t1", "request_id": "r1", "status": 200}]
    secondo = [
        {"event": "http_request", "ts": "t1", "request_id": "r1", "status": 200},
        {"event": "http_request", "ts": "t2", "request_id": "r2", "status": 200},
    ]

    assert export.write_events(primo, path, append=False) == 1
    assert export.write_events(secondo, path, append=True) == 1
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2
