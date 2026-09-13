"""GridMind — risk_events table: Risk assessment snapshots."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, String, DateTime, Text
from backend.common.database import Base


class RiskEventRecord(Base):
    __tablename__ = "risk_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    simulation_run_id = Column(Integer, nullable=True, index=True)
    timestep = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    risk_score = Column(Float, default=0.0)                  # 0 to 100
    risk_level = Column(String(20), default="low")           # RiskLevel
    drivers_json = Column(Text, nullable=True)               # JSON list of RiskDriver values
    assessment_details_json = Column(Text, nullable=True)    # Full assessment JSON
