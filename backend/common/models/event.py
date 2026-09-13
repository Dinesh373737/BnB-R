"""GridMind — events table: System event log (displayed in Event History UI)."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text
from backend.common.database import Base


class EventRecord(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    simulation_run_id = Column(Integer, nullable=True, index=True)
    timestep = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    event_type = Column(String(30), nullable=False)          # EventType
    severity = Column(String(20), default="info")            # EventSeverity
    agent = Column(String(30), nullable=True)                # AgentType (if agent-related)
    action = Column(String(50), nullable=True)
    reason = Column(Text, nullable=True)
    result = Column(Text, nullable=True)
    details_json = Column(Text, nullable=True)               # Extra JSON data
