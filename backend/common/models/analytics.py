"""GridMind — analytics_results table: Computed metrics (GridMind vs Baseline)."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean
from backend.common.database import Base


class AnalyticsResultRecord(Base):
    __tablename__ = "analytics_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    simulation_run_id = Column(Integer, nullable=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    metric_category = Column(String(30), nullable=False)     # MetricCategory
    metric_name = Column(String(50), nullable=False)         # e.g. "total_cost", "peak_demand"
    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String(20), nullable=True)          # e.g. "kWh", "INR", "%"
    is_baseline = Column(Boolean, default=False)             # True = baseline, False = GridMind
    mode = Column(String(20), default="gridmind")            # AnalyticsMode
