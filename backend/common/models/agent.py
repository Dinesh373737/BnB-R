"""GridMind — agents + agent_decisions tables."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, Text
from backend.common.database import Base


class AgentRecord(Base):
    """Registry of the 6 AI agents."""
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True)
    agent_type = Column(String(30), nullable=False)          # AgentType
    status = Column(String(20), default="idle")              # AgentStatus
    description = Column(Text, nullable=True)
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AgentDecisionRecord(Base):
    """Every decision made by any agent, per simulation timestep."""
    __tablename__ = "agent_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    simulation_run_id = Column(Integer, nullable=True, index=True)
    timestep = Column(Integer, default=0)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    agent_type = Column(String(30), nullable=False)          # AgentType
    action = Column(String(30), nullable=False)              # ResourceAction/DemandAction/etc.
    resource = Column(String(50), nullable=True)             # Target resource/entity
    quantity_kwh = Column(Float, nullable=True)
    quantity_kw = Column(Float, nullable=True)
    duration_minutes = Column(Float, nullable=True)
    reason = Column(Text, nullable=True)
    expected_effect = Column(Text, nullable=True)
    confidence = Column(Float, default=1.0)
    priority = Column(Integer, default=5)
    safety_status = Column(String(20), nullable=True)        # SafetyStatus
    coordinator_approved = Column(Boolean, nullable=True)
    inputs_json = Column(Text, nullable=True)                # JSON of agent inputs
