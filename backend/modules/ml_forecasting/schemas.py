"""
ML Forecasting — Pydantic Schemas
====================================
Request/response models for the ML prediction engine.
Structured for consumption by the future Risk & Forecast Agent.
"""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


# ═══════════════════════════════════════════════════════════════════════════
#  FORECAST REQUEST / RESPONSE
# ═══════════════════════════════════════════════════════════════════════════


class ForecastRequest(BaseModel):
    """Request schema for generating a single forecast."""

    forecast_type: str = Field(
        ..., description="Type of forecast: demand, solar, or wind"
    )
    horizon_minutes: int = Field(
        60, ge=1, le=1440, description="Forecast horizon in minutes"
    )
    current_value: Optional[float] = Field(
        None, description="Current observed value (optional, for lag context)"
    )
    temperature_c: Optional[float] = Field(
        None, description="Current temperature in Celsius"
    )
    cloud_cover_pct: Optional[float] = Field(
        None, ge=0, le=100, description="Cloud cover percentage"
    )
    wind_speed_ms: Optional[float] = Field(
        None, ge=0, description="Wind speed in m/s"
    )
    solar_radiation_wm2: Optional[float] = Field(
        None, ge=0, description="Solar radiation in W/m²"
    )

    model_config = ConfigDict(from_attributes=True)


class ForecastResult(BaseModel):
    """Response schema for a single forecast prediction with uncertainty."""

    forecast_type: str = Field(..., description="Type: demand, solar, or wind")
    timestamp: datetime = Field(..., description="Timestamp of the forecast")
    current_value: Optional[float] = Field(
        None, description="Current observed value"
    )
    prediction: float = Field(..., description="Predicted value")
    lower: float = Field(..., description="Lower bound of prediction interval")
    upper: float = Field(..., description="Upper bound of prediction interval")
    confidence: str = Field("medium", description="Confidence level: low, medium, high")
    horizon_minutes: int = Field(60, description="Forecast horizon in minutes")
    model_type: str = Field("xgboost", description="ML model used")
    unit: str = Field("kW", description="Unit of measurement")

    model_config = ConfigDict(from_attributes=True)


# ═══════════════════════════════════════════════════════════════════════════
#  PREDICTIONS SUMMARY
# ═══════════════════════════════════════════════════════════════════════════


class PredictionsSummary(BaseModel):
    """Response schema for /api/predictions — all forecasts at once."""

    timestamp: datetime
    demand: Optional[ForecastResult] = None
    solar: Optional[ForecastResult] = None
    wind: Optional[ForecastResult] = None
    total_generation_forecast: Optional[float] = Field(
        None, description="solar + wind predicted generation"
    )
    net_position: Optional[float] = Field(
        None, description="generation - demand (positive = surplus)"
    )

    model_config = ConfigDict(from_attributes=True)


# ═══════════════════════════════════════════════════════════════════════════
#  TRAINING
# ═══════════════════════════════════════════════════════════════════════════


class TrainRequest(BaseModel):
    """Request schema for triggering model training."""

    forecast_types: List[str] = Field(
        default=["demand", "solar", "wind"],
        description="Which models to train: demand, solar, wind",
    )
    force_retrain: bool = Field(
        False, description="Force retraining even if a model already exists"
    )


class TrainResult(BaseModel):
    """Training result for a single model."""

    forecast_type: str
    status: str  # "success" or "error"
    mae: Optional[float] = None
    rmse: Optional[float] = None
    mape: Optional[float] = None
    train_samples: Optional[int] = None
    val_samples: Optional[int] = None
    test_samples: Optional[int] = None
    message: Optional[str] = None


class TrainResponse(BaseModel):
    """Response for the training endpoint."""

    results: List[TrainResult]
    models_dir: str
