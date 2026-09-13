"""
GridMind — Common Foundation Package
=====================================
This package contains ALL shared infrastructure code.

RULES:
  1. Modules import FROM here — they NEVER modify files in this package.
  2. All database models, schemas, enums, config live here.
  3. This package is built FIRST and stays FROZEN during module development.

Convenient re-exports for modules:
  from backend.common import settings, flags, db_session, event_bus
  from backend.common.models import GridState, WeatherData, ...
  from backend.common.schemas.enums import RiskLevel, AgentType, ...
"""

from backend.common.config import settings
from backend.common.feature_flags import flags
from backend.common.database import get_db_session, engine, Base
from backend.common.events import event_bus
from backend.common.logger import logger
from backend.common.api_registry import api_registry
from backend.common.exceptions import (
    GridMindError,
    DatabaseError,
    AgentError,
    SafetyViolationError,
    DataConnectorError,
    ForecastError,
    MarketError,
    SimulationError,
    ConfigurationError,
    ValidationError,
)

__all__ = [
    "settings",
    "flags",
    "get_db_session",
    "engine",
    "Base",
    "event_bus",
    "logger",
    "api_registry",
    "GridMindError",
    "DatabaseError",
    "AgentError",
    "SafetyViolationError",
    "DataConnectorError",
    "ForecastError",
    "MarketError",
    "SimulationError",
    "ConfigurationError",
    "ValidationError",
]
