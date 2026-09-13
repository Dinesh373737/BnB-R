"""GridMind — simulation_runs table: Tracks each simulation run."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text, Float
from backend.common.database import Base


class SimulationRunRecord(Base):
    __tablename__ = "simulation_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mode = Column(String(20), default="simulation")          # SimulationMode: live/simulation
    scenario = Column(String(50), nullable=True)             # ScenarioType
    status = Column(String(20), default="pending")           # SimulationStatus
    start_time = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    end_time = Column(DateTime, nullable=True)
    total_timesteps = Column(Integer, default=0)
    timestep_seconds = Column(Integer, default=60)
    duration_seconds = Column(Float, nullable=True)
    parameters_json = Column(Text, nullable=True)            # JSON of simulation params
    results_summary_json = Column(Text, nullable=True)       # JSON summary after completion
