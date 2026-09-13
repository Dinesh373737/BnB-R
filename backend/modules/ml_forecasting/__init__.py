"""
GridMind — Module 2: ML Prediction Engine
===========================================
Machine learning forecasting for Demand, Solar, and Wind generation
with calibrated uncertainty estimation.

Exports:
    ForecastingService  — Central forecasting service
    router              — FastAPI endpoints
    ForecastRequest     — Prediction request schema
    ForecastResult      — Prediction result schema with uncertainty
    PredictionsSummary  — Combined predictions summary
"""

from backend.modules.ml_forecasting.schemas import (
    ForecastRequest,
    ForecastResult,
    PredictionsSummary,
    TrainRequest,
    TrainResponse,
    TrainResult,
)
from backend.modules.ml_forecasting.service import ForecastingService
from backend.modules.ml_forecasting.router import router

__all__ = [
    "ForecastingService",
    "router",
    "ForecastRequest",
    "ForecastResult",
    "PredictionsSummary",
    "TrainRequest",
    "TrainResponse",
    "TrainResult",
]
