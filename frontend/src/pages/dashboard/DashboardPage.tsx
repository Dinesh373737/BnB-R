/**
 * GridMind Dashboard
 *
 * Consumes real backend endpoints:
 *   GET /api/health
 *   GET /api/status
 *   GET /api/data/grid
 *   GET /api/data/weather
 *   GET /api/predictions
 *   GET /api/agents/status
 */

import { useEffect, useState, useCallback } from "react";
import {
  systemApi,
  dataApi,
  forecastApi,
  agentsApi,
  HealthResponse,
  StatusResponse,
  GridSnapshot,
  WeatherSnapshot,
  PredictionsSummary,
  AgentStatusResponse,
} from "../../services/api";
import styles from "./DashboardPage.module.css";

function formatTimestamp(ts: string): string {
  const date = new Date(ts);
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
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

function AgentChip({ agentType, status }: { agentType: string; status: string }) {
  const variants: Record<string, string> = {
    idle: styles.agentIdle,
    observing: styles.agentObserving,
    deciding: styles.agentDeciding,
    acting: styles.agentActing,
    waiting: styles.agentWaiting,
    error: styles.agentError,
    disabled: styles.agentDisabled,
  };

  return (
    <span className={`${styles.agentChip} ${variants[status] ?? styles.agentIdle}`}>
      {agentType}
    </span>
  );
}

export default function DashboardPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [grid, setGrid] = useState<GridSnapshot | null>(null);
  const [weather, setWeather] = useState<WeatherSnapshot | null>(null);
  const [predictions, setPredictions] = useState<PredictionsSummary | null>(null);
  const [agents, setAgents] = useState<AgentStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [
        healthData,
        statusData,
        gridData,
        weatherData,
        predictionsData,
        agentsData,
      ] = await Promise.all([
        systemApi.health(),
        systemApi.status(),
        dataApi.grid(),
        dataApi.weather(),
        forecastApi.predictions(),
        agentsApi.status(),
      ]);

      setHealth(healthData);
      setStatus(statusData);
      setGrid(gridData);
      setWeather(weatherData);
      setPredictions(predictionsData);
      setAgents(agentsData);
    } catch (err) {
      setError(
        typeof err === "string"
          ? err
          : err && typeof err === "object" && "message" in err
          ? String((err as { message: string }).message)
          : "Failed to load dashboard data",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 60_000);
    return () => clearInterval(interval);
  }, [refresh]);

  if (loading && !health) {
    return (
      <section className={styles.page}>
        <div className={styles.loading}>
          <div className={styles.spinner} />
          <p>Loading GridMind dashboard…</p>
        </div>
      </section>
    );
  }

  if (error && !health) {
    return (
      <section className={styles.page}>
        <div className={styles.error}>
          <h2>Unable to load GridMind dashboard</h2>
          <p>{error}</p>
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
        <div>
          <h1>GridMind Dashboard</h1>
          <p className={styles.subtitle}>
            Autonomous Multi-Agent AI for Resilient Microgrid Coordination
          </p>
        </div>
        <div className={styles.headerChips}>
          {health && (
            <span className={styles.healthChip}>
              <span className={styles.healthDot} data-status={health.status} />
              {health.status}
            </span>
          )}
          {status?.enabled_agents && (
            <span className={styles.agentCountChip}>
              {status.enabled_agents.length} agents enabled
            </span>
          )}
        </div>
      </header>

      <div className={styles.grid}>
        {/* System status card */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2>System Status</h2>
          </div>
          {health && status && (
            <dl className={styles.metrics}>
              <div className={styles.metric}>
                <dt>Application</dt>
                <dd className={styles.value}>{health.app_name}</dd>
              </div>
              <div className={styles.metric}>
                <dt>Version</dt>
                <dd className={styles.value}>{health.version}</dd>
              </div>
              <div className={styles.metric}>
                <dt>Uptime</dt>
                <dd className={styles.value}>
                  {Math.round(health.uptime_seconds)}s
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Database</dt>
                <dd className={styles.value}>{health.database}</dd>
              </div>
              <div className={styles.metric}>
                <dt>App Mode</dt>
                <dd className={styles.value}>
                  {(status.feature_flags.app_mode as string) ?? "local"}
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Last Check</dt>
                <dd className={styles.value}>
                  {health.timestamp ? formatTimestamp(health.timestamp) : "—"}
                </dd>
              </div>
            </dl>
          )}
        </div>

        {/* Karnataka grid card */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2>Karnataka Grid</h2>
            {grid && <SourceBadge source={grid.source} />}
          </div>
          {grid && (
            <dl className={styles.metrics}>
              <div className={styles.metric}>
                <dt>Demand</dt>
                <dd className={styles.value}>
                  {grid.total_demand_mw.toFixed(1)} MW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Generation</dt>
                <dd className={styles.value}>
                  {grid.total_generation_mw.toFixed(1)} MW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Solar</dt>
                <dd className={styles.value}>
                  {grid.solar_generation_mw.toFixed(1)} MW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Wind</dt>
                <dd className={styles.value}>
                  {grid.wind_generation_mw.toFixed(1)} MW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Frequency</dt>
                <dd className={styles.value}>
                  {grid.grid_frequency_hz.toFixed(3)} Hz
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Status</dt>
                <dd className={styles.value}>
                  <StatusPill status={grid.status} />
                </dd>
              </div>
            </dl>
          )}
        </div>

        {/* Weather card */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2>Weather (Bangalore)</h2>
            {weather && <SourceBadge source={weather.source} />}
          </div>
          {weather && (
            <dl className={styles.metrics}>
              <div className={styles.metric}>
                <dt>Temperature</dt>
                <dd className={styles.value}>
                  {weather.temperature_c.toFixed(1)} °C
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Cloud Cover</dt>
                <dd className={styles.value}>
                  {weather.cloud_cover_percent.toFixed(1)}%
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Wind</dt>
                <dd className={styles.value}>
                  {weather.wind_speed_kmh.toFixed(1)} km/h
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Solar Rad</dt>
                <dd className={styles.value}>
                  {weather.solar_radiation_wm2.toFixed(1)} W/m²
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Condition</dt>
                <dd className={styles.value}>
                  {(weather.weather_condition || "unknown").toUpperCase()}
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Source</dt>
                <dd className={styles.value}>
                  <SourceBadge source={weather.source} />
                </dd>
              </div>
            </dl>
          )}
        </div>

        {/* Predictions card */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2>Predictions</h2>
          </div>
          {predictions && (
            <dl className={styles.metrics}>
              <div className={styles.metric}>
                <dt>Demand (1h)</dt>
                <dd className={styles.value}>
                  {predictions.demand.prediction.toFixed(0)} kW
                </dd>
                <dd className={styles.metricSub}>
                  {predictions.demand.lower?.toFixed(0)} –{" "}
                  {predictions.demand.upper?.toFixed(0)} kW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Solar (1h)</dt>
                <dd className={styles.value}>
                  {predictions.solar.prediction.toFixed(0)} kW
                </dd>
                <dd className={styles.metricSub}>
                  {predictions.solar.lower?.toFixed(0)} –{" "}
                  {predictions.solar.upper?.toFixed(0)} kW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Wind (1h)</dt>
                <dd className={styles.value}>
                  {predictions.wind.prediction.toFixed(0)} kW
                </dd>
                <dd className={styles.metricSub}>
                  {predictions.wind.lower?.toFixed(0)} –{" "}
                  {predictions.wind.upper?.toFixed(0)} kW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Net Position</dt>
                <dd
                  className={
                    predictions.net_position >= 0
                      ? styles.positive
                      : styles.negative
                  }
                >
                  {predictions.net_position.toFixed(0)} kW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Total Gen</dt>
                <dd className={styles.value}>
                  {predictions.total_generation_forecast.toFixed(0)} kW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Confidence</dt>
                <dd className={styles.value}>
                  {(predictions.demand.confidence || "medium").toUpperCase()}
                </dd>
              </div>
            </dl>
          )}
        </div>

        {/* Agents card */}
        <div className={`${styles.card} ${styles.agentsCard}`}>
          <div className={styles.cardHeader}>
            <h2>AI Agents</h2>
            <span className={styles.count}>
              {agents?.agents.length ?? 0} active
            </span>
          </div>
          {agents?.agents && agents.agents.length > 0 ? (
            <ul className={styles.agentList}>
              {agents.agents.map((item) => (
                <li key={item.agent_type} className={styles.agentItem}>
                  <AgentChip agentType={item.agent_type} status={item.status} />
                  <span className={styles.agentDescription}>
                    {item.description ?? item.agent_type}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.empty}>No agent status available.</p>
          )}
        </div>
      </div>

      <footer className={styles.footer}>
        <button type="button" className={styles.refreshButton} onClick={refresh}>
          Refresh dashboard
        </button>
        <p className={styles.note}>
          Data refreshes every 60 seconds. Source labels indicate live, historical, or simulated data.
        </p>
      </footer>
    </section>
  );
}
