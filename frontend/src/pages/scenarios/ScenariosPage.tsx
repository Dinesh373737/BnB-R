/**
 * Scenarios Page
 *
 * Consumes:
 *   GET  /api/scenarios/            (list prebuilt crisis scenarios)
 *   POST /api/scenarios/run         (apply a scenario to a base state)
 *   GET  /api/simulation/state      (base state for scenario application)
 */

import { useCallback, useEffect, useState } from "react";
import {
  scenariosApi,
  simulationApi,
  ScenarioConfig,
  ScenarioRunResult,
  MicrogridState,
} from "../../services/api";
import styles from "../shared.module.css";

function formatMultiplier(label: string, value: number): string {
  if (value === 1.0) return "";
  if (value < 1) return `${label} −${Math.round((1 - value) * 100)}%`;
  return `${label} +${Math.round((value - 1) * 100)}%`;
}

export default function ScenariosPage() {
  const [scenarios, setScenarios] = useState<Record<string, ScenarioConfig>>({});
  const [simState, setSimState] = useState<MicrogridState | null>(null);
  const [result, setResult] = useState<ScenarioRunResult | null>(null);
  const [runningId, setRunningId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [scenarioData, stateData] = await Promise.all([
        scenariosApi.list(),
        simulationApi.state().catch(() => null),
      ]);
      setScenarios(scenarioData);
      setSimState(stateData);
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

  const runScenario = useCallback(
    async (scenarioId: string) => {
      setRunningId(scenarioId);
      setResult(null);
      try {
        // Base state: the live simulation state if present, else sensible defaults
        const baseState: Record<string, unknown> = simState
          ? {
              solar_generation: simState.solar.current_output_kw,
              wind_generation: simState.wind.current_output_kw,
              demand: simState.total_demand_kw,
              battery_soc: simState.battery.current_soc,
              grid_status: simState.grid_connection.is_connected
                ? "AVAILABLE"
                : "OFFLINE",
            }
          : {
              solar_generation: 350.0,
              wind_generation: 100.0,
              demand: 2250.0,
              battery_soc: 0.5,
              grid_status: "AVAILABLE",
            };

        const runResult = await scenariosApi.run(scenarioId, baseState);
        setResult(runResult);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setRunningId(null);
      }
    },
    [simState],
  );

  if (loading) {
    return (
      <section className={styles.page}>
        <div className={styles.loading}>
          <div className={styles.spinner} />
          <p>Loading scenarios…</p>
        </div>
      </section>
    );
  }

  if (error && Object.keys(scenarios).length === 0) {
    return (
      <section className={styles.page}>
        <div className={styles.error}>
          <h2>Unable to load scenarios</h2>
          <p>{error}</p>
          <button type="button" className={styles.primaryButton} onClick={refresh}>
            Retry
          </button>
        </div>
      </section>
    );
  }

  const scenarioList = Object.values(scenarios);

  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1>Scenarios</h1>
          <p className={styles.subtitle}>
            Pre-built crisis scenarios — apply grid outages, extreme weather,
            and demand surges to the current microgrid state.
          </p>
        </div>
      </header>

      {error && (
        <div className={styles.error} style={{ marginBottom: 20 }}>
          <p>{error}</p>
        </div>
      )}

      <div className={styles.grid}>
        {scenarioList.map((scenario) => {
          const effects = [
            formatMultiplier("Solar", scenario.solar_multiplier),
            formatMultiplier("Wind", scenario.wind_multiplier),
            formatMultiplier("Demand", scenario.demand_multiplier),
            scenario.grid_available === false ? "Grid OFFLINE" : "",
          ].filter(Boolean);

          return (
            <div key={scenario.id} className={styles.card}>
              <div className={styles.cardHeader}>
                <h2>{scenario.name}</h2>
                <span className={`${styles.pill} ${styles.pillInfo}`}>
                  {scenario.scenario_type}
                </span>
              </div>
              <p className={styles.itemSub}>{scenario.description}</p>
              {effects.length > 0 && (
                <div className={styles.itemMeta} style={{ marginTop: 12 }}>
                  {effects.map((effect) => (
                    <span key={effect} className={`${styles.pill} ${styles.pillWarn}`}>
                      {effect}
                    </span>
                  ))}
                </div>
              )}
              <div style={{ marginTop: 16 }}>
                <button
                  type="button"
                  className={styles.primaryButton}
                  onClick={() => runScenario(scenario.id)}
                  disabled={runningId !== null}
                >
                  {runningId === scenario.id ? "Applying…" : "Apply scenario"}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {result && (
        <div className={`${styles.card} ${styles.cardFull}`} style={{ marginTop: 24 }}>
          <div className={styles.cardHeader}>
            <h2>Applied: {result.scenario_name}</h2>
            <span className={`${styles.pill} ${styles.pillOk}`}>{result.scenario_id}</span>
          </div>
          {result.logs.length > 0 ? (
            <ul className={styles.logList}>
              {result.logs.map((log, i) => (
                <li key={i} className={styles.logItem}>
                  {log}
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.empty}>
              No state fields matched this scenario's modifiers — the current
              simulation state already reflects it.
            </p>
          )}
        </div>
      )}

      <footer className={styles.footer}>
        <button type="button" className={styles.button} onClick={refresh}>
          Refresh scenarios
        </button>
        <p className={styles.note}>
          Scenarios apply multipliers to a snapshot of the current simulation
          state. Use the Simulation page to run the grid under the modified
          conditions.
        </p>
      </footer>
    </section>
  );
}
