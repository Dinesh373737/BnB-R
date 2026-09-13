"""Optional REST adapter for the isolated simulation module.

``backend.main`` intentionally remains untouched; an integration owner can
register this router later using the existing commented registration hook.
"""

from fastapi import APIRouter, HTTPException

from backend.common.exceptions import GridMindError
from backend.common.schemas.microgrid_state import MicrogridState
from backend.modules.simulation.service import SimulationService
from backend.modules.simulation.schemas import (
    ControlInputs,
    EnvironmentalConditions,
    PrimaryScenarioRequest,
    SimulationConfig,
    SimulationStepResult,
)


router = APIRouter(prefix="/simulation")
_service = SimulationService()


@router.post("/initialize", response_model=MicrogridState)
def initialize_simulation(config: SimulationConfig | None = None) -> MicrogridState:
    """Start a new in-memory simulation run with the supplied configuration."""
    global _service
    _service = SimulationService(config)
    return _service.initialize()


@router.get("/state", response_model=MicrogridState)
def get_simulation_state() -> MicrogridState:
    """Return the latest central microgrid state."""
    try:
        return _service.get_state()
    except GridMindError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/step", response_model=MicrogridState)
def step_simulation(
    controls: ControlInputs | None = None,
    conditions: EnvironmentalConditions | None = None,
) -> MicrogridState:
    """Execute one physical timestep using optional resolved controls."""
    try:
        return _service.step(controls=controls, conditions=conditions)
    except GridMindError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/last-result", response_model=SimulationStepResult)
def get_last_result() -> SimulationStepResult:
    """Return detailed accounting unavailable in the shared state schema."""
    try:
        return _service.get_last_result()
    except GridMindError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/scenarios/primary")
def activate_primary_crisis(request: PrimaryScenarioRequest) -> dict[str, str | int | None]:
    """Schedule the solar −50% / flexible-demand +30% crisis."""
    scenario = _service.apply_primary_crisis(
        start_timestep=request.start_timestep,
        duration_steps=request.duration_steps,
    )
    return {
        "scenario": scenario.scenario_type.value,
        "start_timestep": scenario.start_timestep,
        "duration_steps": scenario.duration_steps,
    }


@router.post("/run", response_model=list[MicrogridState])
def run_simulation_loop() -> list[MicrogridState]:
    """Run the fixed 13-step simulation loop."""
    try:
        return _service.run()
    except GridMindError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
