"""GridMind — grid_states table: Real Karnataka grid data snapshots."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, String, DateTime, Text
from backend.common.database import Base


class GridStateRecord(Base):
    __tablename__ = "grid_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    demand_mw = Column(Float, nullable=True)
    total_generation_mw = Column(Float, nullable=True)
    solar_mw = Column(Float, nullable=True)
    wind_mw = Column(Float, nullable=True)
    hydro_mw = Column(Float, nullable=True)
    thermal_mw = Column(Float, nullable=True)
    frequency_hz = Column(Float, nullable=True)
    renewable_contribution_pct = Column(Float, nullable=True)
    condition = Column(String(20), default="stable")     # GridCondition enum value
    data_source = Column(String(20), default="simulated")  # DataSourceType enum value
    raw_data = Column(Text, nullable=True)                 # JSON string of raw API response
