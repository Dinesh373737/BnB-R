/**
 * Digital Twin Volumetric Particle Flow (3D)
 *
 * A living 3D model of the microgrid: solar arrays, wind turbines, battery
 * banks, EV chargers, the critical facility, and the grid interconnection,
 * connected by CatmullRomCurve3 transmission splines. Emissive particles flow
 * along the splines; their emission rate and speed track the live per-asset
 * power from the /ws/microgrid broadcast (e.g. battery discharge instantly
 * increases outflow particles).
 *
 * Assets are genuine glTF models (public/models/*.gltf) loaded
 * asynchronously via useGLTF.
 */

import { Suspense, useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, useGLTF } from "@react-three/drei";
import * as THREE from "three";
import { useLiveChannel } from "../../hooks/useLiveChannel";
import { simulationApi } from "../../services/api";
import styles from "../shared.module.css";

// ── Asset layout: physical positions in the twin ──────────────────────

interface AssetPosition {
  id: string;
  label: string;
  position: [number, number, number];
  model: string;
  scale: number;
}

const ASSETS: AssetPosition[] = [
  { id: "solar", label: "Solar Array", position: [-7, 0, -3], model: "/models/solar_array.gltf", scale: 0.9 },
  { id: "wind", label: "Wind Turbines", position: [7.5, 0, -4], model: "/models/wind_turbine.gltf", scale: 0.9 },
  { id: "battery", label: "Battery Bank", position: [0, 0, -4.5], model: "/models/battery_bank.gltf", scale: 1.0 },
  { id: "ev", label: "EV Chargers", position: [-4.5, 0, 3.5], model: "/models/ev_charger.gltf", scale: 1.1 },
  { id: "hospital", label: "Critical Facility", position: [4.5, 0, 3.5], model: "/models/hospital.gltf", scale: 1.0 },
  { id: "grid", label: "Grid Interconnection", position: [0, 0, 6.5], model: "/models/battery_bank.gltf", scale: 0.75 },
];

// ── Transmission splines (real energy pathways) ──────────────────────

interface FlowPath {
  id: string;
  from: string;
  to: string;
  curve: THREE.CatmullRomCurve3;
  /** unit vector direction the particles travel (from → to). */
  forward: boolean;
}

function buildSplines(): FlowPath[] {
  const byId = new Map(ASSETS.map((a) => [a.id, a.position]));

  const make = (from: string, to: string, lift = 1.6): FlowPath => {
    const a = new THREE.Vector3(...(byId.get(from) as [number, number, number]));
    const b = new THREE.Vector3(...(byId.get(to) as [number, number, number]));
    // Midpoint raised to give flowing transmission arcs.
    const mid = a.clone().add(b).multiplyScalar(0.5);
    const dir = b.clone().sub(a).normalize();
    const perp = new THREE.Vector3(-dir.z, 0, dir.x);
    mid.add(perp.multiplyScalar(lift * 0.3));
    mid.y += lift;
    const curve = new THREE.CatmullRomCurve3(
      [a, mid, b],
      false,
      "catmullrom",
      0.5,
    );
    return { id: `${from}->${to}`, from, to, curve, forward: true };
  };

  return [
    make("solar", "battery"),
    make("wind", "battery"),
    make("battery", "hospital"),
    make("battery", "ev"),
    make("grid", "battery"),
    make("battery", "solar"),   // charging path (reverse flow)
    make("solar", "hospital"),
    make("wind", "ev"),
  ];
}

// ── Live flow intensities per pathway from broadcast state ────────────

interface FlowLevels {
  solar: number;
  wind: number;
  battery: number;   // >0 charging, <0 discharging
  batterySoc: number;
  grid: number;       // import positive
  ev: number;
  critical: number;
  household: number;
  industry: number;
}

function extractFlow(msg: unknown): FlowLevels | null {
  const m = msg as { flow?: Record<string, number> } | null;
  const f = m?.flow;
  if (!f) return null;
  return {
    solar: f.solar_kw ?? 0,
    wind: f.wind_kw ?? 0,
    battery: f.battery_kw ?? 0,
    batterySoc: f.battery_soc ?? 0,
    grid: f.grid_import_kw ?? 0,
    ev: f.ev_kw ?? 0,
    critical: f.critical_kw ?? 0,
    household: f.household_kw ?? 0,
    industry: f.industry_kw ?? 0,
  };
}

/** Map live kW flow to a pathway intensity [0, 1]. */
function pathIntensity(path: FlowPath, flow: FlowLevels): number {
  switch (`${path.from}->${path.to}`) {
    case "solar->battery":
      return clamp01(flow.solar / 500);
    case "wind->battery":
      return clamp01(flow.wind / 500);
    case "battery->hospital":
      return clamp01(flow.critical / 250);
    case "battery->ev":
      return clamp01(flow.ev / 150);
    case "grid->battery":
      return clamp01(flow.grid / 2000);
    case "battery->solar": // battery charging from surplus
      return clamp01(flow.battery / 300);
    case "solar->hospital":
      return clamp01((flow.solar * 0.3) / 200);
    case "wind->ev":
      return clamp01((flow.wind * 0.3) / 200);
    default:
      return 0.15;
  }
}

function clamp01(v: number): number {
  return Math.max(0.05, Math.min(1, Math.abs(v) / 300));
}

// ── Emissive particles travelling the splines ─────────────────────────

const PARTICLES_PER_PATH = 14;

function FlowParticles({
  splines,
  live,
}: {
  splines: FlowPath[];
  live: React.RefObject<unknown>;
}) {
  const group = useRef<THREE.Group>(null);
  const particleMeshes = useRef<THREE.Mesh[]>([]);
  const progress = useRef<number[]>(
    Array.from({ length: splines.length }, (_, i) => i / splines.length),
  );

  // Instanced emissive spheres per path
  const materials = useMemo(
    () =>
      splines.map(() =>
        new THREE.MeshBasicMaterial({
          color: "#22d3ee",
          transparent: true,
          opacity: 0.85,
        }),
      ),
    [splines],
  );

  useFrame((_, delta) => {
    const flow = extractFlow((live as { current: unknown }).current);
    const dt = Math.min(delta, 0.05);

    for (let p = 0; p < splines.length; p++) {
      const path = splines[p];
      const intensity = flow ? pathIntensity(path, flow) : 0.2;

      // Emission rate scales with instantaneous power — e.g. a rapidly
      // discharging battery instantly increases particle flow out.
      const speed = 0.06 + intensity * 0.5;

      for (let k = 0; k < PARTICLES_PER_PATH; k++) {
        const idx = p * PARTICLES_PER_PATH + k;
        const mesh = particleMeshes.current[idx];
        if (!mesh) continue;

        if (k === 0) {
          // advance the head particle; others follow at fixed offsets
          progress.current[p] = (progress.current[p] + speed * dt) % 1;
        }
        const t =
          (progress.current[p] + k / PARTICLES_PER_PATH) % 1;
        const point = path.curve.getPointAt(t);
        mesh.position.copy(point);

        // fade tail particles
        const material = materials[p];
        material.opacity = 0.25 + intensity * 0.6;
        mesh.material = material;
        const scale = 0.5 + intensity * 0.9 * (1 - k / PARTICLES_PER_PATH);
        mesh.scale.setScalar(scale);
      }
    }
  });

  return (
    <group ref={group}>
      {splines.map((_, p) =>
        Array.from({ length: PARTICLES_PER_PATH }).map((_, k) => (
          <mesh
            key={`${p}-${k}`}
            ref={(m) => {
              if (m) particleMeshes.current[p * PARTICLES_PER_PATH + k] = m;
            }}
          >
            <sphereGeometry args={[0.09, 10, 10]} />
            <meshBasicMaterial color="#22d3ee" transparent opacity={0.7} />
          </mesh>
        )),
      )}
    </group>
  );
}

// ── Transmission line geometry (faint tubes along splines) ───────────

function TransmissionLines({ splines }: { splines: FlowPath[] }) {
  const geometries = useMemo(
    () => splines.map((s) => new THREE.TubeGeometry(s.curve, 48, 0.025, 6, false)),
    [splines],
  );
  return (
    <>
      {geometries.map((g, i) => (
        <mesh key={i} geometry={g}>
          <meshBasicMaterial color="#1e3a5f" transparent opacity={0.5} />
        </mesh>
      ))}
    </>
  );
}

// ── GlTF asset instances ─────────────────────────────────────────────

function Asset({
  info,
  live,
}: {
  info: AssetPosition;
  live: React.RefObject<unknown>;
}) {
  const { scene } = useGLTF(info.model) as unknown as { scene: THREE.Group };
  const cloned = useMemo(() => scene.clone(true), [scene]);
  const group = useRef<THREE.Group>(null);
  const rotor = useRef<THREE.Group>(null);

  // wind turbine rotor blades (procedural, animated by live wind kW)
  useFrame((state, delta) => {
    if (info.id === "wind") {
      const flow = extractFlow((live as { current: unknown }).current);
      const windKw = flow?.wind ?? 120;
      const spin = (windKw / 500) * 6 * Math.min(delta * 60, 2);
      if (rotor.current) rotor.current.rotation.z += spin;
    }
    if (info.id === "battery" && group.current) {
      const flow = extractFlow((live as { current: unknown }).current);
      const soc = flow?.batterySoc ?? 0.5;
      // subtle glow pulse tied to SOC
      const s = 1 + 0.02 * Math.sin(state.clock.elapsedTime * (1 + soc * 3));
      group.current.scale.setScalar(s * info.scale);
    }
  });

  return (
    <group ref={group} position={info.position} scale={info.scale}>
      <primitive object={cloned} />
      {info.id === "wind" && (
        <group ref={rotor} position={[0, 3.35, 0.3]}>
          {[0, 1, 2].map((i) => (
            <mesh key={i} rotation={[0, 0, (i * Math.PI * 2) / 3]}>
              <boxGeometry args={[0.08, 1.4, 0.02]} />
              <meshStandardMaterial color="#e2e8f0" metalness={0.3} />
            </mesh>
          ))}
        </group>
      )}
      {/* Label anchor light */}
      <pointLight
        color={info.id === "battery" ? "#fbbf24" : "#38bdf8"}
        intensity={0.6}
        distance={4}
        position={[0, 1.4, 0]}
      />
    </group>
  );
}

// ── Ground grid ──────────────────────────────────────────────────────

function Ground() {
  return (
    <>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.02, 0]}>
        <planeGeometry args={[40, 40]} />
        <meshStandardMaterial color="#0b1220" roughness={0.9} metalness={0.1} />
      </mesh>
      <gridHelper args={[40, 40, "#123", "#0d1b2a"]} position={[0, 0, 0]} />
    </>
  );
}

// ── Scene assembly ────────────────────────────────────────────────────

function TwinScene({ live }: { live: React.RefObject<unknown> }) {
  const splines = useMemo(() => buildSplines(), []);
  return (
    <>
      <ambientLight intensity={0.5} />
      <directionalLight position={[6, 10, 4]} intensity={1.1} color="#e0f2fe" />
      <directionalLight position={[-6, 6, -6]} intensity={0.3} color="#fef3c7" />
      <Suspense fallback={null}>
        {ASSETS.map((asset) => (
          <Asset key={asset.id} info={asset} live={live} />
        ))}
      </Suspense>
      <TransmissionLines splines={splines} />
      <FlowParticles splines={splines} live={live} />
      <Ground />
      <OrbitControls
        enableDamping
        dampingFactor={0.6}
        target={[0, 0.5, 0]}
        minDistance={6}
        maxDistance={45}
        maxPolarAngle={Math.PI / 2.05}
        rotateSpeed={0.8}
        zoomSpeed={1.0}
      />
    </>
  );
}

// ── Page component with telemetry side panel ──────────────────────────

export function DigitalTwinPage() {
  const { latest, snapshot, connected } = useLiveChannel("microgrid");
  const flow = extractFlow(snapshot);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  /** Run the agent-driven loop live — particles visibly change as power shifts. */
  const runLive = async () => {
    setBusy(true);
    setNote(null);
    try {
      const states = await simulationApi.run();
      setNote(
        `Agent loop complete — ${states.length} timesteps. Watch the battery outflow and grid import particles change intensity over the next broadcasts.`,
      );
    } catch (err) {
      setNote(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const triggerCrisis = async () => {
    setBusy(true);
    setNote(null);
    try {
      const res = await simulationApi.activatePrimaryScenario();
      setNote(
        `Crisis "${res.scenario}" active — solar particles will thin (−50% output) within the next broadcast.`,
      );
    } catch (err) {
      setNote(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1>Digital Twin</h1>
          <p className={styles.subtitle}>
            Volumetric particle flow across the live microgrid — solar, wind,
            battery, EV, critical facility, and grid interconnection. Drag to
            orbit, scroll to zoom; particle intensity tracks instantaneous kW.
          </p>
        </div>
        <div className={styles.headerActions}>
          <span className={`${styles.pill} ${connected ? styles.pillOk : styles.pillWarn}`}>
            {connected ? "● LIVE TWIN" : "○ connecting…"}
          </span>
          <button type="button" className={styles.button} onClick={runLive} disabled={busy}>
            {busy ? "Running…" : "Run agent loop"}
          </button>
          <button type="button" className={styles.primaryButton} onClick={triggerCrisis} disabled={busy}>
            Trigger crisis
          </button>
        </div>
      </header>

      {note && <p className={styles.reasoning} style={{ marginBottom: 16 }}>{note}</p>}

      <div className={styles.canvasShell} style={{ background: "#080e1c" }}>
        <Canvas camera={{ position: [0, 11, 18], fov: 55 }} dpr={[1, 2]}>
          <color attach="background" args={["#080e1c"]} />
          <TwinScene live={latest} />
        </Canvas>

        <div className={styles.hopOverlay}>
          {flow ? (
            <>
              <div className={styles.hopStat}>
                <span>Solar</span>
                <strong>{flow.solar.toFixed(0)} kW</strong>
              </div>
              <div className={styles.hopStat}>
                <span>Wind</span>
                <strong>{flow.wind.toFixed(0)} kW</strong>
              </div>
              <div className={styles.hopStat}>
                <span>Battery</span>
                <strong className={flow.battery >= 0 ? styles.positive : styles.negative}>
                  {flow.battery >= 0 ? "+" : ""}
                  {flow.battery.toFixed(0)} kW ({(flow.batterySoc * 100).toFixed(0)}%)
                </strong>
              </div>
              <div className={styles.hopStat}>
                <span>Grid import</span>
                <strong>{flow.grid.toFixed(0)} kW</strong>
              </div>
              <div className={styles.hopStat}>
                <span>Critical load</span>
                <strong className={styles.positive}>{flow.critical.toFixed(0)} kW</strong>
              </div>
            </>
          ) : (
            <p className={styles.hopStat}>Waiting for live broadcast…</p>
          )}
        </div>
      </div>

      <footer className={styles.footer}>
        <p className={styles.note}>
          Emission rates map to instantaneous power — a rapidly discharging
          battery instantly increases outflow particles; wind rotor speed
          tracks live wind generation.
        </p>
      </footer>
    </section>
  );
}
