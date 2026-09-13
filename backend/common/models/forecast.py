"""GridMind — forecasts table: ML prediction records."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, String, DateTime
from backend.common.database import Base


class ForecastRecord(Base):
    __tablename__ = "forecasts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    simulation_run_id = Column(Integer, nullable=True, index=True)
    forecast_type = Column(String(20), nullable=False)       # ForecastType: demand/solar/wind
    current_value = Column(Float, nullable=True)
    forecast_value = Column(Float, nullable=True)
    lower_bound = Column(Float, nullable=True)               # Uncertainty range
    upper_bound = Column(Float, nullable=True)
    confidence = Column(String(10), default="medium")        # ForecastConfidence
    horizon_minutes = Column(Integer, default=60)
    model_type = Column(String(20), default="xgboost")       # MLModelType
    data_source = Column(String(20), default="simulated")
