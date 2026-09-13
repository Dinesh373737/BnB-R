from backend.common.schemas.enums import ResourceStatus
from backend.modules.simulation.loop import SIMULATION_LOOP_STEPS
from backend.modules.simulation.service import SimulationService
from backend.modules.simulation.schemas import ControlInputs, SimulationConfig


def test_timestep_uses_grid_for_remaining_deficit_after_local_generation():
    engine = SimulationService(
        SimulationConfig(
            solar_capacity_kw=100.0,
            solar_base_capacity_factor=0.5,
            wind_capacity_kw=0.0,
            household_count=1,
            household_fixed_demand_per_household_kw=40.0,
            household_flexible_demand_per_household_kw=0.0,
            industry_fixed_demand_kw=0.0,
            industry_flexible_demand_kw=0.0,
            ev_flexible_demand_kw=0.0,
            critical_load_kw=30.0,
            grid_import_limit_kw=100.0,
        )
    )
    engine.initialize()

    state = engine.step(controls=ControlInputs(battery_power_kw=-10.0))

    assert state.total_generation_kw == 60.0
    assert state.total_demand_kw == 70.0
    assert state.energy_balance_kw == -10.0
    assert state.grid_connection.import_power_kw == 10.0
    assert state.battery.status == ResourceStatus.DISCHARGING


def test_service_runs_the_defined_thirteen_step_loop():
    engine = SimulationService(SimulationConfig())

    states = engine.run()

    assert len(states) == SIMULATION_LOOP_STEPS
    assert states[0].timestep == 1
    assert states[-1].timestep == SIMULATION_LOOP_STEPS
    assert all(state.total_generation_kw >= 0.0 for state in states)
    assert all(state.total_demand_kw >= 0.0 for state in states)
    assert all(
        state.battery.min_soc <= state.battery.current_soc <= state.battery.max_soc
        for state in states
    )
    assert all(
        state.grid_connection.import_power_kw <= state.grid_connection.import_limit_kw
        and state.grid_connection.export_power_kw <= state.grid_connection.export_limit_kw
        for state in states
    )
