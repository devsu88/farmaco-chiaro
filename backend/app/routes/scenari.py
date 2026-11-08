"""Route degli scenari "Cosa faccio se...?"."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas import (
    ScenarioRequest,
    ScenarioResponse,
    ScenariResponse,
)
from services.scenari import elenco_scenari, risolvi_scenario

router = APIRouter()


@router.get("/scenari", response_model=ScenariResponse)
def get_scenari() -> dict:
    """Elenca gli scenari disponibili per il wizard."""
    return {"scenari": elenco_scenari()}


@router.post("/scenari/{scenario_id}", response_model=ScenarioResponse)
def post_scenario(scenario_id: str, req: ScenarioRequest) -> dict:
    """Risolve uno scenario per un farmaco, citando il foglio."""
    try:
        return risolvi_scenario(scenario_id, req.farmaco_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
