import uuid

from services.simplify import _chunk_text, semplifica

RISPOSTA = """
{"una_frase": "Serve per il dolore.",
 "versione_facile": ["Prendi una compressa."],
 "glossario": [{"termine": "analgesico", "spiegazione": "che toglie il dolore"}],
 "domande_farmacista": ["Quante compresse al giorno?"],
 "entita_verificate": {"dosaggi_preservati": true, "note": ""}}
"""


class _Risposta:
    content = RISPOSTA


class _LLM:
    model_name = "fake-model"

    def __init__(self):
        self.chiamate = 0

    def invoke(self, messages):
        self.chiamate += 1
        return _Risposta()


def test_chunk_text_spezza_testi_lunghi():
    testo = "\n\n".join(["paragrafo " * 200] * 4)
    chunks = _chunk_text(testo, max_chars=1000)
    assert len(chunks) > 1
    assert all(len(chunk) <= 1000 for chunk in chunks)


def test_semplifica_testo_lungo_unisce_i_risultati():
    testo = "\n\n".join(["paragrafo " * 200] * 3) + f"\n\n{uuid.uuid4()}"
    risultato = semplifica(testo, _LLM(), max_chars=1000)
    assert risultato["una_frase"] == "Serve per il dolore."
    assert risultato["versione_facile"]
    assert "Semplificato in" in risultato["entita_verificate"]["note"]


def test_semplifica_usa_la_cache_persistente():
    llm = _LLM()
    testo = f"Testo unico per il test della cache persistente {uuid.uuid4()}."

    primo = semplifica(testo, llm)
    secondo = semplifica(testo, llm)

    assert primo["cached"] is False
    assert secondo["cached"] is True
    assert llm.chiamate == 1
