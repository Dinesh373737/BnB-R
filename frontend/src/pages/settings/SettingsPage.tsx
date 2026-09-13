/**
 * Settings Page
 *
 * Consumes:
 *   GET /api/status   (feature flags, enabled agents/forecasts, API registry)
 *   GET /api/health
 */

import { useCallback, useEffect, useState } from "react";
import {
  systemApi,
  safetyApi,
  StatusResponse,
  HealthResponse,
  SafetyStatusResponse,
} from "../../services/api";
import styles from "../shared.module.css";

interface FlagGroup {
  title: string;
  flags: { name: string; value: boolean | string }[];
}

function buildFlagGroups(status: StatusResponse): FlagGroup[] {
  const ff = (status.feature_flags ?? {}) as Record<string, unknown>;
  const boolFlags = (obj: unknown): { name: string; value: boolean | string }[] =>
    Object.entries((obj ?? {}) as Record<string, unknown>).map(([name, value]) => ({
      name,
      value: value as boolean | string,
    }));

  return [
    {
      title: "Application",
      flags: [
        { name: "APP_MODE", value: String(ff.app_mode ?? "local") },
        { name: "DATABASE_MODE", value: String(ff.database_mode ?? "sqlite") },
      ],
    },
    { title: "Agents", flags: boolFlags(ff.agents) },
    { title: "Machine Learning", flags: boolFlags(ff.ml) },
    { title: "Data Sources", flags: boolFlags(ff.data_sources) },
    { title: "Features", flags: boolFlags(ff.features) },
    { title: "Cloud", flags: boolFlags(ff.cloud) },
    { title: "Optional", flags: boolFlags(ff.optional) },
  ].filter((group) => group.flags.length > 0);
}

export default function SettingsPage() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [safety, setSafety] = useState<SafetyStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [statusData, healthData, safetyData] = await Promise.all([
        systemApi.status(),
        systemApi.health(),
        safetyApi.status().catch(() => null),
      ]);
      setStatus(statusData);
      setHealth(healthData);
      setSafety(safetyData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 30_000);
    return () => clearInterval(interval);
  }, [refresh]);

  if (loading && !status) {
    return (
      <section className={styles.page}>
        <div className={styles.loading}>
          <div className={styles.spinner} />
          <p>Loading configuration…</p>
        </div>
      </section>
    );
  }

  if (error && !status) {
    return (
      <section className={styles.page}>
        <div className={styles.error}>
          <h2>Unable to load settings</h2>
          <p>{error}</p>
          <button type="button" className={styles.primaryButton} onClick={refresh}>
            Retry
          </button>
        </div>
      </section>
    );
  }

  const groups = status ? buildFlagGroups(status) : [];

  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1>Settings</h1>
          <p className={styles.subtitle}>
            Live configuration and feature flags, read from the backend
            environment. Values are set in the server's .env file.
          </p>
        </div>
        <div className={styles.headerActions}>
          {health && (
            <span className={`${styles.pill} ${styles.pillOk}`}>
              {health.app_name} v{health.version} — {health.status}
            </span>
          )}
        </div>
      </header>

      <div className={styles.grid}>
        {groups.map((group) => (
          <div key={group.title} className={styles.card}>
            <div className={styles.cardHeader}>
              <h2>{group.title}</h2>
            </div>
            <ul className={styles.list}>
              {group.flags.map((flag) => {
                const isString = typeof flag.value === "string";
                const isOn = flag.value === true;
                return (
                  <li key={flag.name} className={styles.listItem}>
                    <span className={styles.itemTitle}>{flag.name}</span>
                    {isString ? (
                      <span className={`${styles.pill} ${styles.pillInfo}`}>
                        {String(flag.value)}
                      </span>
                    ) : (
                      <span
                        className={`${styles.pill} ${isOn ? styles.pillOk : styles.pillNeutral}`}
                      >
                        {isOn ? "ON" : "OFF"}
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        ))}

        {status?.enabled_agents && (
          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <h2>Enabled Agents</h2>
              <span className={styles.count}>{status.enabled_agents.length}</span>
            </div>
            <div className={styles.itemMeta}>
              {status.enabled_agents.map((agent) => (
                <span key={agent} className={`${styles.pill} ${styles.pillOk}`}>
                  {agent}
                </span>
              ))}
            </div>
          </div>
        )}

        {status?.enabled_forecasts && (
          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <h2>Enabled Forecasts</h2>
              <span className={styles.count}>{status.enabled_forecasts.length}</span>
            </div>
            <div className={styles.itemMeta}>
              {status.enabled_forecasts.map((forecast) => (
                <span key={forecast} className={`${styles.pill} ${styles.pillInfo}`}>
                  {forecast}
                </span>
              ))}
            </div>
          </div>
        )}

        {safety && (
          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <h2>Safety Layer</h2>
              <span className={`${styles.pill} ${styles.pillOk}`}>{safety.status}</span>
            </div>
            <p className={styles.itemSub}>{safety.service}</p>
            <div className={styles.itemMeta} style={{ marginTop: 12 }}>
              {safety.risk_levels.map((level) => (
                <span key={level} className={`${styles.pill} ${styles.pillNeutral}`}>
                  {level}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      <footer className={styles.footer}>
        <button type="button" className={styles.button} onClick={refresh}>
          Refresh settings
        </button>
        <p className={styles.note}>
          Feature flags are loaded from the backend .env at startup. Edit the
          .env file and restart the server to change them.
        </p>
      </footer>
    </section>
  );
}
