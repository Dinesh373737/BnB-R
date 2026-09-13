/**
 * Simulation Page
 *
 * Consumes:
 *   POST /api/simulation/initialize
 *   GET  /api/simulation/state
 *   GET  /api/simulation/last-result
 *   POST /api/simulation/step
 *   POST /api/simulation/run
 *   POST /api/simulation/scenarios/primary
 */

import { useCallback, useEffect, useState } from "react";
import {
  simulationApi,
  MicrogridState,
  SimulationStepResult,
  ScenarioActivationResponse,
  SimulationConfig,
} from "../../services/api";
import styles from "../shared.module.css";

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export default function SimulationPage() {
  const [state, setState] = useState<MicrogridState | null>(null);
  const [lastResult, setLastResult] = useState<SimulationStepResult | null>(null);
  const [history, setHistory] = useState<MicrogridState[]>([]);
  const [scenario, setScenario] = useState<ScenarioActivationResponse | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [stateData, resultData] = await Promise.all([
        simulationApi.state().catch((e: Error) => {
          if (String(e.message).includes("409")) return null;
          throw e;
        }),
        simulationApi.lastResult(),
      ]);
      setState(stateData);
      setLastResult(resultData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const initialize = useCallback(async () => {
    setBusy(true);
    setMessage(null);
    try {
      const config: SimulationConfig = {};
      const newState = await simulationApi.initialize(config);
      setState(newState);
      setHistory([]);
      setScenario(null);
      setLastResult(null);
      setMessage(`Simulation initialized at timestep ${newState.timestep}.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, []);

  const step = useCallback(async () => {
    setBusy(true);
    setMessage(null);
    try {
      const newState = await simulationApi.step();
      setState(newState);
      setHistory((h) => [...h, newState].slice(-13));
      const result = await simulationApi.lastResult();
      setLastResult(result);
      setMessage(`Timestep ${newState.timestep} completed.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, []);

  const runLoop = useCallback(async () => {
    setBusy(true);
    setMessage(null);
    try {
      const states = await simulationApi.run();
      setHistory(states);
      if (states.length > 0) {
        setState(states[states.length - 1]);
      }
      const result = await simulationApi.lastResult();
      setLastResult(result);
      setMessage(`Full loop complete — ${states.length} timesteps.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, []);

  const activateCrisis = useCallback(async () => {
    setBusy(true);
    setMessage(null);
    try {
      const response = await simulationApi.activatePrimaryScenario(
        state ? state.timestep + 1 : 1,
        5,
      );
      setScenario(response);
      setMessage(
        `Crisis scenario "${response.scenario}" scheduled (solar −50%, flexible demand +30%) from timestep ${response.start_timestep ?? "next"}.`,
      );
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [state]);

  if (loading && !state) {
    return (
      <section className={styles.page}>
        <div className={styles.loading}>
          <div className={styles.spinner} />
          <p>Loading simulation…</p>
        </div>
      </section>
    );
  }

  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1>Simulation Engine</h1>
          <p className={styles.subtitle}>
            Deterministic microgrid simulation — initialize, step through
            timesteps, and trigger crisis scenarios.
          </p>
        </div>
        <div className={styles.headerActions}>
          <button type="button" className={styles.button} onClick={initialize} disabled={busy}>
            Initialize
          </button>
          <button type="button" className={styles.button} onClick={step} disabled={busy}>
            Step
          </button>
          <button type="button" className={styles.button} onClick={runLoop} disabled={busy}>
            Run full loop
          </button>
          <button type="button" className={styles.primaryButton} onClick={activateCrisis} disabled={busy}>
            Activate crisis
          </button>
        </div>
      </header>

      {error && (
        <div className={styles.error} style={{ marginBottom: 20 }}>
          <h2>Simulation error</h2>
          <p>{error}</p>
          <button type="button" className={styles.primaryButton} onClick={initialize}>
            Initialize a new run
          </button>
        </div>
      )}

      {message && <p className={styles.reasoning} style={{ marginBottom: 16 }}>{message}</p>}

      {scenario && (
        <p className={styles.reasoning} style={{ marginBottom: 16 }}>
          Active crisis: <strong>{scenario.scenario}</strong> — starts at timestep{" "}
          {scenario.start_timestep ?? "next"}, duration {scenario.duration_steps ?? "∞"} steps.
        </p>
      )}

      {state ? (
        <div className={styles.grid}>
          {/* Core state */}
          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <h2>Current State</h2>
              <span className={`${styles.pill} ${styles.pillInfo}`}>
                t = {state.timestep}
              </span>
            </div>
            <dl className={styles.metrics}>
              <div className={styles.metric}>
                <dt>Total demand</dt>
                <dd className={styles.value}>{state.total_demand_kw.toFixed(0)} kW</dd>
              </div>
              <div className={styles.metric}>
                <dt>Total generation</dt>
                <dd className={styles.value}>{state.total_generation_kw.toFixed(0)} kW</dd>
              </div>
              <div className={styles.metric}>
                <dt>Renewable</dt>
                <dd className={`${styles.value} ${state.renewable_generation_kw >= 0 ? styles.positive : ""}`}>
                  {state.renewable_generation_kw.toFixed(0)} kW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Renewable %</dt>
                <dd className={styles.value}>{state.renewable_percentage.toFixed(1)}%</dd>
              </div>
              <div className={styles.metric}>
                <dt>Energy balance</dt>
                <dd className={`${styles.value} ${state.energy_balance_kw >= 0 ? styles.positive : styles.negative}`}>
                  {state.energy_balance_kw.toFixed(0)} kW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Grid dependency</dt>
                <dd className={styles.value}>{state.grid_dependency_pct.toFixed(1)}%</dd>
              </div>
            </dl>
          </div>

          {/* Resources */}
          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <h2>Resources</h2>
            </div>
            <dl className={styles.metrics}>
              <div className={styles.metric}>
                <dt>Solar</dt>
                <dd className={styles.value}>
                  {state.solar.current_output_kw.toFixed(0)} / {state.solar.capacity_kw.toFixed(0)} kW
                </dd>
                <dd className={styles.metricSub}>{state.solar.status}</dd>
              </div>
              <div className={styles.metric}>
                <dt>Wind</dt>
                <dd className={styles.value}>
                  {state.wind.current_output_kw.toFixed(0)} / {state.wind.capacity_kw.toFixed(0)} kW
                </dd>
                <dd className={styles.metricSub}>{state.wind.status}</dd>
              </div>
              <div className={styles.metric}>
                <dt>Battery SOC</dt>
                <dd className={styles.value}>{pct(state.battery.current_soc)}</dd>
                <dd className={styles.metricSub}>{state.battery.status}</dd>
              </div>
              <div className={styles.metric}>
                <dt>Battery power</dt>
                <dd className={`${styles.value} ${state.battery.current_power_kw >= 0 ? styles.positive : styles.negative}`}>
                  {state.battery.current_power_kw.toFixed(0)} kW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>EVs charging</dt>
                <dd className={styles.value}>
                  {state.ev.charging_count}/{state.ev.total_count}
                </dd>
              </div>
            </dl>
          </div>

          {/* Loads and grid */}
          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <h2>Loads & Grid</h2>
              <span
                className={`${styles.pill} ${
                  state.grid_connection.is_connected ? styles.pillOk : styles.pillErr
                }`}
              >
                {state.grid_connection.is_connected ? "grid connected" : "islanded"}
              </span>
            </div>
            <dl className={styles.metrics}>
              <div className={styles.metric}>
                <dt>Households</dt>
                <dd className={styles.value}>{state.households.total_demand_kw.toFixed(0)} kW</dd>
                <dd className={styles.metricSub}>
                  {state.households.count} homes, flex {state.households.flexible_demand_kw.toFixed(0)} kW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Industry</dt>
                <dd className={styles.value}>{state.industry.total_demand_kw.toFixed(0)} kW</dd>
                <dd className={styles.metricSub}>
                  flex {state.industry.flexible_demand_kw.toFixed(0)} kW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Critical facility</dt>
                <dd className={`${styles.value} ${state.critical_facility.is_protected ? styles.positive : styles.negative}`}>
                  {state.critical_facility.current_supply_kw.toFixed(0)} / {state.critical_facility.required_power_kw.toFixed(0)} kW
                </dd>
                <dd className={styles.metricSub}>
                  {state.critical_facility.is_protected ? "protected" : "at risk"}
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Grid import</dt>
                <dd className={styles.value}>{state.grid_connection.import_power_kw.toFixed(0)} kW</dd>
              </div>
              <div className={styles.metric}>
                <dt>Import price</dt>
                <dd className={styles.value}>
                  ₹{state.grid_connection.electricity_price_per_kwh.toFixed(2)}/kWh
                </dd>
              </div>
            </dl>
          </div>

          {/* Last step details */}
          {lastResult && (
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <h2>Last Step Detail</h2>
                {lastResult.active_scenario && (
                  <span className={`${styles.pill} ${styles.pillWarn}`}>
                    {lastResult.active_scenario}
                  </span>
                )}
              </div>
              <dl className={styles.metrics}>
                <div className={styles.metric}>
                  <dt>Requested</dt>
                  <dd className={styles.value}>{lastResult.requested_demand_kw.toFixed(0)} kW</dd>
                </div>
                <div className={styles.metric}>
                  <dt>Served</dt>
                  <dd className={`${styles.value} ${lastResult.unserved_load_kw > 0 ? styles.negative : styles.positive}`}>
                    {lastResult.served_demand_kw.toFixed(0)} kW
                  </dd>
                </div>
                <div className={styles.metric}>
                  <dt>Unserved</dt>
                  <dd className={`${styles.value} ${lastResult.unserved_load_kw > 0 ? styles.negative : ""}`}>
                    {lastResult.unserved_load_kw.toFixed(0)} kW
                  </dd>
                </div>
                <div className={styles.metric}>
                  <dt>Curtailment</dt>
                  <dd className={styles.value}>{lastResult.curtailed_generation_kw.toFixed(0)} kW</dd>
                </div>
              </dl>
            </div>
          )}

          {/* History table */}
          {history.length > 0 && (
            <div className={`${styles.card} ${styles.cardFull}`}>
              <div className={styles.cardHeader}>
                <h2>Timestep History</h2>
                <span className={styles.count}>{history.length} steps</span>
              </div>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>t</th>
                    <th>Demand (kW)</th>
                    <th>Generation (kW)</th>
                    <th>Balance (kW)</th>
                    <th>Battery SOC</th>
                    <th>Grid import (kW)</th>
                    <th>Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((s) => (
                    <tr key={s.timestep}>
                      <td>{s.timestep}</td>
                      <td>{s.total_demand_kw.toFixed(0)}</td>
                      <td>{s.total_generation_kw.toFixed(0)}</td>
                      <td className={s.energy_balance_kw >= 0 ? styles.positive : styles.negative}>
                        {s.energy_balance_kw.toFixed(0)}
                      </td>
                      <td>{pct(s.battery.current_soc)}</td>
                      <td>{s.grid_connection.import_power_kw.toFixed(0)}</td>
                      <td>{String(s.risk.risk_level).toUpperCase()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : (
        !error && (
          <div className={styles.error}>
            <h2>No active simulation</h2>
            <p>Initialize a run to start the deterministic microgrid simulation.</p>
            <button type="button" className={styles.primaryButton} onClick={initialize}>
              Initialize simulation
            </button>
          </div>
        )
      )}

      <footer className={styles.footer}>
        <button type="button" className={styles.button} onClick={refresh}>
          Refresh state
        </button>
        <p className={styles.note}>
          Each timestep is {60}s of simulated time. The crisis scenario cuts solar 50%
          and raises flexible demand 30%.
        </p>
      </footer>
    </section>
  );
}
