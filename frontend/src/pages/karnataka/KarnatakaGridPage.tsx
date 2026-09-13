/**
 * Karnataka Grid Page
 *
 * Displays live/historical/simulated Karnataka macro-grid state from
 * GET /api/data/grid, plus weather from GET /api/data/weather and
 * historical snapshots from /api/data/grid/history and /api/data/weather/history.
 */

import { useEffect, useState, useCallback } from "react";
import {
  dataApi,
  GridSnapshot,
  WeatherSnapshot,
} from "../../services/api";
import styles from "./KarnatakaGridPage.module.css";

interface PageState {
  grid: GridSnapshot | null;
  weather: WeatherSnapshot | null;
  gridHistory: GridSnapshot[];
  weatherHistory: WeatherSnapshot[];
  selectedSnapshot: GridSnapshot | null;
  loading: boolean;
  error: string | null;
  lastUpdated: string | null;
}

function formatTimestamp(ts: string): string {
  const date = new Date(ts);
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZoneName: "short",
  });
}

function SourceBadge({ source }: { source: string }) {
  const label = source?.toUpperCase() ?? "UNKNOWN";
  const className =
    source === "live"
      ? styles.badgeLive
      : source === "historical"
      ? styles.badgeHistorical
      : styles.badgeSimulated;

  return <span className={`${styles.badge} ${className}`}>{label}</span>;
}

function StatusPill({ status }: { status: string }) {
  const normalized = (status || "").toUpperCase();
  const isStressed = normalized.includes("STRESS");
  const isOutage = normalized.includes("OUT");
  const variant = isOutage
    ? styles.statusOutage
    : isStressed
    ? styles.statusStressed
    : styles.statusNormal;

  return (
    <span className={`${styles.statusPill} ${variant}`}>
      {normalized || "NORMAL"}
    </span>
  );
}

export default function KarnatakaGridPage() {
  const [state, setState] = useState<PageState>({
    grid: null,
    weather: null,
    gridHistory: [],
    weatherHistory: [],
    selectedSnapshot: null,
    loading: true,
    error: null,
    lastUpdated: null,
  });

  const refresh = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const [grid, weather, gridHistory, weatherHistory] = await Promise.all([
        dataApi.grid(),
        dataApi.weather(),
        dataApi.gridHistory(60),
        dataApi.weatherHistory(60),
      ]);

      setState({
        grid,
        weather,
        gridHistory,
        weatherHistory,
        selectedSnapshot: grid,
        loading: false,
        error: null,
        lastUpdated: new Date().toISOString(),
      });
    } catch (err) {
      const message =
        typeof err === "string"
          ? err
          : err && typeof err === "object" && "message" in err
          ? String((err as { message: string }).message)
          : "Failed to load Karnataka grid data";

      setState((prev) => ({
        ...prev,
        loading: false,
        error: message,
        lastUpdated: new Date().toISOString(),
      }));
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 30_000);
    return () => clearInterval(interval);
  }, [refresh]);

  if (state.loading && !state.grid) {
    return (
      <section className={styles.page}>
        <div className={styles.loading}>
          <div className={styles.spinner} />
          <p>Loading Karnataka grid state…</p>
        </div>
      </section>
    );
  }

  if (state.error && !state.grid) {
    return (
      <section className={styles.page}>
        <div className={styles.error}>
          <h2>Unable to load Karnataka grid data</h2>
          <p>{state.error}</p>
          <button type="button" className={styles.retryButton} onClick={refresh}>
            Retry
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <h1>Karnataka State Grid</h1>
        <div className={styles.headerMeta}>
          <StatusPill status={state.grid?.status ?? "UNKNOWN"} />
          {state.grid && <SourceBadge source={state.grid.source} />}
          {state.lastUpdated && (
            <time className={styles.lastUpdated} dateTime={state.lastUpdated}>
              Updated {formatTimestamp(state.lastUpdated)}
            </time>
          )}
        </div>
      </header>

      <div className={styles.grid}>
        {/* Current snapshot card */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2>Current Grid State</h2>
            {state.grid && <SourceBadge source={state.grid.source} />}
          </div>

          {state.grid && (
            <dl className={styles.metrics}>
              <div className={styles.metric}>
                <dt>Total Demand</dt>
                <dd className={styles.value}>
                  {state.grid.total_demand_mw.toFixed(2)} MW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Total Generation</dt>
                <dd className={styles.value}>
                  {state.grid.total_generation_mw.toFixed(2)} MW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Solar Generation</dt>
                <dd className={styles.value}>
                  {state.grid.solar_generation_mw.toFixed(2)} MW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Wind Generation</dt>
                <dd className={styles.value}>
                  {state.grid.wind_generation_mw.toFixed(2)} MW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Grid Frequency</dt>
                <dd className={styles.value}>
                  {state.grid.grid_frequency_hz.toFixed(3)} Hz
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Balance</dt>
                <dd
                  className={
                    state.grid.total_generation_mw >= state.grid.total_demand_mw
                      ? styles.positive
                      : styles.negative
                  }
                >
                  {(state.grid.total_generation_mw - state.grid.total_demand_mw).toFixed(2)} MW
                </dd>
              </div>
            </dl>
          )}
        </div>

        {/* Weather card */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2>Current Weather</h2>
            {state.weather && <SourceBadge source={state.weather.source} />}
          </div>

          {state.weather && (
            <dl className={styles.metrics}>
              <div className={styles.metric}>
                <dt>Temperature</dt>
                <dd className={styles.value}>
                  {state.weather.temperature_c.toFixed(1)} °C
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Cloud Cover</dt>
                <dd className={styles.value}>
                  {state.weather.cloud_cover_percent.toFixed(1)}%
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Wind Speed</dt>
                <dd className={styles.value}>
                  {state.weather.wind_speed_kmh.toFixed(1)} km/h
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Solar Radiation</dt>
                <dd className={styles.value}>
                  {state.weather.solar_radiation_wm2.toFixed(1)} W/m²
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Condition</dt>
                <dd className={styles.value}>
                  {(state.weather.weather_condition || "unknown").toUpperCase()}
                </dd>
              </div>
            </dl>
          )}
        </div>

        {/* Historical grid snapshots */}
        <div className={`${styles.card} ${styles.historyCard}`}>
          <div className={styles.cardHeader}>
            <h2>Grid History</h2>
            <span className={styles.count}>
              {state.gridHistory.length} snapshots
            </span>
          </div>

          {state.gridHistory.length === 0 ? (
            <p className={styles.empty}>No persisted grid snapshots yet.</p>
          ) : (
            <ul className={styles.historyList}>
              {state.gridHistory.map((snapshot) => (
                <li
                  key={`${snapshot.timestamp}-${snapshot.total_demand_mw}`}
                  className={styles.historyItem}
                  onClick={() =>
                    setState((prev) => ({
                      ...prev,
                      selectedSnapshot: snapshot,
                    }))
                  }
                >
                  <time className={styles.historyTime}>
                    {formatTimestamp(snapshot.timestamp)}
                  </time>
                  <div className={styles.historyValues}>
                    <span className={styles.historyDemand}>
                      {snapshot.total_demand_mw.toFixed(1)} MW
                    </span>
                    <span className={styles.historyGen}>
                      {snapshot.total_generation_mw.toFixed(1)} MW
                    </span>
                    <SourceBadge source={snapshot.source} />
                    <StatusPill status={snapshot.status} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Selected snapshot detail */}
        {state.selectedSnapshot && state.selectedSnapshot !== state.grid && (
          <div className={`${styles.card} ${styles.detailCard}`}>
            <div className={styles.cardHeader}>
              <h2>Snapshot Detail</h2>
              <button
                type="button"
                className={styles.closeButton}
                onClick={() =>
                  setState((prev) => ({
                    ...prev,
                    selectedSnapshot: null,
                  }))
                }
                aria-label="Close snapshot detail"
              >
                ×
              </button>
            </div>

            <dl className={styles.metrics}>
              <div className={styles.metric}>
                <dt>Timestamp</dt>
                <dd className={styles.value}>
                  {formatTimestamp(state.selectedSnapshot.timestamp)}
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Demand</dt>
                <dd className={styles.value}>
                  {state.selectedSnapshot.total_demand_mw.toFixed(2)} MW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Generation</dt>
                <dd className={styles.value}>
                  {state.selectedSnapshot.total_generation_mw.toFixed(2)} MW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Solar</dt>
                <dd className={styles.value}>
                  {state.selectedSnapshot.solar_generation_mw.toFixed(2)} MW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Wind</dt>
                <dd className={styles.value}>
                  {state.selectedSnapshot.wind_generation_mw.toFixed(2)} MW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Frequency</dt>
                <dd className={styles.value}>
                  {state.selectedSnapshot.grid_frequency_hz.toFixed(3)} Hz
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Source</dt>
                <dd className={styles.value}>
                  <SourceBadge source={state.selectedSnapshot.source} />
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Status</dt>
                <dd className={styles.value}>
                  <StatusPill status={state.selectedSnapshot.status} />
                </dd>
              </div>
            </dl>
          </div>
        )}
      </div>

      <footer className={styles.footer}>
        <button type="button" className={styles.refreshButton} onClick={refresh}>
          Refresh now
        </button>
        <p className={styles.note}>
          Data source priority: live API → historical CSV → simulated fallback.
          Source label shown for every reading.
        </p>
      </footer>
    </section>
  );
}
