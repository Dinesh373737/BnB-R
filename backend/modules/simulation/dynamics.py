"""Deterministic microgrid energy-balance calculations."""

from datetime import datetime, timezone

from backend.common.schemas.enums import DataSourceType, ResourceStatus
from backend.common.schemas.microgrid_state import (
    BatteryState,
    CriticalFacilityState,
    EVState,
    GridConnectionState,
    HouseholdState,
    IndustryState,
    MicrogridState,
    SolarState,
    WeatherState,
    WindState,
)
from backend.modules.simulation.environment import MicrogridEnvironment, ResolvedConditions
from backend.modules.simulation.schemas import (
    ControlInputs,
    CrisisScenario,
    SimulationConfig,
    SimulationStepResult,
)


def advance_timestep(
    *,
    environment: MicrogridEnvironment,
    config: SimulationConfig,
    timestep: int,
    timestamp: datetime | None = None,
    controls: ControlInputs | None = None,
    conditions: ResolvedConditions,
    solar_generation_multiplier: float = 1.0,
    flexible_demand_multiplier: float = 1.0,
    active_scenario: CrisisScenario | None = None,
) -> SimulationStepResult:
    """Advance all physical components once and return a shared state snapshot.

    Accounting convention: ``energy_balance_kw`` is the pre-grid local balance
    (local generation minus requested load).  Grid import/export is represented
    separately in ``grid_connection``.  Battery discharge is local generation;
    battery charging is local demand.
    """
    controls = controls or ControlInputs()
    timestamp = timestamp or datetime.now(timezone.utc)
    timestep_hours = config.timestep_seconds / 3600.0

    solar_output_kw = environment.solar.generate(
        conditions.solar_capacity_factor,
        solar_generation_multiplier,
    )
    wind_output_kw = environment.wind.generate(conditions.wind_capacity_factor)

    household_fixed_kw, household_flexible_kw = environment.households.resolve_demand(
        flexible_demand_multiplier,
        controls.household_flexible_demand_kw,
    )
    industry_fixed_kw, industry_flexible_kw = environment.industry.resolve_demand(
        flexible_demand_multiplier,
        controls.industry_flexible_demand_kw,
    )
    ev_flexible_kw = environment.ev.resolve_demand(
        flexible_demand_multiplier,
        controls.ev_flexible_demand_kw,
    )
    fixed_load_kw = household_fixed_kw + industry_fixed_kw
    non_storage_demand_kw = (
        environment.critical_facility.required_power_kw
        + fixed_load_kw
        + household_flexible_kw
        + industry_flexible_kw
        + ev_flexible_kw
    )

    # Charging is not allowed to consume capacity required for existing loads.
    # This is a physical critical-load priority, not an AI decision.
    requested_battery_power_kw = controls.battery_power_kw
    if requested_battery_power_kw > 0:
        grid_support_kw = (
            config.grid_import_limit_kw
            if conditions.grid_connected and conditions.grid_condition.value != "outage"
            else 0.0
        )
        maximum_charge_support_kw = max(
            0.0,
            solar_output_kw + wind_output_kw + grid_support_kw - non_storage_demand_kw,
        )
        requested_battery_power_kw = min(
            requested_battery_power_kw,
            maximum_charge_support_kw,
        )
    battery_power_kw = environment.battery.apply_power(
        requested_battery_power_kw,
        timestep_hours,
    )

    battery_charge_kw = max(0.0, battery_power_kw)
    battery_discharge_kw = max(0.0, -battery_power_kw)
    total_generation_kw = solar_output_kw + wind_output_kw + battery_discharge_kw
    renewable_generation_kw = solar_output_kw + wind_output_kw
    total_demand_kw = non_storage_demand_kw + battery_charge_kw
    energy_balance_kw = total_generation_kw - total_demand_kw

    environment.grid.is_connected = conditions.grid_connected
    environment.grid.condition = conditions.grid_condition
    exchange = environment.grid.exchange(energy_balance_kw)
    unserved_load_kw = max(0.0, -energy_balance_kw - exchange.import_power_kw)
    curtailed_generation_kw = max(0.0, energy_balance_kw - exchange.export_power_kw)
    served_demand_kw = total_demand_kw - unserved_load_kw

    # Available physical supply is allocated to the critical facility first.
    critical_supply_kw, critical_status, critical_is_protected = (
        environment.critical_facility.supply_status(
            total_generation_kw + exchange.import_power_kw
        )
    )

    battery_status = environment.battery.status
    renewable_percentage = (
        renewable_generation_kw / total_generation_kw * 100.0
        if total_generation_kw > 0
        else 0.0
    )
    grid_dependency_pct = (
        exchange.import_power_kw / total_demand_kw * 100.0 if total_demand_kw > 0 else 0.0
    )
    state = MicrogridState(
        timestamp=timestamp,
        simulation_run_id=config.simulation_run_id,
        timestep=timestep,
        total_demand_kw=total_demand_kw,
        total_generation_kw=total_generation_kw,
        renewable_generation_kw=renewable_generation_kw,
        renewable_percentage=renewable_percentage,
        energy_balance_kw=energy_balance_kw,
        grid_dependency_pct=grid_dependency_pct,
        solar=SolarState(
            capacity_kw=config.solar_capacity_kw,
            current_output_kw=solar_output_kw,
            utilization_pct=environment.solar.utilization_pct,
            status=ResourceStatus.ACTIVE,
        ),
        wind=WindState(
            capacity_kw=config.wind_capacity_kw,
            current_output_kw=wind_output_kw,
            utilization_pct=environment.wind.utilization_pct,
            status=ResourceStatus.ACTIVE,
        ),
        battery=BatteryState(
            capacity_kwh=config.battery_capacity_kwh,
            current_soc=environment.battery.current_soc,
            soc_percentage=environment.battery.current_soc * 100.0,
            current_power_kw=battery_power_kw,
            min_soc=config.battery_min_soc,
            max_soc=config.battery_max_soc,
            charge_rate_kw=config.battery_charge_rate_kw,
            discharge_rate_kw=config.battery_discharge_rate_kw,
            energy_available_kwh=environment.battery.energy_available_kwh,
            status=battery_status,
        ),
        ev=EVState(
            total_count=config.ev_total_count,
            connected_count=config.ev_connected_count,
            charging_count=(config.ev_connected_count if ev_flexible_kw > 0 else 0),
            total_demand_kw=ev_flexible_kw,
            total_battery_kwh=environment.ev.total_battery_kwh,
            average_soc=environment.ev.average_soc,
            flexible_demand_kw=ev_flexible_kw,
        ),
        households=HouseholdState(
            count=config.household_count,
            total_demand_kw=household_fixed_kw + household_flexible_kw,
            fixed_demand_kw=household_fixed_kw,
            flexible_demand_kw=household_flexible_kw,
        ),
        industry=IndustryState(
            total_demand_kw=config.industry_fixed_demand_kw + industry_flexible_kw,
            fixed_demand_kw=industry_fixed_kw,
            flexible_demand_kw=industry_flexible_kw,
        ),
        critical_facility=CriticalFacilityState(
            required_power_kw=environment.critical_facility.required_power_kw,
            current_supply_kw=critical_supply_kw,
            backup_energy_kwh=environment.critical_facility.backup_energy_kwh,
            reserve_power_kw=environment.critical_facility.required_power_kw,
            status=critical_status,
            is_protected=critical_is_protected,
        ),
        grid_connection=GridConnectionState(
            condition=conditions.grid_condition,
            import_power_kw=exchange.import_power_kw,
            export_power_kw=exchange.export_power_kw,
            import_limit_kw=config.grid_import_limit_kw,
            export_limit_kw=config.grid_export_limit_kw,
            is_connected=(
                conditions.grid_connected and conditions.grid_condition.value != "outage"
            ),
            electricity_price_per_kwh=config.electricity_price_per_kwh,
        ),
        weather=WeatherState(
            temperature_c=conditions.temperature_c,
            cloud_cover_pct=conditions.cloud_cover_pct,
            solar_radiation_wm2=conditions.solar_radiation_wm2,
            wind_speed_ms=conditions.wind_speed_ms,
            weather_condition=conditions.weather_condition,
            data_source=DataSourceType.SIMULATED,
        ),
        data_source=DataSourceType.SIMULATED,
    )
    return SimulationStepResult(
        state=state,
        requested_demand_kw=total_demand_kw,
        served_demand_kw=served_demand_kw,
        unserved_load_kw=unserved_load_kw,
        curtailed_generation_kw=curtailed_generation_kw,
        critical_load_supply_kw=critical_supply_kw,
        active_scenario=(
            active_scenario.scenario_type
            if active_scenario and active_scenario.is_active_at(timestep)
            else None
        ),
        completed_at=timestamp,
    )
