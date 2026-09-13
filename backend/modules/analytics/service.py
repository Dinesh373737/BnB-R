"""Analytics module — Service layer for analytics orchestration.

Responsible for:
    1. Loading GridMind simulation results (from DB or in-memory).
    2. Calculating GridMind metrics.
    3. Running the baseline simulation (same scenario / config).
    4. Calculating baseline metrics.
    5. Producing the comparison with improvement deltas.
    6. Persisting analytics results to the ``analytics_results`` table.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from backend.common.logger import get_module_logger
from backend.common.models.analytics import AnalyticsResultRecord
from backend.common.models.microgrid import MicrogridStateDBRecord
from backend.common.models.market import TradeRecord
from backend.common.models.simulation import SimulationRunRecord
from backend.common.schemas.enums import AnalyticsMode, MetricCategory
from backend.modules.analytics.baseline import BaselineController
from backend.modules.analytics.metrics import (
    calculate_all_metrics,
    calculate_cost_savings_percent,
    calculate_peak_reduction_percent,
)
from backend.modules.analytics.schemas import (
    ComparisonResult,
    FullMetricSet,
    ImprovementMetrics,
    TimestepSnapshot,
    TradeData,
    snapshot_from_db_record,
    snapshot_from_step_result,
)

log = get_module_logger("analytics.service")


class AnalyticsService:
    """Orchestrates metric calculation and baseline comparison."""

    def __init__(self, db: Session):
        self.db = db
        self.baseline_controller = BaselineController()

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    def get_analytics(
        self, simulation_run_id: int
    ) -> FullMetricSet:
        """Load or calculate GridMind metrics for a simulation run."""
        snapshots = self._load_gridmind_snapshots(simulation_run_id)
        trades = self._load_trades(simulation_run_id)
        return calculate_all_metrics(snapshots, trades)

    def get_comparison(
        self,
        simulation_run_id: int,
        *,
        num_baseline_steps: int = 13,
    ) -> ComparisonResult:
        """Produce a full baseline-vs-GridMind comparison.

        Flow:
            1. Load GridMind simulation data from the database.
            2. Calculate GridMind metrics.
            3. Reconstruct the same config/scenario and run the baseline.
            4. Calculate baseline metrics.
            5. Compute improvement deltas.
            6. Persist results.
            7. Return the comparison.
        """
        # --- GridMind metrics ---
        gm_snapshots = self._load_gridmind_snapshots(simulation_run_id)
        gm_trades = self._load_trades(simulation_run_id)
        gm_metrics = calculate_all_metrics(gm_snapshots, gm_trades)

        # --- Baseline metrics ---
        config, scenario = self._reconstruct_simulation_params(simulation_run_id)
        baseline_snapshots = self.baseline_controller.run(
            config, scenario, num_steps=num_baseline_steps
        )
        baseline_metrics = calculate_all_metrics(baseline_snapshots)

        # --- Improvement ---
        improvement = self._calculate_improvement(baseline_metrics, gm_metrics)

        # Populate comparison-only fields
        gm_metrics.economic.cost_savings_percent = improvement.cost_savings_percent
        gm_metrics.grid.peak_reduction_percent = improvement.peak_reduction_percent

        # Determine scenario name
        sim_record = self._load_simulation_run(simulation_run_id)
        scenario_name = sim_record.scenario if sim_record else None

        comparison = ComparisonResult(
            simulation_run_id=simulation_run_id,
            scenario=scenario_name,
            baseline=baseline_metrics,
            gridmind=gm_metrics,
            improvement=improvement,
        )

        # Persist
        self._persist_metrics(
            simulation_run_id, gm_metrics, AnalyticsMode.GRIDMIND
        )
        self._persist_metrics(
            simulation_run_id, baseline_metrics, AnalyticsMode.BASELINE
        )

        log.info(
            "Analytics comparison completed for simulation_run_id=%s",
            simulation_run_id,
        )
        return comparison

    def calculate_and_persist(
        self, simulation_run_id: int
    ) -> FullMetricSet:
        """Calculate GridMind metrics and persist them.

        Convenience wrapper for routes that only want GridMind analytics
        (no baseline comparison).
        """
        metrics = self.get_analytics(simulation_run_id)
        self._persist_metrics(
            simulation_run_id, metrics, AnalyticsMode.GRIDMIND
        )
        return metrics

    # ------------------------------------------------------------------
    #  Data loading (from database)
    # ------------------------------------------------------------------

    def _load_simulation_run(
        self, simulation_run_id: int
    ) -> SimulationRunRecord | None:
        return (
            self.db.query(SimulationRunRecord)
            .filter(SimulationRunRecord.id == simulation_run_id)
            .first()
        )

    def _load_gridmind_snapshots(
        self, simulation_run_id: int
    ) -> list[TimestepSnapshot]:
        """Load microgrid state history from the DB and convert to snapshots."""
        records = (
            self.db.query(MicrogridStateDBRecord)
            .filter(
                MicrogridStateDBRecord.simulation_run_id == simulation_run_id
            )
            .order_by(MicrogridStateDBRecord.timestep)
            .all()
        )
        sim = self._load_simulation_run(simulation_run_id)
        ts_seconds = sim.timestep_seconds if sim else 60

        return [
            snapshot_from_db_record(r, timestep_seconds=ts_seconds)
            for r in records
        ]

    def _load_trades(
        self, simulation_run_id: int
    ) -> list[TradeData]:
        """Load P2P trade records and convert to lightweight data objects."""
        records = (
            self.db.query(TradeRecord)
            .filter(TradeRecord.simulation_run_id == simulation_run_id)
            .all()
        )
        return [
            TradeData(
                energy_kwh=r.energy_kwh,
                price_per_kwh=r.price_per_kwh,
                total_cost=r.total_cost,
            )
            for r in records
        ]

    def _reconstruct_simulation_params(self, simulation_run_id: int):
        """Reconstruct ``SimulationConfig`` and ``CrisisScenario`` for the
        baseline to face the same scenario.

        Falls back to defaults if the simulation record is missing.
        """
        from backend.modules.simulation.schemas import (
            SimulationConfig,
            CrisisScenario,
            build_scenario,
        )
        from backend.common.schemas.enums import ScenarioType

        sim = self._load_simulation_run(simulation_run_id)
        config = SimulationConfig()
        scenario = None

        if sim and sim.parameters_json:
            try:
                params = json.loads(sim.parameters_json)
                config = SimulationConfig(**params)
            except (json.JSONDecodeError, Exception) as exc:
                log.warning(
                    "Could not parse simulation parameters: %s", exc
                )

        if sim and sim.scenario:
            try:
                scenario_type = ScenarioType(sim.scenario)
                scenario = build_scenario(scenario_type)
            except (ValueError, Exception) as exc:
                log.warning(
                    "Could not reconstruct scenario '%s': %s",
                    sim.scenario,
                    exc,
                )

        return config, scenario

    # ------------------------------------------------------------------
    #  Comparison logic
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_improvement(
        baseline: FullMetricSet,
        gridmind: FullMetricSet,
    ) -> ImprovementMetrics:
        """Compute improvement deltas between baseline and GridMind."""
        return ImprovementMetrics(
            cost_savings_percent=calculate_cost_savings_percent(
                baseline.economic.total_cost,
                gridmind.economic.total_cost,
            ),
            peak_reduction_percent=calculate_peak_reduction_percent(
                baseline.grid.peak_demand_kw,
                gridmind.grid.peak_demand_kw,
            ),
            renewable_improvement_percent=_safe_improvement(
                baseline.renewable.renewable_utilization_percent,
                gridmind.renewable.renewable_utilization_percent,
            ),
            unserved_energy_reduction_percent=_safe_improvement(
                baseline.resilience.unserved_energy_kwh,
                gridmind.resilience.unserved_energy_kwh,
            ),
            critical_load_improvement_percent=_safe_improvement_higher_is_better(
                baseline.resilience.critical_load_protection_percent,
                gridmind.resilience.critical_load_protection_percent,
            ),
            recovery_time_improvement_percent=_safe_improvement(
                baseline.resilience.recovery_time_minutes,
                gridmind.resilience.recovery_time_minutes,
            ),
        )

    # ------------------------------------------------------------------
    #  Persistence
    # ------------------------------------------------------------------

    def _persist_metrics(
        self,
        simulation_run_id: int,
        metrics: FullMetricSet,
        mode: AnalyticsMode,
    ) -> None:
        """Write metric records to the ``analytics_results`` table."""
        is_baseline = mode == AnalyticsMode.BASELINE

        # Delete previous records for this run + mode to avoid duplicates
        self.db.query(AnalyticsResultRecord).filter(
            AnalyticsResultRecord.simulation_run_id == simulation_run_id,
            AnalyticsResultRecord.mode == mode.value,
        ).delete()

        rows: list[AnalyticsResultRecord] = []

        # Economic
        rows.extend(
            self._make_records(
                simulation_run_id,
                MetricCategory.ECONOMIC,
                is_baseline,
                mode,
                {
                    "total_cost": (metrics.economic.total_cost, "INR"),
                    "average_cost_per_kwh": (
                        metrics.economic.average_cost_per_kwh,
                        "INR/kWh",
                    ),
                    "cost_savings_percent": (
                        metrics.economic.cost_savings_percent,
                        "%",
                    ),
                },
            )
        )

        # Grid
        rows.extend(
            self._make_records(
                simulation_run_id,
                MetricCategory.GRID,
                is_baseline,
                mode,
                {
                    "peak_demand_kw": (metrics.grid.peak_demand_kw, "kW"),
                    "peak_reduction_percent": (
                        metrics.grid.peak_reduction_percent,
                        "%",
                    ),
                },
            )
        )

        # Renewable
        rows.extend(
            self._make_records(
                simulation_run_id,
                MetricCategory.RENEWABLE,
                is_baseline,
                mode,
                {
                    "renewable_utilization_percent": (
                        metrics.renewable.renewable_utilization_percent,
                        "%",
                    ),
                    "solar_utilization_percent": (
                        metrics.renewable.solar_utilization_percent,
                        "%",
                    ),
                    "renewable_curtailment_kwh": (
                        metrics.renewable.renewable_curtailment_kwh,
                        "kWh",
                    ),
                },
            )
        )

        # Storage
        rows.extend(
            self._make_records(
                simulation_run_id,
                MetricCategory.STORAGE,
                is_baseline,
                mode,
                {
                    "battery_utilization_percent": (
                        metrics.storage.battery_utilization_percent,
                        "%",
                    ),
                    "battery_reserve_percent": (
                        metrics.storage.battery_reserve_percent,
                        "%",
                    ),
                },
            )
        )

        # Resilience
        rows.extend(
            self._make_records(
                simulation_run_id,
                MetricCategory.RESILIENCE,
                is_baseline,
                mode,
                {
                    "unserved_energy_kwh": (
                        metrics.resilience.unserved_energy_kwh,
                        "kWh",
                    ),
                    "critical_load_protection_percent": (
                        metrics.resilience.critical_load_protection_percent,
                        "%",
                    ),
                    "recovery_time_minutes": (
                        metrics.resilience.recovery_time_minutes,
                        "min",
                    ),
                },
            )
        )

        # Market
        rows.extend(
            self._make_records(
                simulation_run_id,
                MetricCategory.MARKET,
                is_baseline,
                mode,
                {
                    "total_energy_traded_kwh": (
                        metrics.market.total_energy_traded_kwh,
                        "kWh",
                    ),
                    "transaction_count": (
                        float(metrics.market.transaction_count),
                        "count",
                    ),
                    "average_trading_price": (
                        metrics.market.average_trading_price,
                        "INR/kWh",
                    ),
                },
            )
        )

        self.db.add_all(rows)
        self.db.flush()
        log.debug(
            "Persisted %d analytics rows (run=%s, mode=%s)",
            len(rows),
            simulation_run_id,
            mode.value,
        )

    @staticmethod
    def _make_records(
        simulation_run_id: int,
        category: MetricCategory,
        is_baseline: bool,
        mode: AnalyticsMode,
        metrics_map: dict[str, tuple[float, str]],
    ) -> list[AnalyticsResultRecord]:
        return [
            AnalyticsResultRecord(
                simulation_run_id=simulation_run_id,
                metric_category=category.value,
                metric_name=name,
                metric_value=value,
                metric_unit=unit,
                is_baseline=is_baseline,
                mode=mode.value,
            )
            for name, (value, unit) in metrics_map.items()
        ]


# ══════════════════════════════════════════════════════════════════════════
#  Module-private helpers
# ══════════════════════════════════════════════════════════════════════════


def _safe_improvement(baseline_val: float, gridmind_val: float) -> float:
    """% reduction: (baseline − gridmind) / baseline × 100.

    Used for metrics where *lower is better* (cost, unserved energy, etc.).
    """
    if baseline_val <= 0:
        return 0.0
    return round((baseline_val - gridmind_val) / baseline_val * 100.0, 2)


def _safe_improvement_higher_is_better(
    baseline_val: float, gridmind_val: float
) -> float:
    """% improvement: (gridmind − baseline) / baseline × 100.

    Used for metrics where *higher is better* (protection %, utilisation %).
    """
    if baseline_val <= 0:
        if gridmind_val > 0:
            return 100.0
        return 0.0
    return round((gridmind_val - baseline_val) / baseline_val * 100.0, 2)
