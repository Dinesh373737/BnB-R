"""
ML Forecasting — API Router
=============================
FastAPI router providing endpoints for Demand, Solar, and Wind forecasts,
predictions summary, and model retraining.

Endpoints:
    GET  /api/forecast/demand   — Demand forecast with uncertainty intervals
    GET  /api/forecast/solar    — Solar generation forecast with uncertainty intervals
    GET  /api/forecast/wind     — Wind generation forecast with uncertainty intervals
    GET  /api/predictions       — Consolidated predictions & net power position
    POST /api/forecast/train    — Trigger model training/retraining
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from backend.common.database import get_db_session
from backend.common.logger import get_module_logger
from backend.modules.ml_forecasting.schemas import (
    ForecastRequest,
    ForecastResult,
    PredictionsSummary,
    TrainRequest,
    TrainResponse,
)
from backend.modules.ml_forecasting.service import ForecastingService

log = get_module_logger("ml_forecasting.router")

router = APIRouter(tags=["Forecasting"])


def get_service() -> ForecastingService:
    """Dependency provider for ForecastingService singleton."""
    return ForecastingService.get_instance()


# ═══════════════════════════════════════════════════════════════════════════
#  FORECAST ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/forecast/demand", response_model=ForecastResult)
@router.get("/api/forecast/demand", response_model=ForecastResult, include_in_schema=False)
def get_demand_forecast(
    horizon_minutes: int = Query(60, ge=1, le=1440, description="Forecast horizon in minutes"),
    current_value: Optional[float] = Query(None, description="Current demand in kW"),
    temperature_c: Optional[float] = Query(None, description="Current temperature in Celsius"),
    service: ForecastingService = Depends(get_service),
    db: Session = Depends(get_db_session),
):
    """Retrieve the latest demand forecast with uncertainty intervals."""
    req = ForecastRequest(
        forecast_type="demand",
        horizon_minutes=horizon_minutes,
        current_value=current_value,
        temperature_c=temperature_c,
    )
    return service.predict_demand(request=req, db=db)


@router.get("/forecast/solar", response_model=ForecastResult)
@router.get("/api/forecast/solar", response_model=ForecastResult, include_in_schema=False)
def get_solar_forecast(
    horizon_minutes: int = Query(60, ge=1, le=1440, description="Forecast horizon in minutes"),
    current_value: Optional[float] = Query(None, description="Current solar output in kW"),
    temperature_c: Optional[float] = Query(None, description="Current temperature in Celsius"),
    cloud_cover_pct: Optional[float] = Query(None, ge=0, le=100, description="Cloud cover percentage"),
    solar_radiation_wm2: Optional[float] = Query(None, ge=0, description="Solar radiation W/m²"),
    service: ForecastingService = Depends(get_service),
    db: Session = Depends(get_db_session),
):
    """Retrieve the latest solar generation forecast with uncertainty intervals."""
    req = ForecastRequest(
        forecast_type="solar",
        horizon_minutes=horizon_minutes,
        current_value=current_value,
        temperature_c=temperature_c,
        cloud_cover_pct=cloud_cover_pct,
        solar_radiation_wm2=solar_radiation_wm2,
    )
    return service.predict_solar(request=req, db=db)


@router.get("/forecast/wind", response_model=ForecastResult)
@router.get("/api/forecast/wind", response_model=ForecastResult, include_in_schema=False)
def get_wind_forecast(
    horizon_minutes: int = Query(60, ge=1, le=1440, description="Forecast horizon in minutes"),
    current_value: Optional[float] = Query(None, description="Current wind output in kW"),
    temperature_c: Optional[float] = Query(None, description="Current temperature in Celsius"),
    wind_speed_ms: Optional[float] = Query(None, ge=0, description="Wind speed in m/s"),
    service: ForecastingService = Depends(get_service),
    db: Session = Depends(get_db_session),
):
    """Retrieve the latest wind generation forecast with uncertainty intervals."""
    req = ForecastRequest(
        forecast_type="wind",
        horizon_minutes=horizon_minutes,
        current_value=current_value,
        temperature_c=temperature_c,
        wind_speed_ms=wind_speed_ms,
    )
    return service.predict_wind(request=req, db=db)


@router.get("/predictions", response_model=PredictionsSummary)
@router.get("/api/predictions", response_model=PredictionsSummary, include_in_schema=False)
def get_all_predictions(
    service: ForecastingService = Depends(get_service),
    db: Session = Depends(get_db_session),
):
    """
    Retrieve consolidated predictions (demand, solar, wind) along with
    total generation forecast and net power position.
    """
    return service.predict_all(db=db)


# ═══════════════════════════════════════════════════════════════════════════
#  TRAINING ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/forecast/train", response_model=TrainResponse)
@router.post("/api/forecast/train", response_model=TrainResponse, include_in_schema=False)
def trigger_training(
    request: TrainRequest = TrainRequest(),
    service: ForecastingService = Depends(get_service),
):
    """
    Trigger training/retraining of one or more forecasting models.
    """
    valid_types = {"demand", "solar", "wind"}
    invalid = set(request.forecast_types) - valid_types
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid forecast types: {list(invalid)}. Must be in {list(valid_types)}",
        )
    return service.train(forecast_types=request.forecast_types, force=request.force_retrain)
