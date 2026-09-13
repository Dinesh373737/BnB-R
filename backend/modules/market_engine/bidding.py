"""
Market Engine — Bidding Logic
Handles the placement and cancellation of market orders.
"""

from sqlalchemy.orm import Session
from backend.common.models.market import MarketOrderRecord
from backend.common.schemas.enums import OrderStatus
from backend.modules.market_engine.schemas import OrderCreate


def place_order(db: Session, order_data: OrderCreate) -> MarketOrderRecord:
    """
    Creates a new Bid or Ask order and saves it to the database with a PENDING status.
    """
    db_order = MarketOrderRecord(
        simulation_run_id=order_data.simulation_run_id,
        timestep=order_data.timestep,
        participant_id=order_data.participant_id,
        participant_name=order_data.participant_name,
        order_type=order_data.order_type,
        energy_kwh=order_data.energy_kwh,
        price_per_kwh=order_data.price_per_kwh,
        status=OrderStatus.PENDING
    )
    
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order


def cancel_order(db: Session, order_id: int) -> MarketOrderRecord | None:
    """
    Cancels an existing PENDING order.
    Returns the updated order, or None if the order doesn't exist.
    Raises ValueError if the order is already executed or matched.
    """
    db_order = db.query(MarketOrderRecord).filter(MarketOrderRecord.id == order_id).first()
    
    if not db_order:
        return None
        
    if db_order.status in [OrderStatus.EXECUTED, OrderStatus.MATCHED]:
        raise ValueError(f"Cannot cancel order {order_id} because its status is {db_order.status}")
        
    db_order.status = OrderStatus.CANCELLED
    db.commit()
    db.refresh(db_order)
    
    return db_order


def get_order(db: Session, order_id: int) -> MarketOrderRecord | None:
    """Retrieves an order by its ID."""
    return db.query(MarketOrderRecord).filter(MarketOrderRecord.id == order_id).first()


def get_pending_orders(db: Session) -> list[MarketOrderRecord]:
    """Retrieves all currently PENDING orders."""
    return db.query(MarketOrderRecord).filter(MarketOrderRecord.status == OrderStatus.PENDING).all()
