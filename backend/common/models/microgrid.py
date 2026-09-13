"""GridMind — microgrid_states table: Snapshots of full microgrid state per timestep."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, Text
from backend.common.database import Base


class MicrogridStateDBRecord(Base):
    __tablename__ = "microgrid_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    simulation_run_id = Column(Integer, nullable=True, index=True)
    timestep = Column(Integer, default=0)

    # Aggregate metrics
    total_demand_kw = Column(Float, default=0.0)
    total_generation_kw = Column(Float, default=0.0)
    renewable_generation_kw = Column(Float, default=0.0)
    renewable_percentage = Column(Float, default=0.0)
    energy_balance_kw = Column(Float, default=0.0)

    # Key component values
    battery_soc = Column(Float, default=0.0)
    ev_demand_kw = Column(Float, default=0.0)
    grid_import_kw = Column(Float, default=0.0)
    grid_export_kw = Column(Float, default=0.0)
    energy_traded_kwh = Column(Float, default=0.0)
    solar_output_kw = Column(Float, default=0.0)
    wind_output_kw = Column(Float, default=0.0)

    # Status
    risk_level = Column(String(20), default="low")
    risk_score = Column(Float, default=0.0)
    grid_condition = Column(String(20), default="stable")
    critical_load_status = Column(String(20), default="protected")
    data_source = Column(String(20), default="simulated")

    # Full state JSON (for detailed reconstruction)
    full_state_json = Column(Text, nullable=True)
