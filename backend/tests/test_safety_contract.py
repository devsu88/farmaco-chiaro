"""Contract tests for the safety-critical configuration.

These do not test the model: they pin the clauses and the data contract that
the product relies on. A change to the chat prompt, the ETR prompt or the
scenario file that drops a safety rule fails here before it reaches review.
"""
from __future__ import annotations

import json

from app.config import SCENARI_FILE
from graph.chat_graph import SYSTEM_PROMPT
from services.simplify import (
    ETR_MAX_DOMANDE,
    ETR_MAX_FRASI,
    ETR_MAX_GLOSSARIO,
    ETR_SYSTEM_PROMPT,
)

URGENZE = {"normale", "contatta_medico", "emergenza"}


def test_chat_prompt_keeps_grounding_rules():
    for clause in (
        "RISPONDI SOLO usando",
        "NON inventare dosaggi",
        "Non dare consigli medici personalizzati",
        "Ogni risposta deve citare la fonte",
        "Non ho trovato questa informazione nel foglio illustrativo",
    ):
        assert clause in SYSTEM_PROMPT, clause


def test_simplify_prompt_keeps_doses_and_limits():
    for clause in (
        "Dosaggi e scadenze devono rimanere esatti",
        "Non inventare informazioni",
        "Massimo 7 frasi",
    ):
        assert clause in ETR_SYSTEM_PROMPT, clause
    assert (ETR_MAX_FRASI, ETR_MAX_GLOSSARIO, ETR_MAX_DOMANDE) == (7, 3, 3)


def test_every_scenario_has_source_query_urgency_action_and_fallback():
    data = json.loads(SCENARI_FILE.read_text(encoding="utf-8"))
    scenari = data["scenari"]
    assert scenari
    for scenario in scenari:
        for field in ("id", "titolo", "query", "ancore", "azione", "urgenza", "fallback_risposta"):
            assert scenario.get(field), f"{scenario.get('id')}: missing {field}"
        assert scenario["urgenza"] in URGENZE, scenario["id"]
        assert any(
            word in scenario["azione"]
            for word in ("medico", "farmacista", "112", "118", "Centro Antiveleni")
        ), f"{scenario['id']}: no redirect in azione"


def test_red_flag_scenario_escalates_to_emergency_number():
    data = json.loads(SCENARI_FILE.read_text(encoding="utf-8"))
    scenario = next(item for item in data["scenari"] if item["id"] == "reazione_avversa")
    assert scenario["urgenza"] in {"contatta_medico", "emergenza"}
    assert "112" in scenario["azione"]
    assert "difficoltà a respirare" in scenario["azione"].lower()


def test_scenarios_are_cited_or_explicitly_missing():
    """A scenario either returns a source block or an explicit fallback."""
    from services.scenari import risolvi_scenario

    for farmaco_id in ("012745_01", "025669_01"):
        result = risolvi_scenario("dose_dimenticata", farmaco_id)
        assert result["trovato"] is True
        assert result["fonti"]
        assert result["fonti"][0]["blocco_id"]

    result = risolvi_scenario("dose_doppia", "012745_01")
    assert result["trovato"] is False
    assert result["fonti"] == []
    assert result["risposta"].strip()
