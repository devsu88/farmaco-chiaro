"""
Factory condivisa per i client LLM (OpenRouter).

Note importanti:
- I modelli "reasoning" (es. nvidia/nemotron-3-ultra) consumano i token nel
  ragionamento e restituiscono content=null se non si disabilita il reasoning.
- Il free tier può impiegare 15-30s: il timeout deve essere ampio e i retry
  disabilitati, altrimenti la richiesta raddoppia/triplica la latenza.
"""
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()

CHAT_MODEL = os.getenv("CHAT_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")
SIMPLIFY_MODEL = os.getenv("SIMPLIFY_MODEL", CHAT_MODEL)

# Timeout in secondi per singola richiesta
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "90"))


def has_valid_api_key() -> bool:
    """Verifica che la key esista e non sia il placeholder di esempio."""
    if not OPENROUTER_API_KEY:
        return False
    placeholder = "la_tua_api_key_qui"
    return OPENROUTER_API_KEY != placeholder


def build_llm(model: str | None = None, temperature: float = 0.2, max_tokens: int = 2000) -> ChatOpenAI:
    """Crea un client OpenRouter con reasoning disabilitato e nessun retry."""
    return ChatOpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=OPENROUTER_API_KEY,
        model=model or SIMPLIFY_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=LLM_TIMEOUT,
        max_retries=0,
        # Disabilita il reasoning: senza questo, i modelli reasoning
        # restituiscono content=null e consumano tutti i token nel pensiero.
        extra_body={"reasoning": {"enabled": False}},
    )
