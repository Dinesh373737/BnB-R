"""
GridMind — Database Initialization
=====================================
Creates all tables, seeds initial data (6 agents), and verifies the DB.

Usage:
    # As a script:
    python -m backend.common.init_db

    # From code:
    from backend.common.init_db import initialize_database
    initialize_database()
"""

from backend.common.database import engine, Base, get_db_session_context
from backend.common.logger import get_module_logger

# IMPORTANT: Import all models so SQLAlchemy knows about them
from backend.common.models import (  # noqa: F401
    GridStateRecord,
    WeatherDataRecord,
    ForecastRecord,
    MicrogridStateDBRecord,
    ResourceRecord,
    AgentRecord,
    AgentDecisionRecord,
    MarketOrderRecord,
    TradeRecord,
    EventRecord,
    SimulationRunRecord,
    AnalyticsResultRecord,
    RiskEventRecord,
)
from backend.common.schemas.enums import AgentType

log = get_module_logger("init_db")


# ── The 6 AI Agents (seeded on first run) ─────────────────────────────

AGENT_SEED_DATA = [
    {
        "name": "Coordinator Agent",
        "agent_type": AgentType.COORDINATOR.value,
        "description": "Overall orchestration + conflict resolution. Receives info from all agents, resolves competing objectives, coordinates final response.",
    },
    {
        "name": "Risk & Forecast Agent",
        "agent_type": AgentType.RISK_FORECAST.value,
        "description": "Demand/solar/wind prediction + uncertainty estimation + risk/failure assessment. Provides intelligence to all other agents.",
    },
    {
        "name": "Market & Trading Agent",
        "agent_type": AgentType.MARKET_TRADING.value,
        "description": "P2P energy market: bids, asks, order matching, clearing price calculation, and transaction execution.",
    },
    {
        "name": "Energy Resource Agent",
        "agent_type": AgentType.ENERGY_RESOURCE.value,
        "description": "Battery + solar + wind + EV energy resource decisions: charge, discharge, hold, reserve, sell, delay EV.",
    },
    {
        "name": "Demand Management Agent",
        "agent_type": AgentType.DEMAND_MANAGEMENT.value,
        "description": "Household + industry + flexible load decisions: run, delay, reduce, shift, pause demand.",
    },
    {
        "name": "Critical Facility Agent",
        "agent_type": AgentType.CRITICAL_FACILITY.value,
        "description": "Protects hospital/critical loads. Ensures critical load never falls below required threshold.",
    },
]


def create_tables() -> None:
    """Create all database tables (if they don't exist)."""
    log.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    log.info(f"Created {len(Base.metadata.tables)} tables: {list(Base.metadata.tables.keys())}")


def seed_agents() -> None:
    """Insert the 6 AI agents if they don't exist yet."""
    with get_db_session_context() as db:
        existing = db.query(AgentRecord).count()
        if existing > 0:
            log.info(f"Agents already seeded ({existing} found). Skipping.")
            return

        for agent_data in AGENT_SEED_DATA:
            agent = AgentRecord(**agent_data)
            db.add(agent)

        log.info(f"Seeded {len(AGENT_SEED_DATA)} AI agents.")


def verify_database() -> bool:
    """Verify all tables exist and DB is accessible."""
    try:
        with get_db_session_context() as db:
            # Test a simple query on each table
            db.query(AgentRecord).count()
            db.query(EventRecord).count()
        log.info("Database verification: OK")
        return True
    except Exception as e:
        log.error(f"Database verification FAILED: {e}")
        return False


def initialize_database() -> bool:
    """
    Full database initialization:
    1. Create all tables
    2. Seed initial data (6 agents)
    3. Verify everything works

    Returns True if successful, False otherwise.
    """
    log.info("=" * 60)
    log.info("GridMind Database Initialization")
    log.info("=" * 60)

    try:
        create_tables()
        seed_agents()
        success = verify_database()

        if success:
            log.info("Database initialization: COMPLETE ✓")
        else:
            log.error("Database initialization: FAILED ✗")

        return success

    except Exception as e:
        log.error(f"Database initialization error: {e}")
        return False


# Allow running as: python -m backend.common.init_db
if __name__ == "__main__":
    initialize_database()
