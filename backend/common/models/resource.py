"""GridMind — resources table: Energy resources (solar, wind, battery, EV)."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, String, DateTime
from backend.common.database import Base


class ResourceRecord(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    resource_type = Column(String(20), nullable=False)       # ResourceType: solar/wind/battery/ev
    capacity_kw = Column(Float, default=0.0)
    capacity_kwh = Column(Float, nullable=True)              # For storage (battery/EV)
    current_output_kw = Column(Float, default=0.0)
    current_soc = Column(Float, nullable=True)               # For storage (0.0 to 1.0)
    min_soc = Column(Float, nullable=True)
    max_soc = Column(Float, nullable=True)
    charge_rate_kw = Column(Float, nullable=True)
    discharge_rate_kw = Column(Float, nullable=True)
    status = Column(String(20), default="active")            # ResourceStatus
    simulation_run_id = Column(Integer, nullable=True, index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
