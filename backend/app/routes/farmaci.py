"""Route per i farmaci: lista, dettaglio preview e documento citabile."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from app import farmaci
from app.config import CATALOGO_FILE
from app.schemas import DocumentoResponse, FarmacoDetail, FarmacoPreview
from services.documento import documento as documento_farmaco

router = APIRouter()


def _load_catalogo() -> list[dict]:
    if not CATALOGO_FILE.exists():
        raise HTTPException(status_code=500, detail="Catalogo farmaci non trovato")
    return json.loads(CATALOGO_FILE.read_text(encoding="utf-8"))


@router.get("/farmaci", response_model=list[FarmacoPreview])
def list_farmaci() -> list[dict]:
    """Restituisce la lista di tutti i farmaci disponibili (preview)."""
    return [
        {
            "id": f.id,
            "nome": f.nome,
            "principio_attivo": f.principio_attivo,
        }
        for f in farmaci.all()
    ]


@router.get("/farmaci/{farmaco_id}", response_model=FarmacoDetail)
def get_farmaco(farmaco_id: str) -> dict:
    """Restituisce il dettaglio preview (catalogo JSON) di un farmaco."""
    if farmaci.get(farmaco_id) is None:
        raise HTTPException(status_code=404, detail=f"Farmaco {farmaco_id} non trovato")

    catalogo = _load_catalogo()
    for farmaco in catalogo:
        if farmaco["id"] == farmaco_id:
            return farmaco
    raise HTTPException(status_code=404, detail=f"Farmaco {farmaco_id} non trovato")


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
            detail="Documento non indicizzato. Esegui index/build_index.py",
        )
    return risultato
