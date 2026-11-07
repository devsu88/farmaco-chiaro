"""Ricerca sui fogli illustrativi, aggregata per farmaco."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas import SearchResponse
from services.retrieval import cerca_farmaci

router = APIRouter()


@router.get("/search", response_model=SearchResponse)
def search(q: str = Query(..., min_length=1, description="Query di ricerca")) -> dict:
    """Cerca per nome, principio attivo o sintomo nei testi indicizzati."""
    return {"query": q, "risultati": cerca_farmaci(q)}
