"""
Market Engine — Trade Clearing
Executes matched orders to create trade records and finalize the transaction.
"""

from sqlalchemy.orm import Session
from backend.common.models.market import MarketOrderRecord, TradeRecord
from backend.common.schemas.enums import OrderStatus, TradeStatus


def execute_trades(db: Session, matched_pairs: list[tuple[MarketOrderRecord, MarketOrderRecord]]) -> list[TradeRecord]:
    """
    Takes a list of matched (Bid, Ask) pairs, calculates the clearing price,
    creates TradeRecords, and marks the original orders as EXECUTED.
    
    The clearing price is determined as the mid-point between the bid and ask price,
    which is a standard approach for fair P2P market clearing.
    """
    trades = []
    
    for bid, ask in matched_pairs:
        # Calculate clearing price (mid-point pricing)
        clearing_price = (bid.price_per_kwh + ask.price_per_kwh) / 2.0
        
        # Energy should be equal since the matching algorithm already split partial fills
        traded_energy = bid.energy_kwh
        total_cost = traded_energy * clearing_price
        
        # Create the TradeRecord
        trade = TradeRecord(
            simulation_run_id=bid.simulation_run_id,
            timestep=bid.timestep,
            seller_id=ask.participant_id,
            seller_name=ask.participant_name,
            buyer_id=bid.participant_id,
            buyer_name=bid.participant_name,
            energy_kwh=traded_energy,
            price_per_kwh=clearing_price,
            total_cost=total_cost,
            status=TradeStatus.COMPLETED,
            reason="Market Clearing"
        )
        
        db.add(trade)
        
        # Finalize the orders by marking them as EXECUTED
        bid.status = OrderStatus.EXECUTED
        ask.status = OrderStatus.EXECUTED
        
        trades.append(trade)
        
    db.commit()
    
    # Refresh to get the generated trade IDs
    for trade in trades:
        db.refresh(trade)
        
    return trades
