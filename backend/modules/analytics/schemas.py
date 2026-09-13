"""Analytics module — Pydantic schemas for requests, responses, and metric structures.

Reuses shared enums (MetricCategory, AnalyticsMode) and base response wrappers
from ``backend.common``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.common.schemas.base import BaseResponse, DataResponse
from backend.common.schemas.enums import MetricCategory, AnalyticsMode


# ══════════════════════════════════════════════════════════════════════════
#  TIMESTEP DATA — flattened snapshot for metric calculations
# ══════════════════════════════════════════════════════════════════════════


class TimestepSnapshot(BaseModel):
    """Flattened per-timestep data consumed by pure metric functions.

    Can be constructed from a ``MicrogridState``, a ``SimulationStepResult``,
    or a ``MicrogridStateDBRecord`` via the provided converter helpers.
    """

    model_config = ConfigDict(from_attributes=True)

    timestep: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Aggregate power
    total_demand_kw: float = 0.0
    total_generation_kw: float = 0.0
    renewable_generation_kw: float = 0.0
    energy_balance_kw: float = 0.0

    # Solar / Wind
    solar_output_kw: float = 0.0
    solar_capacity_kw: float = 0.0
    wind_output_kw: float = 0.0
    wind_capacity_kw: float = 0.0

    # Battery
    battery_soc: float = 0.0          # 0–1
    battery_capacity_kwh: float = 0.0
    battery_power_kw: float = 0.0     # +charge / −discharge

    # Grid connection
    grid_import_kw: float = 0.0
    grid_export_kw: float = 0.0
    electricity_price_per_kwh: float = 6.5

    # Critical facility
    critical_load_required_kw: float = 0.0
    critical_load_supply_kw: float = 0.0
    critical_load_status: str = "protected"

    # Risk
    risk_level: str = "low"
    risk_score: float = 0.0

    # Market (cumulative for the timestep)
    energy_traded_kwh: float = 0.0

    # Detailed data (available from SimulationStepResult)
    unserved_load_kw: float = 0.0
    curtailed_generation_kw: float = 0.0

    # Timing
    timestep_seconds: int = 60


class TradeData(BaseModel):
    """Minimal trade record for metric calculations."""

    model_config = ConfigDict(from_attributes=True)

    energy_kwh: float = 0.0
    price_per_kwh: float = 0.0
    total_cost: float | None = None


# ══════════════════════════════════════════════════════════════════════════
#  METRIC RESULT SCHEMAS (grouped by category)
# ══════════════════════════════════════════════════════════════════════════


class EconomicMetrics(BaseModel):
    """Economic performance metrics."""
    total_cost: float = 0.0                   # INR — grid import cost
    average_cost_per_kwh: float = 0.0         # INR/kWh
    cost_savings_percent: float = 0.0         # vs baseline (populated in comparison)


class GridMetrics(BaseModel):
    """Grid demand metrics."""
    peak_demand_kw: float = 0.0
    peak_reduction_percent: float = 0.0       # vs baseline (populated in comparison)


class RenewableMetrics(BaseModel):
    """Renewable energy utilisation metrics."""
    renewable_utilization_percent: float = 0.0   # renewable gen / total demand
    solar_utilization_percent: float = 0.0       # solar output / solar capacity
    renewable_curtailment_kwh: float = 0.0       # curtailed renewable energy


class StorageMetrics(BaseModel):
    """Battery storage metrics."""
    battery_utilization_percent: float = 0.0     # cycles / available cycles proxy
    battery_reserve_percent: float = 0.0         # average SOC %


class ResilienceMetrics(BaseModel):
    """System resilience metrics."""
    unserved_energy_kwh: float = 0.0
    critical_load_protection_percent: float = 0.0
    recovery_time_minutes: float = 0.0


class MarketMetrics(BaseModel):
    """P2P energy market metrics."""
    total_energy_traded_kwh: float = 0.0
    transaction_count: int = 0
    average_trading_price: float = 0.0


class FullMetricSet(BaseModel):
    """All metric categories bundled together."""
    economic: EconomicMetrics = Field(default_factory=EconomicMetrics)
    grid: GridMetrics = Field(default_factory=GridMetrics)
    renewable: RenewableMetrics = Field(default_factory=RenewableMetrics)
    storage: StorageMetrics = Field(default_factory=StorageMetrics)
    resilience: ResilienceMetrics = Field(default_factory=ResilienceMetrics)
    market: MarketMetrics = Field(default_factory=MarketMetrics)


class ImprovementMetrics(BaseModel):
    """Calculated improvement of GridMind over baseline."""
    cost_savings_percent: float = 0.0
    peak_reduction_percent: float = 0.0
    renewable_improvement_percent: float = 0.0
    unserved_energy_reduction_percent: float = 0.0
    critical_load_improvement_percent: float = 0.0
    recovery_time_improvement_percent: float = 0.0


class ComparisonResult(BaseModel):
    """Side-by-side baseline vs GridMind comparison."""

    model_config = ConfigDict(from_attributes=True)

    simulation_run_id: int | None = None
    scenario: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    baseline: FullMetricSet = Field(default_factory=FullMetricSet)
    gridmind: FullMetricSet = Field(default_factory=FullMetricSet)
    improvement: ImprovementMetrics = Field(default_factory=ImprovementMetrics)


# ══════════════════════════════════════════════════════════════════════════
#  API REQUEST / RESPONSE SCHEMAS
# ══════════════════════════════════════════════════════════════════════════


class AnalyticsRequest(BaseModel):
    """Request to calculate analytics for a simulation run."""
    simulation_run_id: int


class AnalyticsResponse(BaseResponse):
    """Response containing full metric set for one controller mode."""
    simulation_run_id: int | None = None
    mode: AnalyticsMode = AnalyticsMode.GRIDMIND
    metrics: FullMetricSet = Field(default_factory=FullMetricSet)


class ComparisonResponse(BaseResponse):
    """Response containing baseline vs GridMind comparison."""
    comparison: ComparisonResult = Field(default_factory=ComparisonResult)


# ══════════════════════════════════════════════════════════════════════════
#  CONVERTER HELPERS
# ══════════════════════════════════════════════════════════════════════════


def snapshot_from_microgrid_state(
    state,
    *,
    unserved_load_kw: float = 0.0,
    curtailed_generation_kw: float = 0.0,
    timestep_seconds: int = 60,
) -> TimestepSnapshot:
    """Build a ``TimestepSnapshot`` from a ``MicrogridState`` Pydantic model."""
    return TimestepSnapshot(
        timestep=state.timestep,
        timestamp=state.timestamp,
        total_demand_kw=state.total_demand_kw,
        total_generation_kw=state.total_generation_kw,
        renewable_generation_kw=state.renewable_generation_kw,
        energy_balance_kw=state.energy_balance_kw,
        solar_output_kw=state.solar.current_output_kw,
        solar_capacity_kw=state.solar.capacity_kw,
        wind_output_kw=state.wind.current_output_kw,
        wind_capacity_kw=state.wind.capacity_kw,
        battery_soc=state.battery.current_soc,
        battery_capacity_kwh=state.battery.capacity_kwh,
        battery_power_kw=state.battery.current_power_kw,
        grid_import_kw=state.grid_connection.import_power_kw,
        grid_export_kw=state.grid_connection.export_power_kw,
        electricity_price_per_kwh=state.grid_connection.electricity_price_per_kwh,
        critical_load_required_kw=state.critical_facility.required_power_kw,
        critical_load_supply_kw=state.critical_facility.current_supply_kw,
        critical_load_status=state.critical_facility.status.value
        if hasattr(state.critical_facility.status, "value")
        else str(state.critical_facility.status),
        risk_level=state.risk.risk_level.value
        if hasattr(state.risk.risk_level, "value")
        else str(state.risk.risk_level),
        risk_score=state.risk.risk_score,
        energy_traded_kwh=state.market.total_energy_traded_kwh,
        unserved_load_kw=unserved_load_kw,
        curtailed_generation_kw=curtailed_generation_kw,
        timestep_seconds=timestep_seconds,
    )


def snapshot_from_step_result(
    result,
    *,
    timestep_seconds: int = 60,
) -> TimestepSnapshot:
    """Build a ``TimestepSnapshot`` from a ``SimulationStepResult``."""
    return snapshot_from_microgrid_state(
        result.state,
        unserved_load_kw=result.unserved_load_kw,
        curtailed_generation_kw=result.curtailed_generation_kw,
        timestep_seconds=timestep_seconds,
    )


def snapshot_from_db_record(record, *, timestep_seconds: int = 60) -> TimestepSnapshot:
    """Build a ``TimestepSnapshot`` from a ``MicrogridStateDBRecord`` ORM row.

    Prefers the lossless ``full_state_json`` snapshot when present; otherwise
    falls back to the flattened DB columns and estimates missing fields.
    """
    import json

    grid_import = getattr(record, "grid_import_kw", 0.0) or 0.0
    grid_export = getattr(record, "grid_export_kw", 0.0) or 0.0
    total_demand = getattr(record, "total_demand_kw", 0.0) or 0.0
    total_gen = getattr(record, "total_generation_kw", 0.0) or 0.0
    energy_balance = getattr(record, "energy_balance_kw", 0.0) or 0.0

    # Estimate unserved load: if local balance + grid import still negative
    supplied = total_gen + grid_import - grid_export
    estimated_unserved = max(0.0, total_demand - supplied)

    critical_status = getattr(record, "critical_load_status", "protected") or "protected"

    # ── Prefer the full-state JSON (persisted by the simulation layer) ──
    full_state_raw = getattr(record, "full_state_json", None)
    if full_state_raw:
        try:
            from backend.common.schemas.microgrid_state import MicrogridState

            state = MicrogridState.model_validate_json(full_state_raw)
            return snapshot_from_microgrid_state(
                state,
                unserved_load_kw=estimated_unserved,
                curtailed_generation_kw=0.0,
                timestep_seconds=timestep_seconds,
            )
        except Exception:
            pass  # fall back to flattened columns below

    return TimestepSnapshot(
        timestep=getattr(record, "timestep", 0) or 0,
        timestamp=getattr(record, "timestamp", datetime.now(timezone.utc)),
        total_demand_kw=total_demand,
        total_generation_kw=total_gen,
        renewable_generation_kw=getattr(record, "renewable_generation_kw", 0.0) or 0.0,
        energy_balance_kw=energy_balance,
        solar_output_kw=getattr(record, "solar_output_kw", 0.0) or 0.0,
        solar_capacity_kw=0.0,  # not stored in DB record
        wind_output_kw=getattr(record, "wind_output_kw", 0.0) or 0.0,
        wind_capacity_kw=0.0,
        battery_soc=getattr(record, "battery_soc", 0.0) or 0.0,
        battery_capacity_kwh=0.0,
        battery_power_kw=0.0,
        grid_import_kw=grid_import,
        grid_export_kw=grid_export,
        electricity_price_per_kwh=6.5,
        critical_load_required_kw=0.0,
        critical_load_supply_kw=0.0,
        critical_load_status=critical_status,
        risk_level=getattr(record, "risk_level", "low") or "low",
        risk_score=getattr(record, "risk_score", 0.0) or 0.0,
        energy_traded_kwh=getattr(record, "energy_traded_kwh", 0.0) or 0.0,
        unserved_load_kw=estimated_unserved,
        curtailed_generation_kw=0.0,
        timestep_seconds=timestep_seconds,
    )
