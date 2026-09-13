"""Simulation-local contracts.

The shared ``MicrogridState`` remains the cross-module state contract.  These
models describe only configuration, external physical conditions, and already
approved control inputs supplied to the deterministic simulator.
"""

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.common.config import settings
from backend.common.exceptions import ScenarioError
from backend.common.schemas.enums import GridCondition, ScenarioType
from backend.common.schemas.microgrid_state import MicrogridState


class CrisisScenario(BaseModel):
    """An exogenous, optionally time-bounded physical crisis modifier."""

    scenario_type: ScenarioType
    name: str
    solar_generation_multiplier: float = Field(default=1.0, ge=0)
    flexible_demand_multiplier: float = Field(default=1.0, ge=0)
    start_timestep: int = Field(default=1, ge=0)
    duration_steps: int | None = Field(default=None, gt=0)

    def is_active_at(self, timestep: int) -> bool:
        """Return whether this scenario affects the given timestep."""
        if timestep < self.start_timestep:
            return False
        if self.duration_steps is None:
            return True
        return timestep < self.start_timestep + self.duration_steps


def primary_crisis_scenario(
    *, start_timestep: int = 1, duration_steps: int | None = None
) -> CrisisScenario:
    """Build the required solar −50% / flexible-demand +30% crisis.

    The multiplier intentionally excludes fixed household/industrial load and
    the critical facility's requirement.
    """
    return CrisisScenario(
        scenario_type=ScenarioType.SOLAR_DROP_DEMAND_SURGE,
        name="solar_drop_demand_surge",
        solar_generation_multiplier=0.50,
        flexible_demand_multiplier=1.30,
        start_timestep=start_timestep,
        duration_steps=duration_steps,
    )


def build_scenario(
    scenario_type: ScenarioType,
    *,
    start_timestep: int = 1,
    duration_steps: int | None = None,
) -> CrisisScenario:
    """Build a supported common scenario without inventing unassigned ones."""
    if scenario_type == ScenarioType.SOLAR_DROP_DEMAND_SURGE:
        return primary_crisis_scenario(
            start_timestep=start_timestep,
            duration_steps=duration_steps,
        )
    raise ScenarioError(
        scenario_type.value,
        "Only the primary solar-drop/flexible-demand-surge scenario is implemented",
    )


class SimulationConfig(BaseModel):
    """Physical configuration for a single simulation run.

    Values default to the frozen shared settings where a setting exists.  Load
    splits are intentionally local: the common configuration defines aggregate
    capacity but not household or industrial fixed/flexible load composition.
    """

    model_config = ConfigDict(validate_assignment=True)

    simulation_run_id: int | None = None
    timestep_seconds: int = Field(default=settings.SIMULATION_TIMESTEP_SECONDS, gt=0)
    simulation_start_time: datetime = Field(
        default_factory=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc)
    )

    solar_capacity_kw: float = Field(default=settings.DEFAULT_SOLAR_CAPACITY_KW, ge=0)
    solar_base_capacity_factor: float = Field(default=0.70, ge=0, le=1)
    wind_capacity_kw: float = Field(default=settings.DEFAULT_WIND_CAPACITY_KW, ge=0)
    wind_base_capacity_factor: float = Field(default=0.50, ge=0, le=1)

    battery_capacity_kwh: float = Field(default=settings.DEFAULT_BATTERY_CAPACITY_KWH, ge=0)
    battery_initial_soc: float = Field(default=0.50, ge=0, le=1)
    battery_min_soc: float = Field(default=settings.DEFAULT_BATTERY_MIN_SOC, ge=0, le=1)
    battery_max_soc: float = Field(default=settings.DEFAULT_BATTERY_MAX_SOC, ge=0, le=1)
    battery_charge_rate_kw: float = Field(default=settings.DEFAULT_BATTERY_CHARGE_RATE_KW, ge=0)
    battery_discharge_rate_kw: float = Field(
        default=settings.DEFAULT_BATTERY_DISCHARGE_RATE_KW, ge=0
    )
    battery_charge_efficiency: float = Field(default=0.95, gt=0, le=1)
    battery_discharge_efficiency: float = Field(default=0.95, gt=0, le=1)

    household_count: int = Field(default=settings.DEFAULT_NUM_HOUSEHOLDS, ge=0)
    household_fixed_demand_per_household_kw: float = Field(default=2.0, ge=0)
    household_flexible_demand_per_household_kw: float = Field(default=1.0, ge=0)
    industry_fixed_demand_kw: float = Field(
        default=settings.DEFAULT_INDUSTRIAL_LOAD_KW * 0.80, ge=0
    )
    industry_flexible_demand_kw: float = Field(
        default=settings.DEFAULT_INDUSTRIAL_LOAD_KW * 0.20, ge=0
    )

    ev_total_count: int = Field(default=settings.DEFAULT_EV_COUNT, ge=0)
    ev_connected_count: int = Field(default=settings.DEFAULT_EV_COUNT, ge=0)
    ev_battery_kwh_per_vehicle: float = Field(default=settings.DEFAULT_EV_BATTERY_KWH, ge=0)
    ev_average_soc: float = Field(default=0.60, ge=0, le=1)
    ev_flexible_demand_kw: float = Field(default=100.0, ge=0)

    critical_load_kw: float = Field(default=settings.DEFAULT_CRITICAL_LOAD_KW, ge=0)
    critical_backup_energy_kwh: float = Field(default=0.0, ge=0)

    grid_import_limit_kw: float = Field(default=settings.DEFAULT_GRID_IMPORT_LIMIT_KW, ge=0)
    grid_export_limit_kw: float = Field(default=settings.DEFAULT_GRID_EXPORT_LIMIT_KW, ge=0)
    grid_connected: bool = True
    grid_condition: GridCondition = GridCondition.STABLE
    electricity_price_per_kwh: float = Field(default=6.5, ge=0)

    @model_validator(mode="after")
    def validate_component_limits(self) -> "SimulationConfig":
        if self.battery_min_soc > self.battery_max_soc:
            raise ValueError("battery_min_soc cannot exceed battery_max_soc")
        if not self.battery_min_soc <= self.battery_initial_soc <= self.battery_max_soc:
            raise ValueError("battery_initial_soc must be between the configured SOC limits")
        if self.ev_connected_count > self.ev_total_count:
            raise ValueError("ev_connected_count cannot exceed ev_total_count")
        return self


class EnvironmentalConditions(BaseModel):
    """Exogenous conditions for a timestep, not decisions made by an agent."""

    solar_capacity_factor: float | None = Field(default=None, ge=0, le=1)
    wind_capacity_factor: float | None = Field(default=None, ge=0, le=1)
    grid_connected: bool | None = None
    grid_condition: GridCondition | None = None

    temperature_c: float | None = None
    cloud_cover_pct: float | None = Field(default=None, ge=0, le=100)
    solar_radiation_wm2: float | None = Field(default=None, ge=0)
    wind_speed_ms: float | None = Field(default=None, ge=0)
    weather_condition: str = "unknown"


class ControlInputs(BaseModel):
    """Already-approved physical setpoints applied during one timestep.

    Positive battery power charges the battery; negative power discharges it.
    Flexible-load values are requested *actual* demand values in kW.  ``None``
    preserves the exogenous/scenario-derived flexible demand.  The engine
    clamps every value to physical limits and gives the critical load fixed
    priority when supply is limited.
    """

    battery_power_kw: float = 0.0
    household_flexible_demand_kw: float | None = Field(default=None, ge=0)
    industry_flexible_demand_kw: float | None = Field(default=None, ge=0)
    ev_flexible_demand_kw: float | None = Field(default=None, ge=0)


class SimulationStepResult(BaseModel):
    """Detailed physical outcome for one completed timestep."""

    state: MicrogridState
    requested_demand_kw: float = Field(ge=0)
    served_demand_kw: float = Field(ge=0)
    unserved_load_kw: float = Field(ge=0)
    curtailed_generation_kw: float = Field(ge=0)
    critical_load_supply_kw: float = Field(ge=0)
    active_scenario: ScenarioType | None = None
    completed_at: datetime


class PrimaryScenarioRequest(BaseModel):
    """Optional API payload for activating the built-in crisis scenario."""

    start_timestep: int | None = Field(default=None, ge=0)
    duration_steps: int | None = Field(default=None, gt=0)
