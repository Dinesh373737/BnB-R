from backend.common.schemas.enums import CriticalLoadStatus, ScenarioType
from backend.modules.simulation.environment import MicrogridEnvironment
from backend.modules.simulation.schemas import (
    EnvironmentalConditions,
    SimulationConfig,
    primary_crisis_scenario,
)
from backend.modules.simulation.service import SimulationService


def test_primary_crisis_halves_solar_and_increases_only_flexible_demand():
    engine = SimulationService(
        SimulationConfig(
            solar_capacity_kw=100.0,
            solar_base_capacity_factor=1.0,
            wind_capacity_kw=0.0,
            household_count=1,
            household_fixed_demand_per_household_kw=10.0,
            household_flexible_demand_per_household_kw=20.0,
            industry_fixed_demand_kw=10.0,
            industry_flexible_demand_kw=10.0,
            ev_flexible_demand_kw=10.0,
            critical_load_kw=10.0,
            grid_import_limit_kw=100.0,
        )
    )
    engine.initialize()
    engine.apply_primary_crisis()

    state = engine.step()
    result = engine.get_last_result()

    assert result.active_scenario == ScenarioType.SOLAR_DROP_DEMAND_SURGE
    assert state.solar.current_output_kw == 50.0
    assert state.households.fixed_demand_kw == 10.0
    assert state.households.flexible_demand_kw == 26.0
    assert state.industry.fixed_demand_kw == 10.0
    assert state.industry.flexible_demand_kw == 13.0
    assert state.ev.flexible_demand_kw == 13.0
    assert state.critical_facility.required_power_kw == 10.0
    assert state.critical_facility.status == CriticalLoadStatus.PROTECTED


def test_primary_crisis_can_expire():
    engine = SimulationService()
    engine.initialize()
    engine.apply_primary_crisis(duration_steps=1)

    engine.step()
    assert engine.get_last_result().active_scenario == ScenarioType.SOLAR_DROP_DEMAND_SURGE
    engine.step()
    assert engine.get_last_result().active_scenario is None


def test_environment_applies_exogenous_inputs_and_primary_scenario_deterministically():
    environment = MicrogridEnvironment(SimulationConfig(solar_base_capacity_factor=0.8))
    scenario = primary_crisis_scenario(start_timestep=2)

    before, solar_before, flexible_before = environment.resolve_conditions(
        EnvironmentalConditions(solar_capacity_factor=0.9), scenario, timestep=1
    )
    during, solar_during, flexible_during = environment.resolve_conditions(
        EnvironmentalConditions(solar_capacity_factor=0.9), scenario, timestep=2
    )

    assert before.solar_capacity_factor == during.solar_capacity_factor == 0.9
    assert (solar_before, flexible_before) == (1.0, 1.0)
    assert (solar_during, flexible_during) == (0.5, 1.3)
