/**
 * Predictions & Risk Page
 *
 * Consumes:
 *   GET /api/predictions
 *   GET /api/forecast/demand
 *   GET /api/forecast/solar
 *   GET /api/forecast/wind
 *   GET /api/agents/status
 *   GET /api/agents/risk_forecast/decisions
 */

import { useEffect, useState, useCallback } from "react";
import {
  forecastApi,
  agentsApi,
  ForecastResult,
  PredictionsSummary,
  AgentDecisionsResponse,
} from "../../services/api";
import styles from "./PredictionsPage.module.css";

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

function ConfidenceBadge({ confidence }: { confidence: string }) {
  const label = (confidence || "medium").toUpperCase();
  const variants: Record<string, string> = {
    LOW: styles.confLow,
    MEDIUM: styles.confMedium,
    HIGH: styles.confHigh,
  };

  return (
    <span className={`${styles.confBadge} ${variants[label] ?? styles.confMedium}`}>
      {label}
    </span>
  );
}

interface HorizonControl {
  label: string;
  value: number;
}

const HORIZONS: HorizonControl[] = [
  { label: "15 min", value: 15 },
  { label: "30 min", value: 30 },
  { label: "1 hour", value: 60 },
  { label: "3 hours", value: 180 },
  { label: "6 hours", value: 360 },
  { label: "24 hours", value: 1440 },
];

export default function PredictionsPage() {
  const [summary, setSummary] = useState<PredictionsSummary | null>(null);
  const [demand, setDemand] = useState<ForecastResult | null>(null);
  const [solar, setSolar] = useState<ForecastResult | null>(null);
  const [wind, setWind] = useState<ForecastResult | null>(null);
  const [riskDecisions, setRiskDecisions] = useState<AgentDecisionsResponse | null>(null);
  const [horizon, setHorizon] = useState(60);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadPredictions = useCallback(
    async (horizonMinutes: number) => {
      setLoading(true);
      setError(null);
      try {
        const [summaryData, demandData, solarData, windData, riskData] = await Promise.all([
          forecastApi.predictions(),
          forecastApi.demand({ horizon_minutes: horizonMinutes }),
          forecastApi.solar({ horizon_minutes: horizonMinutes }),
          forecastApi.wind({ horizon_minutes: horizonMinutes }),
          agentsApi.decisions("risk_forecast").catch(() => null),
        ]);

        setSummary(summaryData);
        setDemand(demandData);
        setSolar(solarData);
        setWind(windData);
        setRiskDecisions(riskData ?? null);
      } catch (err) {
        setError(
          typeof err === "string"
            ? err
            : err && typeof err === "object" && "message" in err
            ? String((err as { message: string }).message)
            : "Failed to load predictions",
        );
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    loadPredictions(horizon);
    const interval = setInterval(() => loadPredictions(horizon), 60_000);
    return () => clearInterval(interval);
  }, [loadPredictions, horizon]);

  if (loading && !summary) {
    return (
      <section className={styles.page}>
        <div className={styles.loading}>
          <div className={styles.spinner} />
          <p>Loading predictions and risk assessment…</p>
        </div>
      </section>
    );
  }

  if (error && !summary) {
    return (
      <section className={styles.page}>
        <div className={styles.error}>
          <h2>Unable to load predictions</h2>
          <p>{error}</p>
          <button type="button" className={styles.retryButton} onClick={() => loadPredictions(horizon)}>
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
          <h1>Predictions & Risk</h1>
          <p className={styles.subtitle}>
            ML demand, solar, and wind forecasts with uncertainty intervals
          </p>
        </div>
        <div className={styles.horizonControl}>
          <label className={styles.horizonLabel}>Forecast horizon</label>
          <select
            className={styles.horizonSelect}
            value={horizon}
            onChange={(e) => setHorizon(Number(e.target.value))}
          >
            {HORIZONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </header>

      <div className={styles.grid}>
        {/* Consolidated predictions */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2>Consolidated Forecast</h2>
            {summary && (
              <span className={styles.timestamp}>
                {formatTimestamp(summary.timestamp)}
              </span>
            )}
          </div>
          {summary && (
            <dl className={styles.metrics}>
              <div className={styles.metric}>
                <dt>Total Generation</dt>
                <dd className={styles.value}>
                  {summary.total_generation_forecast.toFixed(0)} kW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Net Position</dt>
                <dd
                  className={
                    summary.net_position >= 0 ? styles.positive : styles.negative
                  }
                >
                  {summary.net_position.toFixed(0)} kW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Renewable Share</dt>
                <dd className={styles.value}>
                  {(
                    (summary.solar.prediction + summary.wind.prediction) /
                    Math.max(summary.total_generation_forecast, 1) *
                    100
                  ).toFixed(1)}
                  %
                </dd>
              </div>
            </dl>
          )}
        </div>

        {/* Demand forecast */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.cardTitleDemand}>Demand Forecast</h2>
            {demand && <ConfidenceBadge confidence={demand.confidence} />}
          </div>
          {demand && (
            <dl className={styles.metrics}>
              <div className={styles.metric}>
                <dt>Prediction</dt>
                <dd className={styles.value}>
                  {demand.prediction.toFixed(0)} kW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Lower Bound</dt>
                <dd className={styles.value}>
                  {demand.lower?.toFixed(0) ?? "—"} kW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Upper Bound</dt>
                <dd className={styles.value}>
                  {demand.upper?.toFixed(0) ?? "—"} kW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Horizon</dt>
                <dd className={styles.value}>{demand.horizon_minutes} min</dd>
              </div>
              <div className={styles.metric}>
                <dt>Model</dt>
                <dd className={styles.value}>{demand.model_type}</dd>
              </div>
            </dl>
          )}
        </div>

        {/* Solar forecast */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.cardTitleSolar}>Solar Forecast</h2>
            {solar && <ConfidenceBadge confidence={solar.confidence} />}
          </div>
          {solar && (
            <dl className={styles.metrics}>
              <div className={styles.metric}>
                <dt>Prediction</dt>
                <dd className={styles.value}>
                  {solar.prediction.toFixed(0)} kW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Lower Bound</dt>
                <dd className={styles.value}>
                  {solar.lower?.toFixed(0) ?? "—"} kW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Upper Bound</dt>
                <dd className={styles.value}>
                  {solar.upper?.toFixed(0) ?? "—"} kW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Horizon</dt>
                <dd className={styles.value}>{solar.horizon_minutes} min</dd>
              </div>
              <div className={styles.metric}>
                <dt>Model</dt>
                <dd className={styles.value}>{solar.model_type}</dd>
              </div>
            </dl>
          )}
        </div>

        {/* Wind forecast */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.cardTitleWind}>Wind Forecast</h2>
            {wind && <ConfidenceBadge confidence={wind.confidence} />}
          </div>
          {wind && (
            <dl className={styles.metrics}>
              <div className={styles.metric}>
                <dt>Prediction</dt>
                <dd className={styles.value}>
                  {wind.prediction.toFixed(0)} kW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Lower Bound</dt>
                <dd className={styles.value}>
                  {wind.lower?.toFixed(0) ?? "—"} kW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Upper Bound</dt>
                <dd className={styles.value}>
                  {wind.upper?.toFixed(0) ?? "—"} kW
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>Horizon</dt>
                <dd className={styles.value}>{wind.horizon_minutes} min</dd>
              </div>
              <div className={styles.metric}>
                <dt>Model</dt>
                <dd className={styles.value}>{wind.model_type}</dd>
              </div>
            </dl>
          )}
        </div>

        {/* Risk agent decisions */}
        <div className={`${styles.card} ${styles.riskCard}`}>
          <div className={styles.cardHeader}>
            <h2>Risk & Forecast Agent Decisions</h2>
          </div>
          {riskDecisions && riskDecisions.decisions.length > 0 ? (
            <ul className={styles.decisionList}>
              {riskDecisions.decisions.map((decision, index) => (
                <li key={index} className={styles.decisionItem}>
                  <div className={styles.decisionHeader}>
                    <span className={styles.decisionAgent}>{decision.agent}</span>
                    <span className={styles.decisionAction}>{decision.action}</span>
                    {decision.resource && (
                      <span className={styles.decisionResource}>
                        {decision.resource}
                      </span>
                    )}
                  </div>
                  <p className={styles.decisionReason}>
                    {decision.reason ?? decision.expected_effect ?? "No details"}
                  </p>
                  <div className={styles.decisionMeta}>
                    {decision.quantity_kw !== undefined && decision.quantity_kw !== null && (
                      <span>
                        {decision.quantity_kw.toFixed(2)} kW
                      </span>
                    )}
                    {decision.quantity_kwh !== undefined &&
                      decision.quantity_kwh !== null && (
                        <span>
                          {decision.quantity_kwh.toFixed(2)} kWh
                        </span>
                      )}
                    {decision.confidence !== undefined &&
                      decision.confidence !== null && (
                        <span className={styles.decisionConfidence}>
                          Confidence: {(decision.confidence * 100).toFixed(0)}%
                        </span>
                      )}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.empty}>
              No recent risk agent decisions available.
            </p>
          )}
        </div>
      </div>

      <footer className={styles.footer}>
        <button
          type="button"
          className={styles.refreshButton}
          onClick={() => loadPredictions(horizon)}
        >
          Refresh predictions
        </button>
        <p className={styles.note}>
          Forecasts update every 60 seconds. Uncertainty intervals show lower and upper bounds for the selected horizon.
        </p>
      </footer>
    </section>
  );
}
