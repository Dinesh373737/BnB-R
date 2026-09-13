from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from backend.common.schemas.base import IDMixin
from backend.common.schemas.enums import MarketOrderType, OrderStatus, TradeStatus


class OrderCreate(BaseModel):
    """Schema for creating a new market order (Bid or Ask)."""
    participant_id: str = Field(..., description="Unique ID of the participant placing the order")
    participant_name: str | None = Field(None, description="Optional name of the participant")
    order_type: MarketOrderType = Field(..., description="Whether this is a BID (buy) or ASK (sell)")
    energy_kwh: float = Field(..., gt=0.0, description="Amount of energy in kWh")
    price_per_kwh: float = Field(..., ge=0.0, description="Price per kWh")
    simulation_run_id: int | None = Field(None, description="ID of the simulation run if applicable")
    timestep: int = Field(0, description="Current simulation timestep")


class OrderResponse(IDMixin, OrderCreate):
    """Schema representing an existing market order."""
    timestamp: datetime
    status: OrderStatus
    matched_with_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class TradeResponse(IDMixin, BaseModel):
    """Schema representing an executed trade."""
    simulation_run_id: int | None = None
    timestep: int = 0
    timestamp: datetime
    seller_id: str
    seller_name: str | None = None
    buyer_id: str
    buyer_name: str | None = None
    energy_kwh: float
    price_per_kwh: float
    total_cost: float | None = None
    status: TradeStatus
    reason: str | None = None

    model_config = ConfigDict(from_attributes=True)
