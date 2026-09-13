"""Microgrid environment and exogenous-condition resolution."""

from dataclasses import dataclass

from backend.common.schemas.enums import GridCondition
from backend.modules.simulation.microgrid import (
    Battery,
    CriticalFacility,
    EVFleet,
    GridConnection,
    HouseholdLoad,
    IndustrialLoad,
    SolarGenerator,
    WindGenerator,
)
from backend.modules.simulation.schemas import (
    CrisisScenario,
    EnvironmentalConditions,
    SimulationConfig,
)


@dataclass(frozen=True)
class ResolvedConditions:
    """The concrete non-agent conditions used for a timestep."""

    solar_capacity_factor: float
    wind_capacity_factor: float
    grid_connected: bool
    grid_condition: GridCondition
    temperature_c: float | None
    cloud_cover_pct: float | None
    solar_radiation_wm2: float | None
    wind_speed_ms: float | None
    weather_condition: str


class MicrogridEnvironment:
    """Owns the mutable physical components of one simulated microgrid."""

    def __init__(self, config: SimulationConfig):
        self.config = config
        self.solar = SolarGenerator(capacity_kw=config.solar_capacity_kw)
        self.wind = WindGenerator(capacity_kw=config.wind_capacity_kw)
        self.battery = Battery(
            capacity_kwh=config.battery_capacity_kwh,
            current_soc=config.battery_initial_soc,
            min_soc=config.battery_min_soc,
            max_soc=config.battery_max_soc,
            charge_rate_kw=config.battery_charge_rate_kw,
            discharge_rate_kw=config.battery_discharge_rate_kw,
            charge_efficiency=config.battery_charge_efficiency,
            discharge_efficiency=config.battery_discharge_efficiency,
        )
        self.grid = GridConnection(
            import_limit_kw=config.grid_import_limit_kw,
            export_limit_kw=config.grid_export_limit_kw,
            is_connected=config.grid_connected,
            condition=config.grid_condition,
        )
        self.households = HouseholdLoad(
            count=config.household_count,
            fixed_demand_per_household_kw=config.household_fixed_demand_per_household_kw,
            flexible_demand_per_household_kw=config.household_flexible_demand_per_household_kw,
        )
        self.industry = IndustrialLoad(
            fixed_demand_kw=config.industry_fixed_demand_kw,
            flexible_demand_kw=config.industry_flexible_demand_kw,
        )
        self.ev = EVFleet(
            total_count=config.ev_total_count,
            connected_count=config.ev_connected_count,
            battery_kwh_per_vehicle=config.ev_battery_kwh_per_vehicle,
            average_soc=config.ev_average_soc,
            flexible_demand_kw=config.ev_flexible_demand_kw,
        )
        self.critical_facility = CriticalFacility(
            required_power_kw=config.critical_load_kw,
            backup_energy_kwh=config.critical_backup_energy_kwh,
        )

    def resolve_conditions(
        self,
        inputs: EnvironmentalConditions | None,
        scenario: CrisisScenario | None,
        timestep: int,
    ) -> tuple[ResolvedConditions, float, float]:
        """Resolve caller inputs and active scenario modifiers for one step."""
        inputs = inputs or EnvironmentalConditions()
        solar_factor = (
            self.config.solar_base_capacity_factor
            if inputs.solar_capacity_factor is None
            else inputs.solar_capacity_factor
        )
        wind_factor = (
            self.config.wind_base_capacity_factor
            if inputs.wind_capacity_factor is None
            else inputs.wind_capacity_factor
        )
        solar_multiplier = 1.0
        flexible_demand_multiplier = 1.0
        if scenario and scenario.is_active_at(timestep):
            solar_multiplier = scenario.solar_generation_multiplier
            flexible_demand_multiplier = scenario.flexible_demand_multiplier

        return (
            ResolvedConditions(
                solar_capacity_factor=solar_factor,
                wind_capacity_factor=wind_factor,
                grid_connected=(
                    self.config.grid_connected
                    if inputs.grid_connected is None
                    else inputs.grid_connected
                ),
                grid_condition=(
                    self.config.grid_condition
                    if inputs.grid_condition is None
                    else inputs.grid_condition
                ),
                temperature_c=inputs.temperature_c,
                cloud_cover_pct=inputs.cloud_cover_pct,
                solar_radiation_wm2=inputs.solar_radiation_wm2,
                wind_speed_ms=inputs.wind_speed_ms,
                weather_condition=inputs.weather_condition,
            ),
            solar_multiplier,
            flexible_demand_multiplier,
        )
