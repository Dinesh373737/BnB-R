"""
Market Engine — API Router
Exposes the Market Service functionality through REST API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.common.database import get_db_session
from backend.modules.market_engine.schemas import OrderCreate, OrderResponse, TradeResponse
from backend.modules.market_engine.service import MarketService

router = APIRouter(prefix="/api/market", tags=["Market Engine"])

def get_market_service(db: Session = Depends(get_db_session)) -> MarketService:
    return MarketService(db)

@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def place_order(order: OrderCreate, service: MarketService = Depends(get_market_service)):
    """Place a new Bid or Ask order in the market."""
    return service.place_order(order)

@router.get("/orders/pending", response_model=list[OrderResponse])
def get_pending_orders(service: MarketService = Depends(get_market_service)):
    """Retrieve all pending orders."""
    return service.get_pending_orders()

@router.delete("/orders/{order_id}", response_model=OrderResponse)
def cancel_order(order_id: int, service: MarketService = Depends(get_market_service)):
    """Cancel a pending order."""
    try:
        order = service.cancel_order(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        return order
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/match")
def run_market_clearing(service: MarketService = Depends(get_market_service)):
    """Run the matching and clearing engine for all pending orders."""
    return service.run_market_clearing()

@router.get("/trades", response_model=list[TradeResponse])
def get_all_trades(service: MarketService = Depends(get_market_service)):
    """Retrieve all executed trades."""
    return service.get_all_trades()
