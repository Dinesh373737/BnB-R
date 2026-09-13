/**
 * P2P Market & Agent Neural Graph (3D)
 *
 * Force-directed 3D graph of live market participants and AI agents, built
 * with the r3f-forcegraph wrapper over three-forcegraph (d3-force-3d
 * physics). The graph Object3D is hosted inside an R3F Canvas; each frame
 * `tickFrame()` advances the physics engine and particle animation. Buyers
 * and sellers cluster via the force simulation, and energy particles travel
 * the trade links at speeds mapped to the traded kWh volume.
 *
 * Data: /ws/market (pending orders + executed trades) and /ws/agents
 * (live agent decisions), plus REST seeds from the market/agents routers.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import ForceGraph3D from "r3f-forcegraph";
import type { LinkObject, NodeObject } from "r3f-forcegraph";
import * as THREE from "three";
import { agentsApi, marketApi, AgentStatusItem, MarketTrade } from "../../services/api";
import { useLiveChannel } from "../../hooks/useLiveChannel";
import styles from "../shared.module.css";

// ── Types ────────────────────────────────────────────────────────────

interface GraphNode {
  id: string;
  name: string;
  kind: "agent" | "buyer" | "seller";
  capacityKw?: number;
  activity?: number;
  val?: number;
  color?: string;
}

interface GraphLink {
  source: string;
  target: string;
  energyKwh: number;
  price?: number;
  kind: "trade" | "decision";
}

interface GraphDataShape {
  nodes: GraphNode[];
  links: GraphLink[];
}

const AGENT_COLORS: Record<string, string> = {
  coordinator: "#f59e0b",
  risk_forecast: "#ef4444",
  energy_resource: "#10b981",
  demand_management: "#3b82f6",
  market_trading: "#a855f7",
  critical_facility: "#ec4899",
};

function agentColor(type: string): string {
  return AGENT_COLORS[type] ?? "#64748b";
}

function timeNow(): string {
  return new Date().toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

// ── Frame ticker: advances the physics engine every R3F frame ────────

function GraphTicker({ graphRef }: { graphRef: React.MutableRefObject<unknown> }) {
  useFrame(() => {
    const g = graphRef.current as { tickFrame?: () => void } | undefined;
    g?.tickFrame?.();
  });
  return null;
}

/** Fit the camera to the graph bounding box once the layout settles. */
function CameraFit({
  graphRef,
  signal,
}: {
  graphRef: React.MutableRefObject<unknown>;
  signal: number;
}) {
  const { camera } = useThree();
  const lastSignal = useRef(-1);
  useFrame(() => {
    if (signal === lastSignal.current) return;
    const graph = graphRef.current as
      | { getGraphBbox?: () => { x: [number, number]; y: [number, number]; z: [number, number] } }
      | undefined;
    if (!graph?.getGraphBbox) return;
    const bbox = graph.getGraphBbox();
    const dx = bbox.x[1] - bbox.x[0];
    const dy = bbox.y[1] - bbox.y[0];
    const dz = bbox.z[1] - bbox.z[0];
    if (dx + dy + dz > 0.1) {
      const cx = (bbox.x[0] + bbox.x[1]) / 2;
      const cy = (bbox.y[0] + bbox.y[1]) / 2;
      const cz = (bbox.z[0] + bbox.z[1]) / 2;
      const dist = Math.max(dx, dy, dz) * 1.9 + 30;
      camera.position.set(cx + dist * 0.5, cy + dist * 0.6, cz + dist * 0.9);
      camera.lookAt(cx, cy, cz);
      lastSignal.current = signal;
    }
  });
  return null;
}

// ── The R3F scene hosting the three-forcegraph object ────────────────

function GraphScene({
  graphData,
  onNodeClick,
  fitSignal,
}: {
  graphData: GraphDataShape;
  onNodeClick: (node: GraphNode) => void;
  fitSignal: number;
}) {
  // Third-party ref boundary: the wrapper's generics are invariant, so the
  // imperative handle is kept untyped here and cast at each use site.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const graphRef = useRef<any>(undefined);

  const nodeThreeObject = useCallback((node: NodeObject<GraphNode>) => {
    const n = node as GraphNode & NodeObject<GraphNode>;
    const group = new THREE.Group();
    const size = 2 + Math.min((n.val ?? 4) * 0.9, 12);
    const color = new THREE.Color(n.color ?? "#94a3b8");

    group.add(
      new THREE.Mesh(
        new THREE.SphereGeometry(size, 24, 24),
        new THREE.MeshStandardMaterial({
          color,
          emissive: color,
          emissiveIntensity: n.kind === "agent" ? 0.9 : 0.4,
          roughness: 0.3,
          metalness: 0.2,
        }),
      ),
    );

    if (n.kind === "agent") {
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(size * 1.5, size * 0.06, 8, 48),
        new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.5 }),
      );
      ring.rotation.x = Math.PI / 2;
      group.add(ring);
    }
    return group;
  }, []);

  const linkColor = useCallback(
    (link: LinkObject<GraphNode, GraphLink>) =>
      ((link as GraphLink).kind === "trade" ? "#22d3ee" : "#a78bfa"),
    [],
  );

  const particleSpeed = useCallback(
    (link: LinkObject<GraphNode, GraphLink>) => {
      const l = link as GraphLink;
      return 0.004 + (Math.min(l.energyKwh ?? 1, 50) / 50) * 0.012;
    },
    [],
  );

  const particleColor = useCallback(
    (link: LinkObject<GraphNode, GraphLink>) =>
      ((link as GraphLink).kind === "trade" ? "#67e8f9" : "#c4b5fd"),
    [],
  );

  return (
    <>
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      <ForceGraph3D
        ref={graphRef}
        graphData={graphData as any}
        nodeThreeObject={nodeThreeObject}
        nodeColor={(node: NodeObject<GraphNode>) => (node as GraphNode).color ?? "#94a3b8"}
        linkColor={linkColor}
        linkWidth={0.6}
        linkOpacity={0.35}
        linkDirectionalParticles={2}
        linkDirectionalParticleWidth={1.8}
        linkDirectionalParticleSpeed={particleSpeed}
        linkDirectionalParticleColor={particleColor}
        onNodeClick={(node: NodeObject<GraphNode>) => onNodeClick(node as GraphNode)}
        cooldownTicks={120}
        warmupTicks={40}
      />
      <GraphTicker graphRef={graphRef} />
      <CameraFit graphRef={graphRef} signal={fitSignal} />
      <OrbitControls enableDamping dampingFactor={0.6} minDistance={8} maxDistance={400} rotateSpeed={0.7} zoomSpeed={0.9} />
      <ambientLight intensity={0.6} />
      <directionalLight position={[30, 40, 20]} intensity={1.2} />
      <pointLight position={[-30, -20, -30]} intensity={0.5} color="#a855f7" />
    </>
  );
}

// ── Page component ────────────────────────────────────────────────────

export function MarketNeuralGraphPage() {
  const [graphData, setGraphData] = useState<GraphDataShape>({ nodes: [], links: [] });
  const { snapshot: marketMsg } = useLiveChannel("market");
  const { snapshot: agentsMsg } = useLiveChannel("agents");

  const [agentList, setAgentList] = useState<AgentStatusItem[]>([]);
  const [tradesHistory, setTradesHistory] = useState<MarketTrade[]>([]);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [fitSignal, setFitSignal] = useState(0);
  const [activity, setActivity] = useState<string[]>([]);

  // Log live stream events so "it's working" is visible.
  const lastTradeCount = useRef(0);
  useEffect(() => {
    if (!marketMsg) return;
    const trades = (marketMsg as { trades?: unknown[] }).trades ?? [];
    const pending = (marketMsg as { pending_orders?: unknown[] }).pending_orders ?? [];
    if (trades.length !== lastTradeCount.current) {
      const delta = trades.length - lastTradeCount.current;
      lastTradeCount.current = trades.length;
      if (delta > 0) {
        setActivity((a) =>
          [
            `▲ ${timeNow()} — ${delta} new trade(s) executed (total ${trades.length})`,
            ...a,
          ].slice(0, 8),
        );
      }
    }
    setActivity((a) => {
      const status = `● ${timeNow()} — stream alive: ${pending.length} pending order(s), ${trades.length} trade(s)`;
      if (a[0]?.startsWith("●") ?? true) return [status, ...a.filter((x) => !x.startsWith("●"))].slice(0, 8);
      return a;
    });
  }, [marketMsg]);

  useEffect(() => {
    if (!agentsMsg) return;
    const agents = (agentsMsg as { agents?: Array<Record<string, unknown>> }).agents ?? [];
    const withDec = agents.filter((a) => (a.decisions as unknown[] | undefined)?.length);
    if (withDec.length) {
      setActivity((a) =>
        [
          `🧠 ${timeNow()} — ${withDec.length} agent(s) issued decisions (${withDec
            .map((a) => String(a.agent_type))
            .slice(0, 3)
            .join(", ")}${withDec.length > 3 ? "…" : ""})`,
          ...a,
        ].slice(0, 8),
      );
    }
  }, [agentsMsg]);

  useEffect(() => {
    agentsApi.status().then((r) => setAgentList(r.agents)).catch(() => undefined);
    marketApi.trades().then((t) => {
      setTradesHistory(t);
      setFitSignal((s) => s + 1);
    }).catch(() => undefined);
  }, []);

  // Rebuild graph whenever live market/agent messages or histories change.
  useEffect(() => {
    const pending =
      (marketMsg as { pending_orders?: Array<Record<string, unknown>> } | null)?.pending_orders ?? [];
    const liveTrades = (marketMsg as { trades?: Array<Record<string, unknown>> } | null)?.trades ?? [];
    const liveAgentStatuses = (agentsMsg as { agents?: Array<Record<string, unknown>> } | null)?.agents ?? [];

    const nodeMap = new Map<string, GraphNode>();
    const links: GraphLink[] = [];

    // ── Agent nodes ──────────────────────────────────────────────
    for (const agent of agentList) {
      nodeMap.set(`agent:${agent.agent_type}`, {
        id: `agent:${agent.agent_type}`,
        name: agent.name ?? agent.agent_type,
        kind: "agent",
        capacityKw: 500,
        val: 6,
        color: agentColor(agent.agent_type),
      });
    }

    for (const a of liveAgentStatuses) {
      const type = String(a.agent_type ?? "");
      const node = nodeMap.get(`agent:${type}`);
      if (node) {
        const decisions = (a.decisions as unknown[] | undefined)?.length ?? 0;
        node.activity = decisions;
        node.val = 6 + Math.min(decisions * 2, 8);
      }
    }

    // ── Participant nodes ─────────────────────────────────────────
    const participantCapacity = (id: string) => {
      let h = 0;
      for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
      return 20 + (h % 180);
    };

    for (const order of pending) {
      const pid = String(order.participant_id ?? "");
      const type = String(order.order_type ?? "bid");
      if (!pid) continue;
      const key = `p:${pid}`;
      if (!nodeMap.has(key)) {
        nodeMap.set(key, {
          id: key,
          name: String(order.participant_name ?? pid),
          kind: type === "ask" ? "seller" : "buyer",
          capacityKw: participantCapacity(pid),
          val: 3 + participantCapacity(pid) / 60,
          color: type === "ask" ? "#34d399" : "#60a5fa",
        });
      }
    }

    const allTrades = liveTrades as unknown as MarketTrade[];
    for (const trade of allTrades.length ? allTrades : tradesHistory) {
      const sellerKey = `p:${String(trade.seller_id)}`;
      const buyerKey = `p:${String(trade.buyer_id)}`;
      if (!nodeMap.has(sellerKey)) {
        nodeMap.set(sellerKey, {
          id: sellerKey,
          name: trade.seller_name ?? String(trade.seller_id),
          kind: "seller",
          capacityKw: participantCapacity(String(trade.seller_id)),
          val: 4,
          color: "#34d399",
        });
      }
      if (!nodeMap.has(buyerKey)) {
        nodeMap.set(buyerKey, {
          id: buyerKey,
          name: trade.buyer_name ?? String(trade.buyer_id),
          kind: "buyer",
          capacityKw: participantCapacity(String(trade.buyer_id)),
          val: 4,
          color: "#60a5fa",
        });
      }
      links.push({
        source: sellerKey,
        target: buyerKey,
        energyKwh: trade.energy_kwh,
        price: trade.price_per_kwh,
        kind: "trade",
      });
    }

    // ── Agent decision relationships ──────────────────────────────
    for (const a of liveAgentStatuses) {
      const type = String(a.agent_type ?? "");
      const decisions = (a.decisions as Array<Record<string, unknown>> | undefined) ?? [];
      for (const d of decisions) {
        const resource = String(d.resource ?? "");
        if (!resource) continue;
        let targetKey: string | null = null;
        if (resource.includes("battery") || resource.includes("ev")) {
          targetKey = "agent:energy_resource";
        } else if (resource.includes("household") || resource.includes("industry")) {
          targetKey = "agent:demand_management";
        } else if (resource.includes("market") || resource.includes("trade")) {
          targetKey = "agent:market_trading";
        }
        if (targetKey && targetKey !== `agent:${type}`) {
          links.push({
            source: `agent:${type}`,
            target: targetKey,
            energyKwh: Number(d.quantity_kw ?? 1),
            kind: "decision",
          });
        }
      }
    }

    const nodes = Array.from(nodeMap.values());
    if (nodes.length) {
      setGraphData({ nodes, links });
      setFitSignal((s) => s + 1);
    }
  }, [marketMsg, agentsMsg, agentList, tradesHistory]);

  const tradeCount = graphData.links.filter((l) => l.kind === "trade").length;

  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1>Market &amp; Agent Neural Graph</h1>
          <p className={styles.subtitle}>
            Force-directed 3D graph — drag to rotate, scroll to zoom, click a
            node to inspect. Particles flow along executed trades at speeds
            mapped to traded kWh.
          </p>
        </div>
        <div className={styles.headerActions}>
          <span className={`${styles.pill} ${marketMsg ? styles.pillOk : styles.pillWarn}`}>
            {marketMsg ? "● LIVE" : "○ connecting…"}
          </span>
          <span className={`${styles.pill} ${styles.pillInfo}`}>{graphData.nodes.length} nodes</span>
          <span className={`${styles.pill} ${styles.pillNeutral}`}>{tradeCount} live trades</span>
        </div>
      </header>

      <div className={styles.canvasShell}>
        <Canvas camera={{ position: [60, 50, 90], fov: 55 }} dpr={[1, 2]}>
          <color attach="background" args={["#060b18"]} />
          <GraphScene graphData={graphData} onNodeClick={setSelected} fitSignal={fitSignal} />
        </Canvas>

        {/* Live activity log — proof the stream is flowing */}
        <div className={styles.activityPanel}>
          <div className={styles.hopBadge} data-connected={marketMsg ? "true" : "false"}>
            {marketMsg ? "● LIVE" : "○ connecting…"}
          </div>
          {activity.length === 0 ? (
            <p className={styles.hopStat}>Waiting for stream…</p>
          ) : (
            <ul className={styles.activityList}>
              {activity.map((line, i) => (
                <li key={i} className={styles.activityItem} data-agent={line.startsWith("🧠")}>
                  {line}
                </li>
              ))}
            </ul>
          )}
        </div>

        {selected && (
          <div className={styles.graphOverlay}>
            <div className={styles.hopBadge} data-connected="true">SELECTED</div>
            <h3>{selected.name}</h3>
            <p>{selected.kind}</p>
            {selected.capacityKw != null && <p>Capacity ~{selected.capacityKw.toFixed(0)} kW</p>}
            {selected.activity != null && <p>{selected.activity} live decisions</p>}
            <button type="button" className={styles.button} onClick={() => setSelected(null)}>
              Close
            </button>
          </div>
        )}
      </div>

      <footer className={styles.footer}>
        <p className={styles.note}>
          Buyers (blue) and sellers (green) cluster via d3-force-3d physics;
          agents (colored rings) link to the resources they manage. Node
          volume scales with energy capacity.
        </p>
      </footer>
    </section>
  );
}
