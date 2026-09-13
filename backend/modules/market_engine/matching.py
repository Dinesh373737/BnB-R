"""
Market Engine — Matching Algorithm
Pairs compatible Bids and Asks based on price and available energy.
"""

from sqlalchemy.orm import Session
from backend.common.models.market import MarketOrderRecord
from backend.common.schemas.enums import MarketOrderType, OrderStatus
from backend.modules.market_engine.bidding import get_pending_orders


def match_orders(db: Session) -> list[tuple[MarketOrderRecord, MarketOrderRecord]]:
    """
    Matches PENDING Bids and Asks.
    - Bids are sorted by highest price first (willing to pay more).
    - Asks are sorted by lowest price first (willing to sell for less).
    - A match occurs if bid_price >= ask_price.
    
    If orders have different energy amounts, the larger order is split:
    The matched portion is marked MATCHED, and a new PENDING order is created for the remainder.
    
    Returns a list of matched pairs: (bid, ask).
    """
    pending_orders = get_pending_orders(db)
    
    bids = [o for o in pending_orders if o.order_type == MarketOrderType.BID]
    asks = [o for o in pending_orders if o.order_type == MarketOrderType.ASK]
    
    # Sort bids descending (highest price first)
    bids.sort(key=lambda x: x.price_per_kwh, reverse=True)
    # Sort asks ascending (lowest price first)
    asks.sort(key=lambda x: x.price_per_kwh)
    
    matched_pairs = []
    
    bid_idx = 0
    ask_idx = 0
    
    while bid_idx < len(bids) and ask_idx < len(asks):
        bid = bids[bid_idx]
        ask = asks[ask_idx]
        
        if bid.price_per_kwh >= ask.price_per_kwh:
            # We have a match! Determine the matched energy
            matched_energy = min(bid.energy_kwh, ask.energy_kwh)
            
            # Handle remainder for Bid
            if bid.energy_kwh > matched_energy:
                remainder_energy = bid.energy_kwh - matched_energy
                bid.energy_kwh = matched_energy
                
                # Create a new PENDING bid for the remainder
                remainder_bid = MarketOrderRecord(
                    simulation_run_id=bid.simulation_run_id,
                    timestep=bid.timestep,
                    participant_id=bid.participant_id,
                    participant_name=bid.participant_name,
                    order_type=MarketOrderType.BID,
                    energy_kwh=remainder_energy,
                    price_per_kwh=bid.price_per_kwh,
                    status=OrderStatus.PENDING
                )
                db.add(remainder_bid)
                # Insert the remainder into the list so it can be matched in this run
                bids.insert(bid_idx + 1, remainder_bid)
            
            # Handle remainder for Ask
            if ask.energy_kwh > matched_energy:
                remainder_energy = ask.energy_kwh - matched_energy
                ask.energy_kwh = matched_energy
                
                # Create a new PENDING ask for the remainder
                remainder_ask = MarketOrderRecord(
                    simulation_run_id=ask.simulation_run_id,
                    timestep=ask.timestep,
                    participant_id=ask.participant_id,
                    participant_name=ask.participant_name,
                    order_type=MarketOrderType.ASK,
                    energy_kwh=remainder_energy,
                    price_per_kwh=ask.price_per_kwh,
                    status=OrderStatus.PENDING
                )
                db.add(remainder_ask)
                # Insert the remainder into the list so it can be matched in this run
                asks.insert(ask_idx + 1, remainder_ask)
            
            # Mark both as MATCHED
            bid.status = OrderStatus.MATCHED
            ask.status = OrderStatus.MATCHED
            
            matched_pairs.append((bid, ask))
            
            # Move to next pair
            bid_idx += 1
            ask_idx += 1
        else:
            # The highest bid is lower than the lowest ask.
            # No more matches are possible in this pass.
            break
            
    # Commit to get IDs generated for any newly created remainder orders
    db.commit()
    
    # Link the matched pairs together
    for bid, ask in matched_pairs:
        bid.matched_with_id = ask.id
        ask.matched_with_id = bid.id
        
    db.commit()
    
    return matched_pairs
