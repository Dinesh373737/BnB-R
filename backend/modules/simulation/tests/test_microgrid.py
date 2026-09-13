from backend.common.schemas.enums import CriticalLoadStatus
from backend.modules.simulation.microgrid import (
    Battery,
    CriticalFacility,
    EVFleet,
    HouseholdLoad,
    IndustrialLoad,
    RenewableGenerator,
)


def test_renewable_generator_is_limited_to_rated_capacity():
    generator = RenewableGenerator(capacity_kw=100.0)

    assert generator.generate(1.0, multiplier=2.0) == 100.0
    assert generator.utilization_pct == 100.0


def test_battery_respects_soc_and_rate_limits():
    battery = Battery(
        capacity_kwh=100.0,
        current_soc=0.50,
        min_soc=0.10,
        max_soc=0.90,
        charge_rate_kw=20.0,
        discharge_rate_kw=20.0,
    )

    assert battery.apply_power(-100.0, timestep_hours=1.0) == -20.0
    assert battery.current_soc == 0.50 - (20.0 / 0.95 / 100.0)

    battery.current_soc = 0.89
    assert battery.apply_power(20.0, timestep_hours=1.0) < 20.0
    assert battery.current_soc == 0.90


def test_load_components_are_non_negative_and_critical_supply_is_prioritized():
    household = HouseholdLoad(2, fixed_demand_per_household_kw=3.0, flexible_demand_per_household_kw=1.0)
    industry = IndustrialLoad(fixed_demand_kw=5.0, flexible_demand_kw=2.0)
    ev = EVFleet(2, 2, battery_kwh_per_vehicle=60.0, average_soc=0.5, flexible_demand_kw=4.0)
    critical = CriticalFacility(required_power_kw=10.0)

    assert household.resolve_demand(-1.0) == (6.0, 0.0)
    assert industry.resolve_demand(-1.0) == (5.0, 0.0)
    assert ev.resolve_demand(-1.0) == 0.0
    assert ev.total_battery_kwh == 120.0
    assert critical.supply_status(10.0) == (10.0, CriticalLoadStatus.PROTECTED, True)
