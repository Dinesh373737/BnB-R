from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from pydantic import BaseModel
from .runner import ScenarioRunner
from .schemas import ScenarioConfig, ScenarioResult

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])
runner = ScenarioRunner()

class RunScenarioRequest(BaseModel):
    scenario_id: str
    base_state: Dict[str, Any]

@router.get("/", response_model=Dict[str, ScenarioConfig])
async def get_all_scenarios():
    """List all available edge-case scenarios."""
    return runner.get_available_scenarios()

@router.post("/run", response_model=ScenarioResult)
async def run_scenario(request: RunScenarioRequest):
    """Apply a scenario to a given base microgrid state."""
    try:
        result = runner.apply_scenario(base_state=request.base_state, scenario_id=request.scenario_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
