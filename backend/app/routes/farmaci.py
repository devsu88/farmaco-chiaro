"""Route per i farmaci: dettaglio, documento citabile, guida e scheda."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app import farmaci
from app.schemas import (
    DocumentoResponse,
    FarmacoDetail,
    GuidaResponse,
    SchedaResponse,
)
from services.documento import documento as documento_farmaco
from services.guida import guida as guida_farmaco
from services.retrieval import blocchi_per_farmaco
from services.scheda import scheda as scheda_farmaco

router = APIRouter()


@router.get("/farmaci/{farmaco_id}", response_model=FarmacoDetail)
def get_farmaco(farmaco_id: str) -> dict:
    """Dettaglio del foglio: dati di registro e sezioni testuali."""
    farmaco = farmaci.get(farmaco_id)
    if farmaco is None:
        raise HTTPException(status_code=404, detail=f"Farmaco {farmaco_id} non trovato")

    sezioni: dict[str, str] = {}
    for blocco in blocchi_per_farmaco(farmaco_id):
        chiave = blocco.get("sezione_key") or blocco.get("sezione", "")
        sezioni.setdefault(chiave, "")
        sezioni[chiave] = (sezioni[chiave] + "\n\n" + blocco["testo"]).strip()

    return {
        "id": farmaco.id,
        "nome": farmaco.nome,
        "principio_attivo": farmaco.principio_attivo,
        "sezioni": sezioni,
    }


@router.get("/farmaci/{farmaco_id}/documento", response_model=DocumentoResponse)
def get_documento(farmaco_id: str) -> dict:
    """Restituisce il foglio illustrativo completo, sezionato e citabile."""
    try:
        risultato = documento_farmaco(farmaco_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Farmaco {farmaco_id} non trovato")

    if not risultato["sezioni"]:
        raise HTTPException(
            status_code=404,
            detail="Documento non indicizzato. Esegui `python -m aifa_rag.cli dataset`",
        )
    return risultato


@router.get("/farmaci/{farmaco_id}/guida", response_model=GuidaResponse)
def get_guida(farmaco_id: str) -> dict:
    """Percorso guidato in quattro schermate, estratto dal foglio."""
    try:
        return guida_farmaco(farmaco_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Farmaco {farmaco_id} non trovato")


@router.get("/farmaci/{farmaco_id}/scheda", response_model=SchedaResponse)
def get_scheda(farmaco_id: str) -> dict:
    """Scheda condivisibile per un familiare o un caregiver."""
    try:
        return scheda_farmaco(farmaco_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Farmaco {farmaco_id} non trovato")
