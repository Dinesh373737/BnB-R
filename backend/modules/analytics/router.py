"""Analytics module — FastAPI router.

Exposes REST endpoints for:
    * Retrieving GridMind analytics for a simulation run.
    * Retrieving a baseline-vs-GridMind comparison.
    * Triggering analytics calculation on demand.

Follows the project's existing API conventions (prefix, response models,
error handling via HTTPException).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.common.database import get_db_session
from backend.common.schemas.enums import AnalyticsMode
from backend.modules.analytics.schemas import (
    AnalyticsRequest,
    AnalyticsResponse,
    ComparisonResponse,
)
from backend.modules.analytics.service import AnalyticsService


router = APIRouter(prefix="/analytics", tags=["analytics"])


def _get_service(db: Session = Depends(get_db_session)) -> AnalyticsService:
    return AnalyticsService(db)


@router.get(
    "/latest/run",
    summary="Get the most recent simulation run id",
)
def get_latest_run(
    db: Session = Depends(get_db_session),
) -> dict:
    """Return the id of the newest completed simulation run (or None)."""
    from backend.common.models.simulation import SimulationRunRecord

    record = (
        db.query(SimulationRunRecord)
        .order_by(SimulationRunRecord.id.desc())
        .first()
    )
    return {"latest_run_id": record.id if record else None}


@router.get(
    "/hopfield/current",
    summary="Hopfield energy of the live microgrid state",
)
def get_hopfield_energy() -> dict:
    """Compute the continuous Hopfield energy for the current microgrid.

    E = -1/2 Σ w_ij s_i s_j + Σ θ_i s_i, with neuron states mapped from the
    live simulation state (renewables, battery, grid dependency, demand,
    critical protection). Used by the 3D energy-landscape visualization.
    """
    from backend.modules.analytics.hopfield import hopfield_energy
    from backend.modules.simulation.router import _service

    try:
        if not _service.is_initialized:
            _service.initialize()
        state = _service.get_state()
        return {"success": True, **hopfield_energy(state)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/{simulation_run_id}",
    response_model=AnalyticsResponse,
    summary="Get GridMind analytics for a simulation run",
)
def get_analytics(
    simulation_run_id: int,
    service: AnalyticsService = Depends(_get_service),
) -> AnalyticsResponse:
    """Retrieve (or calculate on-the-fly) GridMind metrics for the given
    simulation run.
    """
    try:
        metrics = service.get_analytics(simulation_run_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return AnalyticsResponse(
        success=True,
        message="GridMind analytics retrieved",
        simulation_run_id=simulation_run_id,
        mode=AnalyticsMode.GRIDMIND,
        metrics=metrics,
    )


@router.get(
    "/{simulation_run_id}/comparison",
    response_model=ComparisonResponse,
    summary="Get baseline vs GridMind comparison",
)
def get_comparison(
    simulation_run_id: int,
    service: AnalyticsService = Depends(_get_service),
) -> ComparisonResponse:
    """Run the baseline controller under the same scenario, calculate metrics
    for both controllers, and return a side-by-side comparison with
    improvement deltas.
    """
    try:
        comparison = service.get_comparison(simulation_run_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ComparisonResponse(
        success=True,
        message="Baseline vs GridMind comparison complete",
        comparison=comparison,
    )


@router.post(
    "/{simulation_run_id}/calculate",
    response_model=AnalyticsResponse,
    summary="Trigger analytics calculation and persist results",
)
def calculate_analytics(
    simulation_run_id: int,
    service: AnalyticsService = Depends(_get_service),
) -> AnalyticsResponse:
    """Calculate GridMind metrics for the given simulation run and persist
    the results to the ``analytics_results`` table.
    """
    try:
        metrics = service.calculate_and_persist(simulation_run_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return AnalyticsResponse(
        success=True,
        message="Analytics calculated and persisted",
        simulation_run_id=simulation_run_id,
        mode=AnalyticsMode.GRIDMIND,
        metrics=metrics,
    )
