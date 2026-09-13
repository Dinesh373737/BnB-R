"""Unit tests for analytics metric calculation functions.

All tests use deterministic sample data — no database, no simulation engine.
"""

import pytest

from backend.modules.analytics.schemas import TimestepSnapshot, TradeData
from backend.modules.analytics.metrics import (
    calculate_all_metrics,
    calculate_average_cost,
    calculate_average_trading_price,
    calculate_battery_reserve,
    calculate_battery_utilization,
    calculate_cost_savings_percent,
    calculate_critical_load_protection,
    calculate_peak_demand,
    calculate_peak_reduction_percent,
    calculate_recovery_time,
    calculate_renewable_curtailment,
    calculate_renewable_utilization,
    calculate_solar_utilization,
    calculate_total_cost,
    calculate_total_energy_traded,
    calculate_transaction_count,
    calculate_unserved_energy,
)


# ══════════════════════════════════════════════════════════════════════════
#  FIXTURES — deterministic sample data
# ══════════════════════════════════════════════════════════════════════════


def _snap(**overrides) -> TimestepSnapshot:
    """Build a ``TimestepSnapshot`` with sensible defaults and overrides."""
    defaults = dict(
        timestep=0,
        total_demand_kw=500.0,
        total_generation_kw=400.0,
        renewable_generation_kw=350.0,
        energy_balance_kw=-100.0,
        solar_output_kw=200.0,
        solar_capacity_kw=300.0,
        wind_output_kw=150.0,
        wind_capacity_kw=250.0,
        battery_soc=0.5,
        battery_capacity_kwh=1000.0,
        battery_power_kw=-50.0,  # discharging
        grid_import_kw=100.0,
        grid_export_kw=0.0,
        electricity_price_per_kwh=6.5,
        critical_load_required_kw=50.0,
        critical_load_supply_kw=50.0,
        critical_load_status="protected",
        risk_level="low",
        risk_score=10.0,
        energy_traded_kwh=0.0,
        unserved_load_kw=0.0,
        curtailed_generation_kw=0.0,
        timestep_seconds=60,
    )
    defaults.update(overrides)
    return TimestepSnapshot(**defaults)


def _trade(**overrides) -> TradeData:
    defaults = dict(energy_kwh=10.0, price_per_kwh=5.0, total_cost=50.0)
    defaults.update(overrides)
    return TradeData(**defaults)


@pytest.fixture
def sample_snapshots() -> list[TimestepSnapshot]:
    return [
        _snap(timestep=0, total_demand_kw=500, grid_import_kw=100, battery_power_kw=-50),
        _snap(timestep=1, total_demand_kw=600, grid_import_kw=200, battery_power_kw=-80),
        _snap(timestep=2, total_demand_kw=450, grid_import_kw=50, battery_power_kw=30),
        _snap(timestep=3, total_demand_kw=700, grid_import_kw=300, battery_power_kw=-100),
        _snap(timestep=4, total_demand_kw=400, grid_import_kw=0, battery_power_kw=60),
    ]


@pytest.fixture
def sample_trades() -> list[TradeData]:
    return [
        _trade(energy_kwh=10.0, price_per_kwh=5.0),
        _trade(energy_kwh=20.0, price_per_kwh=4.0),
        _trade(energy_kwh=5.0, price_per_kwh=6.0),
    ]


# ══════════════════════════════════════════════════════════════════════════
#  ECONOMIC METRICS
# ══════════════════════════════════════════════════════════════════════════


class TestTotalCost:
    def test_basic(self, sample_snapshots):
        cost = calculate_total_cost(sample_snapshots)
        # Each snapshot: grid_import * 6.5 * (60/3600)
        expected = sum(
            s.grid_import_kw * 6.5 * (60 / 3600) for s in sample_snapshots
        )
        assert abs(cost - round(expected, 4)) < 0.01

    def test_empty(self):
        assert calculate_total_cost([]) == 0.0

    def test_zero_import(self):
        snaps = [_snap(grid_import_kw=0.0)]
        assert calculate_total_cost(snaps) == 0.0


class TestAverageCost:
    def test_basic(self, sample_snapshots):
        avg = calculate_average_cost(sample_snapshots)
        assert avg > 0.0

    def test_empty(self):
        assert calculate_average_cost([]) == 0.0

    def test_zero_import(self):
        snaps = [_snap(grid_import_kw=0.0)]
        assert calculate_average_cost(snaps) == 0.0


class TestCostSavings:
    def test_positive_savings(self):
        assert calculate_cost_savings_percent(100.0, 70.0) == 30.0

    def test_no_savings(self):
        assert calculate_cost_savings_percent(100.0, 100.0) == 0.0

    def test_negative_savings(self):
        result = calculate_cost_savings_percent(100.0, 120.0)
        assert result == -20.0

    def test_zero_baseline(self):
        assert calculate_cost_savings_percent(0.0, 50.0) == 0.0


# ══════════════════════════════════════════════════════════════════════════
#  GRID METRICS
# ══════════════════════════════════════════════════════════════════════════


class TestPeakDemand:
    def test_basic(self, sample_snapshots):
        assert calculate_peak_demand(sample_snapshots) == 700.0

    def test_empty(self):
        assert calculate_peak_demand([]) == 0.0

    def test_single(self):
        assert calculate_peak_demand([_snap(total_demand_kw=123.0)]) == 123.0


class TestPeakReduction:
    def test_positive(self):
        assert calculate_peak_reduction_percent(800.0, 600.0) == 25.0

    def test_zero_baseline(self):
        assert calculate_peak_reduction_percent(0.0, 100.0) == 0.0

    def test_no_reduction(self):
        assert calculate_peak_reduction_percent(500.0, 500.0) == 0.0


# ══════════════════════════════════════════════════════════════════════════
#  RENEWABLE METRICS
# ══════════════════════════════════════════════════════════════════════════


class TestRenewableUtilization:
    def test_basic(self, sample_snapshots):
        util = calculate_renewable_utilization(sample_snapshots)
        total_ren = sum(s.renewable_generation_kw for s in sample_snapshots)
        total_dem = sum(s.total_demand_kw for s in sample_snapshots)
        expected = round(total_ren / total_dem * 100.0, 2)
        assert abs(util - expected) < 0.01

    def test_empty(self):
        assert calculate_renewable_utilization([]) == 0.0

    def test_zero_demand(self):
        snaps = [_snap(total_demand_kw=0.0, renewable_generation_kw=100.0)]
        assert calculate_renewable_utilization(snaps) == 0.0


class TestSolarUtilization:
    def test_basic(self):
        snaps = [_snap(solar_output_kw=200, solar_capacity_kw=300)]
        util = calculate_solar_utilization(snaps)
        assert abs(util - 66.67) < 0.01

    def test_zero_capacity(self):
        snaps = [_snap(solar_output_kw=0, solar_capacity_kw=0)]
        assert calculate_solar_utilization(snaps) == 0.0

    def test_empty(self):
        assert calculate_solar_utilization([]) == 0.0


class TestCurtailment:
    def test_basic(self):
        snaps = [
            _snap(curtailed_generation_kw=50.0, timestep_seconds=60),
            _snap(curtailed_generation_kw=30.0, timestep_seconds=60),
        ]
        # 50 * 1/60 + 30 * 1/60 = 1.3333 kWh
        result = calculate_renewable_curtailment(snaps)
        assert abs(result - 1.3333) < 0.01

    def test_empty(self):
        assert calculate_renewable_curtailment([]) == 0.0

    def test_zero_curtailment(self):
        snaps = [_snap(curtailed_generation_kw=0.0)]
        assert calculate_renewable_curtailment(snaps) == 0.0


# ══════════════════════════════════════════════════════════════════════════
#  STORAGE METRICS
# ══════════════════════════════════════════════════════════════════════════


class TestBatteryUtilization:
    def test_all_active(self):
        snaps = [_snap(battery_power_kw=-100), _snap(battery_power_kw=50)]
        assert calculate_battery_utilization(snaps) == 100.0

    def test_all_idle(self):
        snaps = [_snap(battery_power_kw=0.0), _snap(battery_power_kw=0.0)]
        assert calculate_battery_utilization(snaps) == 0.0

    def test_empty(self):
        assert calculate_battery_utilization([]) == 0.0


class TestBatteryReserve:
    def test_basic(self):
        snaps = [_snap(battery_soc=0.5), _snap(battery_soc=0.7)]
        reserve = calculate_battery_reserve(snaps)
        assert abs(reserve - 60.0) < 0.01  # average 0.6 → 60%

    def test_empty(self):
        assert calculate_battery_reserve([]) == 0.0


# ══════════════════════════════════════════════════════════════════════════
#  RESILIENCE METRICS
# ══════════════════════════════════════════════════════════════════════════


class TestUnservedEnergy:
    def test_basic(self):
        snaps = [
            _snap(unserved_load_kw=60.0, timestep_seconds=60),
            _snap(unserved_load_kw=0.0, timestep_seconds=60),
        ]
        # 60 kW × 1/60 h = 1.0 kWh
        result = calculate_unserved_energy(snaps)
        assert abs(result - 1.0) < 0.01

    def test_empty(self):
        assert calculate_unserved_energy([]) == 0.0

    def test_zero_unserved(self):
        snaps = [_snap(unserved_load_kw=0.0)]
        assert calculate_unserved_energy(snaps) == 0.0


class TestCriticalLoadProtection:
    def test_all_protected(self):
        snaps = [
            _snap(critical_load_status="protected"),
            _snap(critical_load_status="protected"),
        ]
        assert calculate_critical_load_protection(snaps) == 100.0

    def test_partial(self):
        snaps = [
            _snap(critical_load_status="protected"),
            _snap(critical_load_status="at_risk"),
            _snap(critical_load_status="protected"),
            _snap(critical_load_status="unprotected"),
        ]
        assert abs(calculate_critical_load_protection(snaps) - 50.0) < 0.01

    def test_empty(self):
        assert calculate_critical_load_protection([]) == 0.0


class TestRecoveryTime:
    def test_crisis_and_recovery(self):
        snaps = [
            _snap(timestep=0, risk_level="low", timestep_seconds=60),
            _snap(timestep=1, risk_level="low", timestep_seconds=60),
            _snap(timestep=2, risk_level="high", timestep_seconds=60),
            _snap(timestep=3, risk_level="critical", timestep_seconds=60),
            _snap(timestep=4, risk_level="high", timestep_seconds=60),
            _snap(timestep=5, risk_level="medium", timestep_seconds=60),  # recovered
            _snap(timestep=6, risk_level="low", timestep_seconds=60),
        ]
        # Crisis starts at step 2, recovers at step 5 → 3 steps × 60s / 60 = 3 min
        assert abs(calculate_recovery_time(snaps) - 3.0) < 0.01

    def test_no_crisis(self):
        snaps = [
            _snap(timestep=0, risk_level="low"),
            _snap(timestep=1, risk_level="medium"),
        ]
        assert calculate_recovery_time(snaps) == 0.0

    def test_never_recovers(self):
        snaps = [
            _snap(timestep=0, risk_level="low", timestep_seconds=60),
            _snap(timestep=1, risk_level="high", timestep_seconds=60),
            _snap(timestep=2, risk_level="critical", timestep_seconds=60),
            _snap(timestep=3, risk_level="high", timestep_seconds=60),
        ]
        # Crisis starts at 1, never recovers → last step is 3 → 2 steps × 1 min
        assert abs(calculate_recovery_time(snaps) - 2.0) < 0.01

    def test_empty(self):
        assert calculate_recovery_time([]) == 0.0


# ══════════════════════════════════════════════════════════════════════════
#  MARKET METRICS
# ══════════════════════════════════════════════════════════════════════════


class TestTotalEnergyTraded:
    def test_basic(self, sample_trades):
        total = calculate_total_energy_traded(sample_trades)
        assert abs(total - 35.0) < 0.01

    def test_empty(self):
        assert calculate_total_energy_traded([]) == 0.0


class TestTransactionCount:
    def test_basic(self, sample_trades):
        assert calculate_transaction_count(sample_trades) == 3

    def test_empty(self):
        assert calculate_transaction_count([]) == 0


class TestAverageTradingPrice:
    def test_basic(self, sample_trades):
        # Volume-weighted: (10*5 + 20*4 + 5*6) / 35 = 160/35 ≈ 4.5714
        price = calculate_average_trading_price(sample_trades)
        assert abs(price - 4.5714) < 0.01

    def test_empty(self):
        assert calculate_average_trading_price([]) == 0.0

    def test_zero_energy(self):
        trades = [_trade(energy_kwh=0.0)]
        assert calculate_average_trading_price(trades) == 0.0


# ══════════════════════════════════════════════════════════════════════════
#  AGGREGATE
# ══════════════════════════════════════════════════════════════════════════


class TestCalculateAllMetrics:
    def test_returns_all_categories(self, sample_snapshots, sample_trades):
        result = calculate_all_metrics(sample_snapshots, sample_trades)
        assert result.economic.total_cost > 0
        assert result.grid.peak_demand_kw == 700.0
        assert result.renewable.renewable_utilization_percent > 0
        assert result.storage.battery_reserve_percent > 0
        assert result.market.transaction_count == 3

    def test_empty_inputs(self):
        result = calculate_all_metrics([], [])
        assert result.economic.total_cost == 0.0
        assert result.grid.peak_demand_kw == 0.0
        assert result.renewable.renewable_utilization_percent == 0.0
        assert result.storage.battery_reserve_percent == 0.0
        assert result.resilience.unserved_energy_kwh == 0.0
        assert result.market.total_energy_traded_kwh == 0.0

    def test_no_trades(self, sample_snapshots):
        result = calculate_all_metrics(sample_snapshots)
        assert result.market.total_energy_traded_kwh == 0.0
        assert result.market.transaction_count == 0
        assert result.market.average_trading_price == 0.0


# ══════════════════════════════════════════════════════════════════════════
#  EDGE CASES — zero / empty
# ══════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_zero_demand_everywhere(self):
        snaps = [_snap(total_demand_kw=0.0, grid_import_kw=0.0)]
        result = calculate_all_metrics(snaps)
        assert result.economic.total_cost == 0.0
        assert result.grid.peak_demand_kw == 0.0
        assert result.renewable.renewable_utilization_percent == 0.0

    def test_zero_generation(self):
        snaps = [
            _snap(
                total_generation_kw=0.0,
                renewable_generation_kw=0.0,
                solar_output_kw=0.0,
                wind_output_kw=0.0,
            )
        ]
        result = calculate_all_metrics(snaps)
        assert result.renewable.solar_utilization_percent == 0.0

    def test_single_timestep(self):
        snaps = [_snap()]
        result = calculate_all_metrics(snaps)
        assert result.economic.total_cost > 0
        assert result.grid.peak_demand_kw == 500.0
