"""
Market Engine — Service Layer
Orchestrates bidding, matching, and clearing into a unified service.
"""

from sqlalchemy.orm import Session
from backend.modules.market_engine.schemas import OrderCreate
from backend.modules.market_engine import bidding
from backend.modules.market_engine import matching
from backend.modules.market_engine import clearing
from backend.common.models.market import MarketOrderRecord, TradeRecord


def _active_simulation_run_id() -> int | None:
    """Return the run id of the simulation module's current run, if any.

    Used to attribute UI-placed orders to the active simulation so that the
    run's P2P market metrics include real trades.
    """
    try:
        from backend.modules.simulation.router import _service

        run_id = getattr(_service, "run_id", None)
        return int(run_id) if run_id is not None else None
    except Exception:
        return None


class MarketService:
    """Service class for Market Engine operations."""

    def __init__(self, db: Session):
        self.db = db

    def place_order(self, order_data: OrderCreate) -> MarketOrderRecord:
        """Places a new bid or ask order.

        Orders that arrive without an explicit run id are attributed to the
        simulation module's active run (when one exists) so trades are
        reflected in that run's market metrics.
        """
        if order_data.simulation_run_id is None:
            order_data.simulation_run_id = _active_simulation_run_id()
        return bidding.place_order(self.db, order_data)

    def cancel_order(self, order_id: int) -> MarketOrderRecord | None:
        """Cancels an existing pending order."""
        return bidding.cancel_order(self.db, order_id)
        
    def get_order(self, order_id: int) -> MarketOrderRecord | None:
        """Retrieves a specific order."""
        return bidding.get_order(self.db, order_id)
        
    def get_pending_orders(self) -> list[MarketOrderRecord]:
        """Retrieves all pending orders."""
        return bidding.get_pending_orders(self.db)

    def run_market_clearing(self) -> dict:
        """
        Runs the full market clearing cycle:
        1. Matches compatible Bids and Asks.
        2. Clears the matched pairs to create Trades.
        
        Returns a summary dictionary of the operation.
        """
        # 1. Match orders
        matched_pairs = matching.match_orders(self.db)
        
        if not matched_pairs:
            return {
                "matched_pairs": 0,
                "trades_executed": 0,
                "message": "No compatible orders found to match."
            }
            
        # 2. Clear trades
        executed_trades = clearing.execute_trades(self.db, matched_pairs)
        
        return {
            "matched_pairs": len(matched_pairs),
            "trades_executed": len(executed_trades),
            "message": f"Successfully executed {len(executed_trades)} trades."
        }

    def get_all_trades(self) -> list[TradeRecord]:
        """Retrieves all executed trades."""
        return self.db.query(TradeRecord).all()
