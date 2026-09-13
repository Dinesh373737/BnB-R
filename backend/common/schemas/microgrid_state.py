"""
GridMind — MicrogridState Schema
===================================
The CENTRAL shared state schema that ALL agents read from.
This is the single most important data structure in GridMind.

The simulation engine writes to it.
Agents read from it and make decisions.
The coordinator resolves conflicts based on it.
The UI displays it.

Usage:
    from backend.common.schemas.microgrid_state import MicrogridState, BatteryState
"""

from datetime import datetime, timezone
from pydantic import BaseModel, Field

from backend.common.schemas.enums import (
    RiskLevel,
    GridCondition,
    CriticalLoadStatus,
    DataSourceType,
    ResourceStatus,
)


# ══════════════════════════════════════════════════════════════════════════
#  SUB-COMPONENT STATES
# ══════════════════════════════════════════════════════════════════════════


class SolarState(BaseModel):
    """Current state of solar generation."""
    capacity_kw: float = 0.0
    current_output_kw: float = 0.0
    utilization_pct: float = 0.0           # current_output / capacity * 100
    forecast_output_kw: float | None = None
    status: ResourceStatus = ResourceStatus.ACTIVE
    data_source: DataSourceType = DataSourceType.SIMULATED


class WindState(BaseModel):
    """Current state of wind generation."""
    capacity_kw: float = 0.0
    current_output_kw: float = 0.0
    utilization_pct: float = 0.0
    forecast_output_kw: float | None = None
    status: ResourceStatus = ResourceStatus.ACTIVE
    data_source: DataSourceType = DataSourceType.SIMULATED


class BatteryState(BaseModel):
    """Current state of battery storage."""
    capacity_kwh: float = 0.0
    current_soc: float = 0.0               # 0.0 to 1.0 (0% to 100%)
    soc_percentage: float = 0.0            # 0 to 100
    current_power_kw: float = 0.0          # +ve = charging, -ve = discharging
    min_soc: float = 0.10
    max_soc: float = 0.95
    charge_rate_kw: float = 0.0
    discharge_rate_kw: float = 0.0
    energy_available_kwh: float = 0.0      # (current_soc - min_soc) * capacity
    status: ResourceStatus = ResourceStatus.IDLE


class EVState(BaseModel):
    """Current state of EV fleet."""
    total_count: int = 0
    connected_count: int = 0
    charging_count: int = 0
    total_demand_kw: float = 0.0
    total_battery_kwh: float = 0.0
    average_soc: float = 0.0
    flexible_demand_kw: float = 0.0        # Demand that can be delayed


class HouseholdState(BaseModel):
    """Aggregated household state."""
    count: int = 0
    total_demand_kw: float = 0.0
    flexible_demand_kw: float = 0.0        # Demand that can be shifted/delayed
    fixed_demand_kw: float = 0.0           # Non-negotiable demand


class IndustryState(BaseModel):
    """Industrial load state."""
    total_demand_kw: float = 0.0
    flexible_demand_kw: float = 0.0
    fixed_demand_kw: float = 0.0


class CriticalFacilityState(BaseModel):
    """Critical facility (hospital) state."""
    required_power_kw: float = 0.0
    current_supply_kw: float = 0.0
    backup_energy_kwh: float = 0.0
    reserve_power_kw: float = 0.0
    status: CriticalLoadStatus = CriticalLoadStatus.PROTECTED
    is_protected: bool = True


class GridConnectionState(BaseModel):
    """Connection to main Karnataka grid."""
    condition: GridCondition = GridCondition.STABLE
    import_power_kw: float = 0.0           # Power drawn from main grid
    export_power_kw: float = 0.0           # Power sent to main grid
    import_limit_kw: float = 5000.0
    export_limit_kw: float = 2000.0
    is_connected: bool = True
    electricity_price_per_kwh: float = 6.5  # INR


class MarketState(BaseModel):
    """P2P energy market state."""
    is_active: bool = True
    total_energy_traded_kwh: float = 0.0
    active_bids: int = 0
    active_asks: int = 0
    last_clearing_price: float = 0.0
    total_transactions: int = 0


class ForecastState(BaseModel):
    """Current forecast information."""
    demand_forecast_kw: float | None = None
    demand_lower_kw: float | None = None
    demand_upper_kw: float | None = None
    solar_forecast_kw: float | None = None
    solar_lower_kw: float | None = None
    solar_upper_kw: float | None = None
    wind_forecast_kw: float | None = None
    wind_lower_kw: float | None = None
    wind_upper_kw: float | None = None
    forecast_horizon_minutes: int = 60
    uncertainty_level: str = "medium"


class RiskState(BaseModel):
    """Current risk assessment."""
    risk_score: float = 0.0                # 0 to 100
    risk_level: RiskLevel = RiskLevel.LOW
    drivers: list[str] = Field(default_factory=list)
    assessment_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class WeatherState(BaseModel):
    """Current weather conditions."""
    temperature_c: float | None = None
    cloud_cover_pct: float | None = None
    solar_radiation_wm2: float | None = None
    wind_speed_ms: float | None = None
    weather_condition: str = "unknown"
    data_source: DataSourceType = DataSourceType.SIMULATED


# ══════════════════════════════════════════════════════════════════════════
#  THE CENTRAL MICROGRID STATE
# ══════════════════════════════════════════════════════════════════════════


class MicrogridState(BaseModel):
    """
    THE central shared state of the simulated community microgrid.
    This is the single most important schema in GridMind.

    - The simulation engine WRITES to this.
    - All 6 agents READ from this.
    - The coordinator uses this to resolve conflicts.
    - The frontend displays this.
    - Every simulation timestep produces a new instance.
    """

    # ── Identification ────────────────────────────────────────────────
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    simulation_run_id: int | None = None
    timestep: int = 0

    # ── Aggregate Metrics ─────────────────────────────────────────────
    total_demand_kw: float = 0.0
    total_generation_kw: float = 0.0
    renewable_generation_kw: float = 0.0
    renewable_percentage: float = 0.0
    energy_balance_kw: float = 0.0         # generation - demand (+ve = surplus)
    grid_dependency_pct: float = 0.0       # % of demand met by main grid

    # ── Component States ──────────────────────────────────────────────
    solar: SolarState = Field(default_factory=SolarState)
    wind: WindState = Field(default_factory=WindState)
    battery: BatteryState = Field(default_factory=BatteryState)
    ev: EVState = Field(default_factory=EVState)
    households: HouseholdState = Field(default_factory=HouseholdState)
    industry: IndustryState = Field(default_factory=IndustryState)
    critical_facility: CriticalFacilityState = Field(
        default_factory=CriticalFacilityState
    )
    grid_connection: GridConnectionState = Field(
        default_factory=GridConnectionState
    )
    market: MarketState = Field(default_factory=MarketState)

    # ── Intelligence States ───────────────────────────────────────────
    forecast: ForecastState = Field(default_factory=ForecastState)
    risk: RiskState = Field(default_factory=RiskState)
    weather: WeatherState = Field(default_factory=WeatherState)

    # ── Metadata ──────────────────────────────────────────────────────
    data_source: DataSourceType = DataSourceType.SIMULATED
