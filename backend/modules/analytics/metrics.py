"""Analytics module — Pure metric calculation functions.

All functions in this module are **pure**: they accept lists of
``TimestepSnapshot`` and/or ``TradeData`` and return numeric results.  They
have no database, API, or side-effect dependencies.

Edge cases handled:
  - zero demand / zero generation → 0% utilisation (not division-by-zero)
  - empty snapshot list → zeroed metrics
  - missing trade data → zeroed market metrics
"""

from __future__ import annotations

from backend.modules.analytics.schemas import (
    EconomicMetrics,
    FullMetricSet,
    GridMetrics,
    MarketMetrics,
    RenewableMetrics,
    ResilienceMetrics,
    StorageMetrics,
    TimestepSnapshot,
    TradeData,
)


# ══════════════════════════════════════════════════════════════════════════
#  ECONOMIC METRICS
# ══════════════════════════════════════════════════════════════════════════


def calculate_total_cost(snapshots: list[TimestepSnapshot]) -> float:
    """Total energy cost = Σ(grid_import_kw × price × timestep_hours)."""
    if not snapshots:
        return 0.0
    total = 0.0
    for s in snapshots:
        hours = s.timestep_seconds / 3600.0
        total += s.grid_import_kw * s.electricity_price_per_kwh * hours
    return round(total, 4)


def calculate_average_cost(snapshots: list[TimestepSnapshot]) -> float:
    """Average cost per kWh of energy consumed from the grid."""
    if not snapshots:
        return 0.0
    total_cost = calculate_total_cost(snapshots)
    total_imported_kwh = sum(
        s.grid_import_kw * (s.timestep_seconds / 3600.0) for s in snapshots
    )
    if total_imported_kwh <= 0:
        return 0.0
    return round(total_cost / total_imported_kwh, 4)


def calculate_cost_savings_percent(
    baseline_cost: float, gridmind_cost: float
) -> float:
    """Percentage cost reduction: (baseline − gridmind) / baseline × 100."""
    if baseline_cost <= 0:
        return 0.0
    return round((baseline_cost - gridmind_cost) / baseline_cost * 100.0, 2)


# ══════════════════════════════════════════════════════════════════════════
#  GRID METRICS
# ══════════════════════════════════════════════════════════════════════════


def calculate_peak_demand(snapshots: list[TimestepSnapshot]) -> float:
    """Peak demand across all timesteps (kW)."""
    if not snapshots:
        return 0.0
    return max(s.total_demand_kw for s in snapshots)


def calculate_peak_reduction_percent(
    baseline_peak: float, gridmind_peak: float
) -> float:
    """Percentage peak reduction: (baseline − gridmind) / baseline × 100."""
    if baseline_peak <= 0:
        return 0.0
    return round((baseline_peak - gridmind_peak) / baseline_peak * 100.0, 2)


# ══════════════════════════════════════════════════════════════════════════
#  RENEWABLE METRICS
# ══════════════════════════════════════════════════════════════════════════


def calculate_renewable_utilization(snapshots: list[TimestepSnapshot]) -> float:
    """Renewable utilisation = Σ renewable_gen / Σ total_demand × 100."""
    if not snapshots:
        return 0.0
    total_renewable = sum(s.renewable_generation_kw for s in snapshots)
    total_demand = sum(s.total_demand_kw for s in snapshots)
    if total_demand <= 0:
        return 0.0
    return round(min(total_renewable / total_demand * 100.0, 100.0), 2)


def calculate_solar_utilization(snapshots: list[TimestepSnapshot]) -> float:
    """Solar utilisation = Σ solar_output / Σ solar_capacity × 100."""
    if not snapshots:
        return 0.0
    total_output = sum(s.solar_output_kw for s in snapshots)
    total_capacity = sum(s.solar_capacity_kw for s in snapshots)
    if total_capacity <= 0:
        return 0.0
    return round(min(total_output / total_capacity * 100.0, 100.0), 2)


def calculate_renewable_curtailment(snapshots: list[TimestepSnapshot]) -> float:
    """Total curtailed renewable energy (kWh)."""
    if not snapshots:
        return 0.0
    total = sum(
        s.curtailed_generation_kw * (s.timestep_seconds / 3600.0) for s in snapshots
    )
    return round(total, 4)


# ══════════════════════════════════════════════════════════════════════════
#  STORAGE METRICS
# ══════════════════════════════════════════════════════════════════════════


def calculate_battery_utilization(snapshots: list[TimestepSnapshot]) -> float:
    """Battery utilisation proxy: % of timesteps with non-zero battery power.

    A more sophisticated cycle-counting metric can be substituted later.
    """
    if not snapshots:
        return 0.0
    active = sum(1 for s in snapshots if abs(s.battery_power_kw) > 0.01)
    return round(active / len(snapshots) * 100.0, 2)


def calculate_battery_reserve(snapshots: list[TimestepSnapshot]) -> float:
    """Average battery SOC across all timesteps (%)."""
    if not snapshots:
        return 0.0
    avg_soc = sum(s.battery_soc for s in snapshots) / len(snapshots)
    return round(avg_soc * 100.0, 2)


# ══════════════════════════════════════════════════════════════════════════
#  RESILIENCE METRICS
# ══════════════════════════════════════════════════════════════════════════


def calculate_unserved_energy(snapshots: list[TimestepSnapshot]) -> float:
    """Total unserved energy across all timesteps (kWh)."""
    if not snapshots:
        return 0.0
    total = sum(
        s.unserved_load_kw * (s.timestep_seconds / 3600.0) for s in snapshots
    )
    return round(total, 4)


def calculate_critical_load_protection(
    snapshots: list[TimestepSnapshot],
) -> float:
    """% of timesteps where critical load is fully protected."""
    if not snapshots:
        return 0.0
    protected = sum(
        1
        for s in snapshots
        if s.critical_load_status == "protected"
    )
    return round(protected / len(snapshots) * 100.0, 2)


def calculate_recovery_time(
    snapshots: list[TimestepSnapshot],
) -> float:
    """Recovery time in minutes: elapsed time from crisis onset to stability.

    Crisis onset is detected by a risk level of ``high`` or ``critical``.
    Recovery is when risk drops back to ``low`` or ``medium``.  If the system
    never recovers within the simulation window, the remaining timesteps are
    counted.  If no crisis occurs, recovery time is zero.
    """
    if not snapshots:
        return 0.0

    crisis_levels = {"high", "critical"}
    sorted_snaps = sorted(snapshots, key=lambda s: s.timestep)

    crisis_start_ts: int | None = None
    recovery_ts: int | None = None

    for s in sorted_snaps:
        if crisis_start_ts is None:
            if s.risk_level in crisis_levels:
                crisis_start_ts = s.timestep
        else:
            if s.risk_level not in crisis_levels:
                recovery_ts = s.timestep
                break

    if crisis_start_ts is None:
        return 0.0

    if recovery_ts is None:
        # Never recovered within the window
        recovery_ts = sorted_snaps[-1].timestep

    # Determine timestep_seconds from the first snapshot
    ts_seconds = sorted_snaps[0].timestep_seconds if sorted_snaps else 60
    elapsed_steps = recovery_ts - crisis_start_ts
    return round(elapsed_steps * ts_seconds / 60.0, 2)


# ══════════════════════════════════════════════════════════════════════════
#  MARKET METRICS
# ══════════════════════════════════════════════════════════════════════════


def calculate_total_energy_traded(trades: list[TradeData]) -> float:
    """Total energy traded via P2P market (kWh)."""
    if not trades:
        return 0.0
    return round(sum(t.energy_kwh for t in trades), 4)


def calculate_transaction_count(trades: list[TradeData]) -> int:
    """Number of completed P2P trades."""
    return len(trades)


def calculate_average_trading_price(trades: list[TradeData]) -> float:
    """Volume-weighted average trading price (INR/kWh)."""
    if not trades:
        return 0.0
    total_energy = sum(t.energy_kwh for t in trades)
    if total_energy <= 0:
        return 0.0
    total_revenue = sum(t.energy_kwh * t.price_per_kwh for t in trades)
    return round(total_revenue / total_energy, 4)


# ══════════════════════════════════════════════════════════════════════════
#  AGGREGATE: calculate all metrics in one pass
# ══════════════════════════════════════════════════════════════════════════


def calculate_all_metrics(
    snapshots: list[TimestepSnapshot],
    trades: list[TradeData] | None = None,
) -> FullMetricSet:
    """Calculate and return every metric category from the given data."""
    trades = trades or []
    return FullMetricSet(
        economic=EconomicMetrics(
            total_cost=calculate_total_cost(snapshots),
            average_cost_per_kwh=calculate_average_cost(snapshots),
        ),
        grid=GridMetrics(
            peak_demand_kw=calculate_peak_demand(snapshots),
        ),
        renewable=RenewableMetrics(
            renewable_utilization_percent=calculate_renewable_utilization(snapshots),
            solar_utilization_percent=calculate_solar_utilization(snapshots),
            renewable_curtailment_kwh=calculate_renewable_curtailment(snapshots),
        ),
        storage=StorageMetrics(
            battery_utilization_percent=calculate_battery_utilization(snapshots),
            battery_reserve_percent=calculate_battery_reserve(snapshots),
        ),
        resilience=ResilienceMetrics(
            unserved_energy_kwh=calculate_unserved_energy(snapshots),
            critical_load_protection_percent=calculate_critical_load_protection(
                snapshots,
            ),
            recovery_time_minutes=calculate_recovery_time(snapshots),
        ),
        market=MarketMetrics(
            total_energy_traded_kwh=calculate_total_energy_traded(trades),
            transaction_count=calculate_transaction_count(trades),
            average_trading_price=calculate_average_trading_price(trades),
        ),
    )
