from datetime import datetime, timezone

from backend.common.schemas.enums import CriticalLoadStatus
from backend.modules.simulation.service import SimulationService
from backend.modules.simulation.schemas import ControlInputs, SimulationConfig


def test_engine_records_an_initial_state_and_each_step():
    engine = SimulationService(
        SimulationConfig(
            solar_capacity_kw=100.0,
            wind_capacity_kw=0.0,
            solar_base_capacity_factor=1.0,
            household_count=1,
            household_fixed_demand_per_household_kw=10.0,
            household_flexible_demand_per_household_kw=0.0,
            industry_fixed_demand_kw=0.0,
            industry_flexible_demand_kw=0.0,
            ev_flexible_demand_kw=0.0,
            critical_load_kw=10.0,
        )
    )

    baseline = engine.initialize(start_time=datetime(2026, 1, 1, tzinfo=timezone.utc))
    stepped = engine.step(ControlInputs(battery_power_kw=-10.0))

    assert baseline.timestep == 0
    assert stepped.timestep == 1
    assert len(engine.get_history()) == 2
    assert stepped.battery.current_power_kw == -10.0
    assert stepped.critical_facility.status == CriticalLoadStatus.PROTECTED


def test_grid_shortage_never_allocates_critical_supply_after_other_loads():
    engine = SimulationService(
        SimulationConfig(
            solar_capacity_kw=0.0,
            wind_capacity_kw=0.0,
            household_count=1,
            household_fixed_demand_per_household_kw=50.0,
            household_flexible_demand_per_household_kw=0.0,
            industry_fixed_demand_kw=0.0,
            industry_flexible_demand_kw=0.0,
            ev_flexible_demand_kw=0.0,
            critical_load_kw=30.0,
            grid_import_limit_kw=30.0,
            battery_capacity_kwh=0.0,
            battery_initial_soc=0.0,
            battery_min_soc=0.0,
            battery_max_soc=0.0,
        )
    )

    state = engine.initialize()
    result = engine.get_last_result()

    assert state.critical_facility.is_protected is True
    assert result.unserved_load_kw == 50.0
