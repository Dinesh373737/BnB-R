"""GridMind — market_orders + trades tables: P2P energy market records."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, String, DateTime
from backend.common.database import Base


class MarketOrderRecord(Base):
    """Bid/Ask orders in the P2P energy market."""
    __tablename__ = "market_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    simulation_run_id = Column(Integer, nullable=True, index=True)
    timestep = Column(Integer, default=0)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    participant_id = Column(String(50), nullable=False)      # e.g. "house_a", "solar_farm"
    participant_name = Column(String(100), nullable=True)
    order_type = Column(String(10), nullable=False)          # MarketOrderType: bid/ask
    energy_kwh = Column(Float, nullable=False)
    price_per_kwh = Column(Float, nullable=False)
    status = Column(String(20), default="pending")           # OrderStatus
    matched_with_id = Column(Integer, nullable=True)         # FK to another order


class TradeRecord(Base):
    """Executed P2P energy trades."""
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    simulation_run_id = Column(Integer, nullable=True, index=True)
    timestep = Column(Integer, default=0)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    seller_id = Column(String(50), nullable=False)
    seller_name = Column(String(100), nullable=True)
    buyer_id = Column(String(50), nullable=False)
    buyer_name = Column(String(100), nullable=True)
    energy_kwh = Column(Float, nullable=False)
    price_per_kwh = Column(Float, nullable=False)
    total_cost = Column(Float, nullable=True)
    status = Column(String(20), default="completed")         # TradeStatus
    reason = Column(String(200), nullable=True)
