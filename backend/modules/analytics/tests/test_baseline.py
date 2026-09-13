"""Unit tests for the baseline controller and baseline-vs-GridMind comparison.

These tests exercise the BaselineController's deterministic decision logic
and the comparison/improvement calculations, using deterministic sample data.
"""

import pytest

from backend.modules.analytics.schemas import TimestepSnapshot, FullMetricSet
from backend.modules.analytics.metrics import (
    calculate_all_metrics,
    calculate_cost_savings_percent,
    calculate_peak_reduction_percent,
)
from backend.modules.analytics.baseline import BaselineController


# ══════════════════════════════════════════════════════════════════════════
#  FIXTURES
# ══════════════════════════════════════════════════════════════════════════


def _snap(**overrides) -> TimestepSnapshot:
    """Build a ``TimestepSnapshot`` with sensible defaults."""
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
        battery_power_kw=-50.0,
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


# ══════════════════════════════════════════════════════════════════════════
#  BASELINE CONTROLLER — decision logic
# ══════════════════════════════════════════════════════════════════════════


class TestBaselineController:
    """Test that the baseline controller can be instantiated and produces
    deterministic control inputs.
    """

    def test_instantiation(self):
        controller = BaselineController()
        assert controller is not None

    def test_run_with_defaults(self):
        """Baseline should run with default config and return snapshots."""
        controller = BaselineController()
        snapshots = controller.run(num_steps=3)
        # timestep 0 (init) + 3 steps = 4 snapshots
        assert len(snapshots) == 4
        for s in snapshots:
            assert isinstance(s, TimestepSnapshot)

    def test_run_with_config(self):
        """Baseline accepts a custom SimulationConfig."""
        from backend.modules.simulation.schemas import SimulationConfig

        cfg = SimulationConfig(
            solar_capacity_kw=500.0,
            wind_capacity_kw=200.0,
            battery_capacity_kwh=2000.0,
        )
        controller = BaselineController()
        snapshots = controller.run(cfg, num_steps=2)
        assert len(snapshots) == 3

    def test_run_with_scenario(self):
        """Baseline accepts a CrisisScenario."""
        from backend.modules.simulation.schemas import primary_crisis_scenario

        scenario = primary_crisis_scenario(start_timestep=1, duration_steps=2)
        controller = BaselineController()
        snapshots = controller.run(scenario=scenario, num_steps=5)
        assert len(snapshots) == 6

    def test_deterministic(self):
        """Two identical runs should produce the same results."""
        controller = BaselineController()
        run1 = controller.run(num_steps=3)
        run2 = controller.run(num_steps=3)
        for s1, s2 in zip(run1, run2):
            assert s1.total_demand_kw == s2.total_demand_kw
            assert s1.total_generation_kw == s2.total_generation_kw
            assert s1.battery_soc == s2.battery_soc


# ══════════════════════════════════════════════════════════════════════════
#  COMPARISON LOGIC
# ══════════════════════════════════════════════════════════════════════════


class TestComparison:
    """Test the improvement calculation between baseline and GridMind."""

    @pytest.fixture
    def baseline_snapshots(self) -> list[TimestepSnapshot]:
        """Baseline performs worse: higher cost, higher peak, more unserved."""
        return [
            _snap(
                timestep=i,
                total_demand_kw=600.0,
                grid_import_kw=200.0,
                unserved_load_kw=20.0,
                critical_load_status="at_risk" if i == 2 else "protected",
                risk_level="high" if i == 2 else "low",
            )
            for i in range(5)
        ]

    @pytest.fixture
    def gridmind_snapshots(self) -> list[TimestepSnapshot]:
        """GridMind performs better: lower cost, lower peak, less unserved."""
        return [
            _snap(
                timestep=i,
                total_demand_kw=500.0,
                grid_import_kw=100.0,
                unserved_load_kw=0.0,
                critical_load_status="protected",
                risk_level="low",
            )
            for i in range(5)
        ]

    def test_cost_savings(self, baseline_snapshots, gridmind_snapshots):
        bl_metrics = calculate_all_metrics(baseline_snapshots)
        gm_metrics = calculate_all_metrics(gridmind_snapshots)
        savings = calculate_cost_savings_percent(
            bl_metrics.economic.total_cost,
            gm_metrics.economic.total_cost,
        )
        assert savings > 0  # GridMind should have lower cost

    def test_peak_reduction(self, baseline_snapshots, gridmind_snapshots):
        bl_metrics = calculate_all_metrics(baseline_snapshots)
        gm_metrics = calculate_all_metrics(gridmind_snapshots)
        reduction = calculate_peak_reduction_percent(
            bl_metrics.grid.peak_demand_kw,
            gm_metrics.grid.peak_demand_kw,
        )
        assert reduction > 0  # GridMind should have lower peak

    def test_unserved_energy_improvement(
        self, baseline_snapshots, gridmind_snapshots
    ):
        bl_metrics = calculate_all_metrics(baseline_snapshots)
        gm_metrics = calculate_all_metrics(gridmind_snapshots)
        assert gm_metrics.resilience.unserved_energy_kwh < bl_metrics.resilience.unserved_energy_kwh

    def test_critical_load_protection(
        self, baseline_snapshots, gridmind_snapshots
    ):
        bl_metrics = calculate_all_metrics(baseline_snapshots)
        gm_metrics = calculate_all_metrics(gridmind_snapshots)
        assert (
            gm_metrics.resilience.critical_load_protection_percent
            >= bl_metrics.resilience.critical_load_protection_percent
        )


# ══════════════════════════════════════════════════════════════════════════
#  EDGE CASES
# ══════════════════════════════════════════════════════════════════════════


class TestBaselineEdgeCases:
    def test_empty_comparison(self):
        """Comparing two empty datasets should produce all-zero metrics."""
        bl = calculate_all_metrics([])
        gm = calculate_all_metrics([])
        savings = calculate_cost_savings_percent(
            bl.economic.total_cost, gm.economic.total_cost
        )
        assert savings == 0.0

    def test_identical_runs(self):
        """When baseline and GridMind produce the same results, improvement is zero."""
        snaps = [_snap(timestep=i) for i in range(5)]
        bl = calculate_all_metrics(snaps)
        gm = calculate_all_metrics(snaps)
        savings = calculate_cost_savings_percent(
            bl.economic.total_cost, gm.economic.total_cost
        )
        assert savings == 0.0
        reduction = calculate_peak_reduction_percent(
            bl.grid.peak_demand_kw, gm.grid.peak_demand_kw
        )
        assert reduction == 0.0
