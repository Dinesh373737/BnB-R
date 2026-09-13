/**
 * Analytics Page
 *
 * Consumes:
 *   GET  /api/analytics/{runId}
 *   GET  /api/analytics/{runId}/comparison
 *   POST /api/analytics/{runId}/calculate
 */

import { useCallback, useEffect, useState } from "react";
import {
  analyticsApi,
  AnalyticsResponse,
  ComparisonResponse,
} from "../../services/api";
import styles from "../shared.module.css";

function fmt(value: number | undefined | null, digits = 1): string {
  if (value === undefined || value === null) return "—";
  return value.toFixed(digits);
}

export default function AnalyticsPage() {
  const [runId, setRunId] = useState<number>(1);
  const [metrics, setMetrics] = useState<AnalyticsResponse | null>(null);
  const [comparison, setComparison] = useState<ComparisonResponse | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadAnalytics = useCallback(async (id: number) => {
    setLoading(true);
    setError(null);
    try {
      const [metricsData, comparisonData] = await Promise.all([
        analyticsApi.get(id),
        analyticsApi.comparison(id).catch(() => null),
      ]);
      setMetrics(metricsData);
      setComparison(comparisonData);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setMetrics(null);
      setComparison(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { latest_run_id } = await analyticsApi.latestRun();
        if (!cancelled && latest_run_id) {
          setRunId(latest_run_id);
          await loadAnalytics(latest_run_id);
        } else if (!cancelled) {
          setLoading(false);
        }
      } catch {
        if (!cancelled) {
          loadAnalytics(runId);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const calculate = useCallback(async () => {
    setBusy(true);
    setMessage(null);
    try {
      const result = await analyticsApi.calculate(runId);
      setMessage(result.message);
      await loadAnalytics(runId);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [runId, loadAnalytics]);

  const m = metrics?.metrics;

  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1>Analytics</h1>
          <p className={styles.subtitle}>
            GridMind vs baseline performance — economics, grid, renewables,
            storage, resilience, and market metrics per simulation run.
          </p>
        </div>
        <div className={styles.headerActions}>
          <div className={styles.field}>
            <label className={styles.label} htmlFor="run-id">Simulation run ID</label>
            <input
              id="run-id"
              className={styles.input}
              type="number"
              min="1"
              value={runId}
              onChange={(e) => setRunId(Number(e.target.value) || 1)}
              style={{ width: 120 }}
            />
          </div>
          <button
            type="button"
            className={styles.button}
            onClick={() => loadAnalytics(runId)}
            disabled={loading || busy}
          >
            {loading ? "Loading…" : "Load"}
          </button>
          <button
            type="button"
            className={styles.primaryButton}
            onClick={calculate}
            disabled={loading || busy}
          >
            Calculate &amp; persist
          </button>
        </div>
      </header>

      {error && (
        <div className={styles.error} style={{ marginBottom: 20 }}>
          <h2>Analytics unavailable</h2>
          <p>{error}</p>
          <p className={styles.note}>
            Tip: initialize and run a simulation first (Simulation page), then
            calculate analytics for that run ID.
          </p>
        </div>
      )}

      {message && <p className={styles.reasoning} style={{ marginBottom: 16 }}>{message}</p>}

      {m && (
        <div className={styles.grid}>
          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <h2>Economic</h2>
            </div>
            <dl className={styles.metrics}>
              <div className={styles.metric}>
                <dt>Total cost</dt>
                <dd className={styles.value}>₹{fmt(m.economic.total_cost, 0)}</dd>
              </div>
              <div className={styles.metric}>
                <dt>Avg ₹/kWh</dt>
                <dd className={styles.value}>{fmt(m.economic.average_cost_per_kwh, 2)}</dd>
              </div>
              <div className={styles.metric}>
                <dt>Savings vs baseline</dt>
                <dd className={`${styles.value} ${m.economic.cost_savings_percent >= 0 ? styles.positive : styles.negative}`}>
                  {fmt(m.economic.cost_savings_percent)}%
                </dd>
              </div>
            </dl>
          </div>

          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <h2>Grid &amp; Renewables</h2>
            </div>
            <dl className={styles.metrics}>
              <div className={styles.metric}>
                <dt>Peak demand</dt>
                <dd className={styles.value}>{fmt(m.grid.peak_demand_kw, 0)} kW</dd>
              </div>
              <div className={styles.metric}>
                <dt>Peak reduction</dt>
                <dd className={`${styles.value} ${m.grid.peak_reduction_percent >= 0 ? styles.positive : styles.negative}`}>
                  {fmt(m.grid.peak_reduction_percent)}%
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Renewable util.</dt>
                <dd className={styles.value}>{fmt(m.renewable.renewable_utilization_percent)}%</dd>
              </div>
              <div className={styles.metric}>
                <dt>Solar util.</dt>
                <dd className={styles.value}>{fmt(m.renewable.solar_utilization_percent)}%</dd>
              </div>
              <div className={styles.metric}>
                <dt>Curtailment</dt>
                <dd className={styles.value}>{fmt(m.renewable.renewable_curtailment_kwh, 1)} kWh</dd>
              </div>
            </dl>
          </div>

          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <h2>Storage &amp; Resilience</h2>
            </div>
            <dl className={styles.metrics}>
              <div className={styles.metric}>
                <dt>Battery util.</dt>
                <dd className={styles.value}>{fmt(m.storage.battery_utilization_percent)}%</dd>
              </div>
              <div className={styles.metric}>
                <dt>Battery reserve</dt>
                <dd className={styles.value}>{fmt(m.storage.battery_reserve_percent)}%</dd>
              </div>
              <div className={styles.metric}>
                <dt>Unserved energy</dt>
                <dd className={`${styles.value} ${m.resilience.unserved_energy_kwh > 0 ? styles.negative : styles.positive}`}>
                  {fmt(m.resilience.unserved_energy_kwh, 1)} kWh
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Critical protection</dt>
                <dd className={styles.value}>{fmt(m.resilience.critical_load_protection_percent)}%</dd>
              </div>
              <div className={styles.metric}>
                <dt>Recovery time</dt>
                <dd className={styles.value}>{fmt(m.resilience.recovery_time_minutes, 0)} min</dd>
              </div>
            </dl>
          </div>

          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <h2>Market</h2>
            </div>
            <dl className={styles.metrics}>
              <div className={styles.metric}>
                <dt>Energy traded</dt>
                <dd className={styles.value}>{fmt(m.market.total_energy_traded_kwh, 1)} kWh</dd>
              </div>
              <div className={styles.metric}>
                <dt>Transactions</dt>
                <dd className={styles.value}>{m.market.transaction_count}</dd>
              </div>
              <div className={styles.metric}>
                <dt>Avg trade price</dt>
                <dd className={styles.value}>₹{fmt(m.market.average_trading_price, 2)}</dd>
              </div>
            </dl>
          </div>

          {comparison?.comparison && (
            <div className={`${styles.card} ${styles.cardFull}`}>
              <div className={styles.cardHeader}>
                <h2>Baseline vs GridMind</h2>
                <span className={styles.count}>
                  run #{comparison.comparison.simulation_run_id ?? runId}
                </span>
              </div>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th>Baseline</th>
                    <th>GridMind</th>
                    <th>Improvement</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Total cost (₹)</td>
                    <td>{fmt(comparison.comparison.baseline.economic.total_cost, 0)}</td>
                    <td>{fmt(comparison.comparison.gridmind.economic.total_cost, 0)}</td>
                    <td className={comparison.comparison.improvement.cost_savings_percent >= 0 ? styles.improvement : styles.improvementBad}>
                      {fmt(comparison.comparison.improvement.cost_savings_percent)}% savings
                    </td>
                  </tr>
                  <tr>
                    <td>Peak demand (kW)</td>
                    <td>{fmt(comparison.comparison.baseline.grid.peak_demand_kw, 0)}</td>
                    <td>{fmt(comparison.comparison.gridmind.grid.peak_demand_kw, 0)}</td>
                    <td className={comparison.comparison.improvement.peak_reduction_percent >= 0 ? styles.improvement : styles.improvementBad}>
                      {fmt(comparison.comparison.improvement.peak_reduction_percent)}% reduction
                    </td>
                  </tr>
                  <tr>
                    <td>Renewable utilization (%)</td>
                    <td>{fmt(comparison.comparison.baseline.renewable.renewable_utilization_percent)}</td>
                    <td>{fmt(comparison.comparison.gridmind.renewable.renewable_utilization_percent)}</td>
                    <td className={comparison.comparison.improvement.renewable_improvement_percent >= 0 ? styles.improvement : styles.improvementBad}>
                      {fmt(comparison.comparison.improvement.renewable_improvement_percent)}%
                    </td>
                  </tr>
                  <tr>
                    <td>Unserved energy (kWh)</td>
                    <td>{fmt(comparison.comparison.baseline.resilience.unserved_energy_kwh, 1)}</td>
                    <td>{fmt(comparison.comparison.gridmind.resilience.unserved_energy_kwh, 1)}</td>
                    <td className={comparison.comparison.improvement.unserved_energy_reduction_percent >= 0 ? styles.improvement : styles.improvementBad}>
                      {fmt(comparison.comparison.improvement.unserved_energy_reduction_percent)}% less
                    </td>
                  </tr>
                  <tr>
                    <td>Critical load protection (%)</td>
                    <td>{fmt(comparison.comparison.baseline.resilience.critical_load_protection_percent)}</td>
                    <td>{fmt(comparison.comparison.gridmind.resilience.critical_load_protection_percent)}</td>
                    <td className={comparison.comparison.improvement.critical_load_improvement_percent >= 0 ? styles.improvement : styles.improvementBad}>
                      {fmt(comparison.comparison.improvement.critical_load_improvement_percent)}%
                    </td>
                  </tr>
                  <tr>
                    <td>Recovery time (min)</td>
                    <td>{fmt(comparison.comparison.baseline.resilience.recovery_time_minutes, 0)}</td>
                    <td>{fmt(comparison.comparison.gridmind.resilience.recovery_time_minutes, 0)}</td>
                    <td className={comparison.comparison.improvement.recovery_time_improvement_percent >= 0 ? styles.improvement : styles.improvementBad}>
                      {fmt(comparison.comparison.improvement.recovery_time_improvement_percent)}% faster
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <footer className={styles.footer}>
        <button
          type="button"
          className={styles.button}
          onClick={() => loadAnalytics(runId)}
          disabled={loading || busy}
        >
          Refresh analytics
        </button>
        <p className={styles.note}>
          Metrics are computed from persisted simulation runs. Run a simulation
          and use "Calculate &amp; persist" to store results.
        </p>
      </footer>
    </section>
  );
}
