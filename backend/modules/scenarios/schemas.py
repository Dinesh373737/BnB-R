from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class ScenarioType(str, Enum):
    GRID_OUTAGE = "grid_outage"
    EXTREME_WEATHER = "extreme_weather"
    DEMAND_SURGE = "demand_surge"
    RENEWABLE_FAILURE = "renewable_failure"
    BATTERY_SHORTAGE = "battery_shortage"
    CUSTOM = "custom"


class ScenarioConfig(BaseModel):
    """
    Configuration defining the multipliers or overrides to apply to the microgrid state.
    Multipliers are usually 1.0 (no change), < 1.0 (reduction), or > 1.0 (increase).
    """
    id: str = Field(..., description="Unique identifier for the scenario")
    name: str = Field(..., description="Human-readable name of the scenario")
    description: str = Field(..., description="Detailed description of what the scenario does")
    scenario_type: ScenarioType
    
    # Modifiers
    solar_multiplier: float = Field(1.0, description="Multiplier for solar generation (e.g. 0.5 = 50% drop)")
    wind_multiplier: float = Field(1.0, description="Multiplier for wind generation")
    demand_multiplier: float = Field(1.0, description="Multiplier for total demand (e.g. 1.3 = 30% increase)")
    
    # Overrides
    grid_available: Optional[bool] = Field(None, description="If True/False, overrides the grid availability")
    battery_capacity_multiplier: float = Field(1.0, description="Multiplier for battery SOC/capacity (simulating a failure)")
    
    # Optional Custom Parameters
    custom_parameters: Dict[str, Any] = Field(default_factory=dict, description="Any additional modifiers")


class ScenarioResult(BaseModel):
    """
    The result after applying the scenario to a base state.
    """
    scenario_id: str
    scenario_name: str
    original_state: Dict[str, Any]
    modified_state: Dict[str, Any]
    logs: List[str] = Field(default_factory=list, description="List of changes applied by the runner")
