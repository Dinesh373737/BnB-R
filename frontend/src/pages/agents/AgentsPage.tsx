/**
 * AI Agents Page
 *
 * Consumes:
 *   GET  /api/agents/status
 *   POST /api/agents/run            (uses current simulation state)
 *   GET  /api/agents/{type}/explain
 *   GET  /api/agents/{type}/decisions
 *   GET  /api/simulation/state
 */

import { useCallback, useEffect, useState } from "react";
import {
  agentsApi,
  simulationApi,
  AgentStatusItem,
  AgentStatusResponse,
  AgentExplanationResponse,
  AgentDecisionsResponse,
  RunAgentsResponse,
  MicrogridState,
} from "../../services/api";
import styles from "../shared.module.css";

const AGENT_LABELS: Record<string, string> = {
  coordinator: "Coordinator",
  risk_forecast: "Risk & Forecast",
  energy_resource: "Energy Resource",
  demand_management: "Demand Management",
  market_trading: "Market & Trading",
  critical_facility: "Critical Facility",
};

function statusPillClass(status: string): string {
  const s = status.toLowerCase();
  if (s === "error" || s === "disabled") return styles.pillErr;
  if (s === "deciding" || s === "acting" || s === "waiting") return styles.pillWarn;
  if (s === "observing") return styles.pillInfo;
  return styles.pillOk;
}

export default function AgentsPage() {
  const [status, setStatus] = useState<AgentStatusResponse | null>(null);
  const [simState, setSimState] = useState<MicrogridState | null>(null);
  const [runResult, setRunResult] = useState<RunAgentsResponse | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [explanation, setExplanation] = useState<AgentExplanationResponse | null>(null);
  const [decisions, setDecisions] = useState<AgentDecisionsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [statusData, stateData] = await Promise.all([
        agentsApi.status(),
        simulationApi.state().catch(() => null),
      ]);
      setStatus(statusData);
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
    const interval = setInterval(refresh, 30_000);
    return () => clearInterval(interval);
  }, [refresh]);

  const loadAgentDetails = useCallback(async (agentType: string) => {
    setSelected(agentType);
    setExplanation(null);
    setDecisions(null);
    try {
      const [explain, decisionsData] = await Promise.all([
        agentsApi.explain(agentType).catch(() => null),
        agentsApi.decisions(agentType).catch(() => null),
      ]);
      setExplanation(explain);
      setDecisions(decisionsData);
    } catch {
      /* details stay empty */
    }
  }, []);

  const runPipeline = useCallback(async () => {
    setRunning(true);
    setError(null);
    try {
      let state = simState;
      if (!state) {
        state = await simulationApi.initialize();
        setSimState(state);
      }
      const result = await agentsApi.run({ state });
      setRunResult(result);
      if (selected) {
        await loadAgentDetails(selected);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  }, [simState, selected, loadAgentDetails]);

  if (loading && !status) {
    return (
      <section className={styles.page}>
        <div className={styles.loading}>
          <div className={styles.spinner} />
          <p>Loading agent status…</p>
        </div>
      </section>
    );
  }

  if (error && !status) {
    return (
      <section className={styles.page}>
        <div className={styles.error}>
          <h2>Unable to load agents</h2>
          <p>{error}</p>
          <button type="button" className={styles.primaryButton} onClick={refresh}>
            Retry
          </button>
        </div>
      </section>
    );
  }

  const agents: AgentStatusItem[] = status?.agents ?? [];

  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1>AI Agents</h1>
          <p className={styles.subtitle}>
            Six-agent pipeline: risk → resources → demand → market → critical →
            coordinator, with safety validation.
          </p>
        </div>
        <div className={styles.headerActions}>
          <button
            type="button"
            className={styles.primaryButton}
            onClick={runPipeline}
            disabled={running}
          >
            {running ? "Running pipeline…" : "Run agent pipeline"}
          </button>
        </div>
      </header>

      <div className={styles.grid}>
        {agents.map((agent) => (
          <div key={agent.agent_type} className={styles.card}>
            <div className={styles.cardHeader}>
              <h2>{AGENT_LABELS[agent.agent_type] ?? agent.name ?? agent.agent_type}</h2>
              <span className={`${styles.pill} ${statusPillClass(agent.status)}`}>
                {agent.status}
              </span>
            </div>
            <p className={styles.itemSub}>{agent.description}</p>
            <div className={styles.itemMeta} style={{ marginTop: 12 }}>
              <span className={`${styles.pill} ${styles.pillNeutral}`}>
                {agent.last_decisions_count ?? 0} decisions
              </span>
              <span
                className={`${styles.pill} ${
                  agent.llm_available ? styles.pillOk : styles.pillNeutral
                }`}
              >
                {agent.llm_available ? "LLM active" : "LLM off"}
              </span>
              <button
                type="button"
                className={styles.button}
                onClick={() => loadAgentDetails(agent.agent_type)}
              >
                Details
              </button>
            </div>
          </div>
        ))}
      </div>

      {runResult && (
        <div className={`${styles.card} ${styles.cardFull}`} style={{ marginTop: 24 }}>
          <div className={styles.cardHeader}>
            <h2>Latest Pipeline Run</h2>
            <div className={styles.itemMeta}>
              <span className={`${styles.pill} ${runResult.success ? styles.pillOk : styles.pillErr}`}>
                {runResult.success ? "success" : "failed"}
              </span>
              <span className={`${styles.pill} ${styles.pillInfo}`}>
                risk {runResult.risk_level} ({runResult.risk_score})
              </span>
            </div>
          </div>
          <div className={styles.metrics}>
            <div className={styles.metric}>
              <dt>Total decisions</dt>
              <dd className={styles.value}>{runResult.total_decisions}</dd>
            </div>
            <div className={styles.metric}>
              <dt>Approved</dt>
              <dd className={`${styles.value} ${styles.positive}`}>
                {runResult.approved_decisions}
              </dd>
            </div>
            <div className={styles.metric}>
              <dt>Rejected</dt>
              <dd className={`${styles.value} ${styles.negative}`}>
                {runResult.rejected_decisions}
              </dd>
            </div>
          </div>
          {runResult.agent_results.map((result) => (
            <div key={result.agent_type} style={{ marginTop: 14 }}>
              <div className={styles.itemTitle}>
                {AGENT_LABELS[result.agent_type] ?? result.agent_type} —{" "}
                {result.decisions.length} decision(s)
              </div>
              {result.reasoning ? (
                <p className={styles.reasoning}>{result.reasoning}</p>
              ) : null}
              <ul className={styles.list} style={{ marginTop: 8 }}>
                {result.decisions.map((decision, i) => (
                  <li key={i} className={styles.listItem}>
                    <div>
                      <span className={styles.itemTitle}>{decision.action}</span>{" "}
                      <span className={styles.itemSub}>{decision.resource}</span>
                      {decision.reason ? (
                        <p className={styles.itemSub}>{decision.reason}</p>
                      ) : null}
                    </div>
                    <div className={styles.itemMeta}>
                      {decision.quantity_kw != null && (
                        <span className={`${styles.pill} ${styles.pillNeutral}`}>
                          {decision.quantity_kw.toFixed(1)} kW
                        </span>
                      )}
                      {decision.confidence != null && (
                        <span className={`${styles.pill} ${styles.pillNeutral}`}>
                          {Math.round((decision.confidence ?? 0) * 100)}% conf
                        </span>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      {selected && (explanation || decisions) && (
        <div className={`${styles.card} ${styles.cardFull}`} style={{ marginTop: 24 }}>
          <div className={styles.cardHeader}>
            <h2>{AGENT_LABELS[selected] ?? selected} — details</h2>
            <button
              type="button"
              className={styles.button}
              onClick={() => setSelected(null)}
            >
              Close
            </button>
          </div>
          {explanation && (
            <>
              <div className={styles.label}>Reason</div>
              <p className={styles.reasoning}>{explanation.reason || "No reason recorded yet — run the pipeline first."}</p>
              {explanation.expected_effect && (
                <>
                  <div className={styles.label} style={{ marginTop: 10 }}>
                    Expected effect
                  </div>
                  <p className={styles.reasoning}>{explanation.expected_effect}</p>
                </>
              )}
            </>
          )}
          {decisions && decisions.decisions.length > 0 && (
            <>
              <div className={styles.label} style={{ marginTop: 14 }}>
                Recent decisions ({decisions.total})
              </div>
              <ul className={styles.list} style={{ marginTop: 8 }}>
                {decisions.decisions.map((d, i) => (
                  <li key={i} className={styles.listItem}>
                    <div>
                      <span className={styles.itemTitle}>{d.action}</span>{" "}
                      <span className={styles.itemSub}>{d.resource}</span>
                      {d.reason ? <p className={styles.itemSub}>{d.reason}</p> : null}
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

      <footer className={styles.footer}>
        <button type="button" className={styles.button} onClick={refresh}>
          Refresh status
        </button>
        <p className={styles.note}>
          Agents run deterministically; the Groq LLM adds reasoning when a key is
          configured. Run the pipeline to populate decisions.
        </p>
      </footer>
    </section>
  );
}
