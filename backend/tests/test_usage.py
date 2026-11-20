"""Estrazione e somma dell'usage del provider, senza chiamate reali."""
from __future__ import annotations

from types import SimpleNamespace

import graph.chat_graph as chat_graph
from app.usage import empty_usage, merge_usage, usage_from_message
from services.simplify import _chiama_modello, _merge


class FakeLLM:
    def __init__(self, content: str, usage: dict | None = None) -> None:
        self.content = content
        self.usage = usage or {}

    def invoke(self, messages):  # noqa: ANN001 - fake minimale
        return SimpleNamespace(content=self.content, usage_metadata=self.usage)


def test_usage_from_message_legge_input_output():
    message = SimpleNamespace(
        usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    )
    assert usage_from_message(message) == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }


def test_usage_from_message_accetta_i_nomi_del_provider():
    message = SimpleNamespace(
        usage_metadata={"prompt_tokens": 7, "completion_tokens": 3}
    )
    assert usage_from_message(message) == {
        "prompt_tokens": 7,
        "completion_tokens": 3,
        "total_tokens": 10,
    }


def test_usage_assente_vale_zero():
    assert usage_from_message(SimpleNamespace(usage_metadata=None)) == empty_usage()


def test_merge_usage_somma_i_campi():
    assert merge_usage(
        {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    ) == {"prompt_tokens": 11, "completion_tokens": 22, "total_tokens": 33}


def test_genera_somma_l_usage_allo_stato(monkeypatch):
    llm = FakeLLM(
        '{"risposta": "ok", "fonti": [], "informazione_trovata": true}',
        {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    )
    monkeypatch.setattr(chat_graph, "get_llm", lambda: llm)

    state = {
        "messaggi": [{"ruolo": "utente", "testo": "posso?"}],
        "farmaco_id": "012745_01",
        "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
    }
    risultato = chat_graph._genera(state, "contesto", [], False)

    assert risultato["usage"] == {
        "prompt_tokens": 11,
        "completion_tokens": 7,
        "total_tokens": 18,
    }


def test_chiama_modello_allega_l_usage():
    llm = FakeLLM(
        '{"una_frase": "Serve per la febbre.", "versione_facile": ["Una frase."]}',
        {"input_tokens": 4, "output_tokens": 6, "total_tokens": 10},
    )
    risultato = _chiama_modello(llm, "testo", 0, 1)

    assert risultato["usage"] == {
        "prompt_tokens": 4,
        "completion_tokens": 6,
        "total_tokens": 10,
    }


def test_merge_somma_l_usage_delle_parti():
    parti = [
        {
            "una_frase": "a",
            "versione_facile": ["a"],
            "glossario": [],
            "domande_farmacista": [],
            "entita_verificate": {"dosaggi_preservati": True, "note": ""},
            "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        },
        {
            "una_frase": "b",
            "versione_facile": ["b"],
            "glossario": [],
            "domande_farmacista": [],
            "entita_verificate": {"dosaggi_preservati": True, "note": ""},
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        },
    ]

    assert _merge(parti, 2)["usage"] == {
        "prompt_tokens": 11,
        "completion_tokens": 22,
        "total_tokens": 33,
    }
