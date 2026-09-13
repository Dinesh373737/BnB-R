/**
 * Hopfield Energy Landscape (3D)
 *
 * Renders the microgrid's continuous Hopfield energy
 *   E = -1/2 Σ w_ij s_i s_j + Σ θ_i s_i
 * as an undulating terrain. Vertex z-coordinates are displaced every frame
 * from the live risk/energy broadcast (never via setState — direct
 * buffer/uniform writes inside useFrame).
 *
 * The glowing sphere marks the system's current operating point and tracks
 * the terrain height via the same analytic height function used to displace
 * the plane, so it always sits exactly on the surface.
 */

import { useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { useLiveChannel } from "../../hooks/useLiveChannel";

// ── Hopfield surface shaping ────────────────────────────────────────
// The backend broadcasts { energy, normalized, neurons{solar..critical} }.
// We shape the terrain as a superposition of gaussian "energy wells" whose
// depths are driven by the live neuron states and overall normalized energy.

interface HopfieldData {
  energy: number;
  normalized: number;
  neurons: Record<string, number>;
  risk_score: number;
  risk_level: string;
}

function extractHopfield(msg: unknown): HopfieldData | null {
  const m = msg as { hopfield?: HopfieldData } | null;
  return m?.hopfield ?? null;
}

/** Basins placed across the (x, y) domain; each keyed to a neuron signal. */
const BASINS: { key: string; x: number; y: number; sigma: number }[] = [
  { key: "solar", x: -1.4, y: -1.0, sigma: 1.1 },
  { key: "wind", x: 1.4, y: -1.0, sigma: 1.1 },
  { key: "battery", x: 0.0, y: 0.2, sigma: 1.3 },
  { key: "grid", x: -1.6, y: 1.2, sigma: 1.0 },
  { key: "demand", x: 1.6, y: 1.2, sigma: 1.0 },
  { key: "critical", x: 0.0, y: 1.9, sigma: 0.9 },
];

/** Analytic surface height — identical math for terrain and marker lookup. */
function surfaceHeight(
  x: number,
  y: number,
  neurons: Record<string, number>,
  normalized: number,
  time: number,
): number {
  // Hopfield energy wells: negative neuron state (stress) deepens the basin.
  let z = 0;
  for (const basin of BASINS) {
    const s = neurons[basin.key] ?? 0;
    const dx = x - basin.x;
    const dy = y - basin.y;
    const g = Math.exp(-(dx * dx + dy * dy) / (2 * basin.sigma * basin.sigma));
    // Stable signals carve low-energy basins; stressed ones raise peaks.
    z += g * (0.55 * (1 - s) - 0.35 * s);
  }
  // Global energy level raises/lowers the whole surface.
  z += normalized * 0.6;
  // Gentle ambient ripple so the landscape feels alive (fades near edges so
  // it never creates a slope that drags the ball out of the domain).
  const edgeFade = Math.max(
    0,
    Math.min(
      1,
      Math.min(2.5 - Math.abs(x), 2.5 - Math.abs(y)) / 0.6,
    ),
  );
  z += 0.06 * edgeFade * Math.sin(2 * x + time * 0.6) * Math.cos(2 * y - time * 0.4);
  // Domain walls: smooth quadratic rise near the boundary keeps the rolling
  // marker inside the visible terrain (physical basin, not a hard clamp).
  const wallX = Math.max(0, Math.abs(x) - 2.0);
  const wallY = Math.max(0, Math.abs(y) - 2.0);
  z += 2.2 * (wallX * wallX + wallY * wallY);
  return z;
}

// ── Terrain ──────────────────────────────────────────────────────────

/**
 * Eased shader uniforms — the SINGLE source of truth for the surface shape.
 * The terrain writes them each frame (from the live broadcast, or the idle
 * demo motion); the marker reads them so both sample the identical surface.
 */
interface SharedUniforms {
  [uniform: string]: { value: unknown };
  uTime: { value: number };
  uEnergy: { value: number };
  uRisk: { value: number };
  uNeurons: { value: Float32Array };
}

const NEURON_KEYS = ["solar", "wind", "battery", "grid", "demand", "critical"];

function EnergyTerrain({
  live,
  uniforms,
}: {
  live: React.RefObject<unknown>;
  uniforms: SharedUniforms;
}) {
  const mesh = useRef<THREE.Mesh>(null);

  // Custom shader: energy-coloured terrain (calm teal → stressed crimson)
  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        uniforms,
        vertexShader: /* glsl */ `
          uniform float uTime;
          uniform float uEnergy;
          uniform float uRisk;
          uniform float uNeurons[6];
          varying float vHeight;
          varying vec2 vPos;

          float basin(vec2 p, vec2 c, float sigma, float s) {
            vec2 d = p - c;
            float g = exp(-dot(d, d) / (2.0 * sigma * sigma));
            return g * (0.55 * (1.0 - s) - 0.35 * s);
          }

          void main() {
            vec2 p = position.xy;
            float t = uTime;
            float z = 0.0;
            z += basin(p, vec2(-1.4, -1.0), 1.1, uNeurons[0]); // solar
            z += basin(p, vec2( 1.4, -1.0), 1.1, uNeurons[1]); // wind
            z += basin(p, vec2( 0.0,  0.2), 1.3, uNeurons[2]); // battery
            z += basin(p, vec2(-1.6,  1.2), 1.0, uNeurons[3]); // grid
            z += basin(p, vec2( 1.6,  1.2), 1.0, uNeurons[4]); // demand
            z += basin(p, vec2( 0.0,  1.9), 0.9, uNeurons[5]); // critical
            z += uEnergy * 0.6;
            // Ripple fades near the edges (same as the marker's math).
            float edgeFade = clamp(min(2.5 - abs(p.x), 2.5 - abs(p.y)) / 0.6, 0.0, 1.0);
            z += 0.06 * edgeFade * sin(2.0 * p.x + t * 0.6) * cos(2.0 * p.y - t * 0.4);
            // Smooth domain walls keep the rolling marker inside the terrain.
            float wx = max(abs(p.x) - 2.0, 0.0);
            float wy = max(abs(p.y) - 2.0, 0.0);
            z += 2.2 * (wx * wx + wy * wy);

            vHeight = z;
            vPos = p;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(p, z, 1.0);
          }
        `,
        fragmentShader: /* glsl */ `
          precision highp float;
          uniform float uRisk;
          varying float vHeight;
          varying vec2 vPos;

          vec3 calmColor(float h) {
            float t = clamp((h + 0.8) / 1.6, 0.0, 1.0);
            vec3 low = vec3(0.02, 0.32, 0.30);
            vec3 high = vec3(0.16, 0.20, 0.28);
            return mix(low, high, t);
          }

          vec3 stressColor(float h) {
            float t = clamp((h + 0.4) / 1.2, 0.0, 1.0);
            vec3 low = vec3(0.18, 0.06, 0.10);
            vec3 high = vec3(0.78, 0.16, 0.16);
            return mix(low, high, t);
          }

          void main() {
            float risk = clamp(uRisk, 0.0, 1.0);
            vec3 col = mix(calmColor(vHeight), stressColor(vHeight), risk);
            float band = abs(fract(vHeight * 6.0) - 0.5);
            float line = smoothstep(0.45, 0.5, band);
            col += line * mix(vec3(0.1, 0.6, 0.55), vec3(0.9, 0.4, 0.2), risk) * 0.35;
            gl_FragColor = vec4(col, 1.0);
          }
        `,
        side: THREE.DoubleSide,
      }),
    [uniforms],
  );

  const geometry = useMemo(() => new THREE.PlaneGeometry(5, 5, 100, 100), []);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    uniforms.uTime.value = t;

    const hop = extractHopfield((live as { current: unknown }).current);
    if (hop) {
      // Ease toward live values (no re-render, no popping).
      // NOTE: the grid neuron is sign-inverted on the backend (positive =
      // high grid dependency = UNSTABLE), so we flip it here — for every
      // other signal a positive state is stabilising (deep basin).
      const arr = uniforms.uNeurons.value;
      NEURON_KEYS.forEach((k, i) => {
        const raw = hop.neurons[k] ?? 0;
        const target = k === "grid" ? -raw : raw;
        arr[i] += (target - arr[i]) * 0.08;
      });
      uniforms.uEnergy.value +=
        (hop.normalized - uniforms.uEnergy.value) * 0.08;
      uniforms.uRisk.value +=
        (hop.risk_score / 100 - uniforms.uRisk.value) * 0.08;
    } else {
      // Idle demo motion before the first broadcast arrives.
      uniforms.uRisk.value = 0.3 + 0.25 * Math.sin(t * 0.4);
      uniforms.uEnergy.value = 0.2 * Math.sin(t * 0.3);
      const arr = uniforms.uNeurons.value;
      NEURON_KEYS.forEach((k, i) => {
        const raw = 0.2 * Math.sin(t * 0.35 + i * 1.7);
        arr[i] += ((k === "grid" ? -raw : raw) - arr[i]) * 0.05;
      });
    }
  });

  // NOTE: no rotation/offset here — the parent group owns the transform so
  // the marker shares this exact coordinate space.
  return <mesh ref={mesh} geometry={geometry} material={material} />;
}

// ── Glowing state marker — gradient-descent physics ──────────────────

/**
 * The marker is a point mass relaxing on the Hopfield energy surface.
 * Every frame:
 *   1. The eased uniforms (shared with the terrain) define the surface.
 *   2. A numerical gradient ∇h is sampled at the ball's position.
 *   3. Gravity accelerates it downhill (−∇h); friction damps it.
 *   4. Height-map lookup places it exactly on the surface.
 * Because it reads the SAME eased uniforms the shader displaces with, and
 * lives in the SAME parent group, the ball always rides the visible terrain.
 */
function StateMarker({ uniforms }: { uniforms: SharedUniforms }) {
  const group = useRef<THREE.Group>(null);
  const core = useRef<THREE.Mesh>(null);
  const halo = useRef<THREE.Mesh>(null);

  const pos = useRef(new THREE.Vector2(0, 0));
  const vel = useRef(new THREE.Vector2(0, 0));
  const trailPts = useRef<THREE.Vector3[]>([]);

  const trailGeo = useRef(new THREE.BufferGeometry());
  const trailLine = useMemo(
    () =>
      new THREE.Line(
        trailGeo.current,
        new THREE.LineBasicMaterial({ color: "#38bdf8", transparent: true, opacity: 0.55 }),
      ),
    [],
  );

  // Build a neurons record from the eased uniform array (same order as keys).
  const neuronRecord = (arr: Float32Array): Record<string, number> => {
    const out: Record<string, number> = {};
    NEURON_KEYS.forEach((k, i) => (out[k] = arr[i] ?? 0));
    return out;
  };

  useFrame((_, delta) => {
    const t = uniforms.uTime.value;          // identical clock the shader uses
    const dt = Math.min(delta, 0.05);
    const neurons = neuronRecord(uniforms.uNeurons.value);
    const energy = uniforms.uEnergy.value;

    // Numeric gradient of the surface at the ball's position (central diff).
    const eps = 0.06;
    const hC = surfaceHeight(pos.current.x, pos.current.y, neurons, energy, t);
    const hX =
      surfaceHeight(pos.current.x + eps, pos.current.y, neurons, energy, t) -
      surfaceHeight(pos.current.x - eps, pos.current.y, neurons, energy, t);
    const hY =
      surfaceHeight(pos.current.x, pos.current.y + eps, neurons, energy, t) -
      surfaceHeight(pos.current.x, pos.current.y - eps, neurons, energy, t);
    const gx = hX / (2 * eps);
    const gy = hY / (2 * eps);

    // Gravity pulls downhill; friction prevents oscillation blowup.
    const gravity = 3.2;
    const friction = 1.6;
    vel.current.x += -gx * gravity * dt;
    vel.current.y += -gy * gravity * dt;
    vel.current.multiplyScalar(1 - Math.min(friction * dt, 0.9));
    pos.current.addScaledVector(vel.current, dt);

    // Keep the ball inside the plane's 5×5 domain (half-extent 2.5, margin).
    const bound = 2.35;
    pos.current.x = Math.max(-bound, Math.min(bound, pos.current.x));
    pos.current.y = Math.max(-bound, Math.min(bound, pos.current.y));

    if (group.current) {
      group.current.position.set(pos.current.x, pos.current.y, hC + 0.16);
    }
    if (core.current) {
      core.current.scale.setScalar(1 + 0.12 * Math.sin(t * 3.0));
    }
    if (halo.current) {
      halo.current.scale.setScalar(1.6 + 0.35 * Math.sin(t * 2.2));
    }

    // Rolling trail — last 90 sampled positions.
    const p = new THREE.Vector3(pos.current.x, pos.current.y, hC + 0.05);
    const pts = trailPts.current;
    const last = pts[pts.length - 1];
    if (!last || last.distanceTo(p) > 0.015) {
      pts.push(p);
      if (pts.length > 90) pts.shift();
      trailLine.geometry.dispose(); // free the previous GPU buffer
      trailLine.geometry = new THREE.BufferGeometry().setFromPoints(pts);
    }
  });

  return (
    <>
      <primitive object={trailLine} />
      <group ref={group}>
        <mesh ref={core}>
          <sphereGeometry args={[0.14, 32, 32]} />
          <meshStandardMaterial
            color="#67e8f9"
            emissive="#22d3ee"
            emissiveIntensity={2.4}
            roughness={0.15}
            metalness={0.1}
          />
        </mesh>
        <mesh ref={halo}>
          <sphereGeometry args={[0.14, 24, 24]} />
          <meshBasicMaterial color="#22d3ee" transparent opacity={0.18} />
        </mesh>
        <pointLight color="#22d3ee" intensity={2.5} distance={3} />
      </group>
    </>
  );
}

// ── Scene assembly ────────────────────────────────────────────────────

function Scene({ live }: { live: React.RefObject<unknown> }) {
  const uniforms = useMemo<SharedUniforms>(
    () => ({
      uTime: { value: 0 },
      uEnergy: { value: 0 },
      uRisk: { value: 0 },
      uNeurons: { value: new Float32Array(6) },
    }),
    [],
  );

  return (
    <>
      {/* Shared tilted group: the terrain and the marker live in the SAME
          local coordinate space, so the ball always rides the surface. */}
      <group rotation={[-Math.PI / 2.4, 0, 0]} position={[0, -0.4, 0]}>
        <EnergyTerrain live={live} uniforms={uniforms} />
        <StateMarker uniforms={uniforms} />
      </group>
      <ambientLight intensity={0.35} />
      <directionalLight position={[4, 6, 4]} intensity={0.9} color="#bae6fd" />
      <directionalLight position={[-4, 3, -3]} intensity={0.4} color="#fca5a5" />
      <OrbitControls
        enableDamping
        dampingFactor={0.6}
        minDistance={2.5}
        maxDistance={16}
        maxPolarAngle={Math.PI / 2.05}
        rotateSpeed={0.8}
        zoomSpeed={1.0}
      />
    </>
  );
}

// ── Page component ───────────────────────────────────────────────────

import styles from "../shared.module.css";
import { simulationApi } from "../../services/api";

export function HopfieldLandscapePage() {
  const { latest, snapshot, connected } = useLiveChannel("microgrid");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const hop = extractHopfield(snapshot);
  const flow = (snapshot as { flow?: Record<string, number> } | null)?.flow;

  /** Trigger the real backend crisis: solar −50%, flexible demand +30%. */
  const triggerCrisis = async () => {
    setBusy(true);
    setNote(null);
    try {
      const res = await simulationApi.activatePrimaryScenario();
      setNote(
        `Crisis "${res.scenario}" active — solar −50%, flexible demand +30%. Watch the landscape reshape and the marker roll downhill within ~2s (next broadcast).`,
      );
    } catch (err) {
      setNote(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const stepSimulation = async () => {
    setBusy(true);
    setNote(null);
    try {
      await simulationApi.step();
      setNote("Stepped one timestep — risk and energy recomputed from live physics.");
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
          <h1>Hopfield Energy Landscape</h1>
          <p className={styles.subtitle}>
            The microgrid's stability surface E&nbsp;=&nbsp;−½Σw<sub>ij</sub>s<sub>i</sub>s<sub>j</sub>&nbsp;+&nbsp;Σθ<sub>i</sub>s<sub>i</sub>,
            displaced live by risk. Drag to rotate, scroll to zoom; the glowing
            marker tracks the current operating point.
          </p>
        </div>
        <div className={styles.headerActions}>
          <span className={`${styles.pill} ${connected ? styles.pillOk : styles.pillWarn}`}>
            {connected ? "● LIVE" : "○ connecting…"}
          </span>
          <button type="button" className={styles.button} onClick={stepSimulation} disabled={busy}>
            Step simulation
          </button>
          <button type="button" className={styles.primaryButton} onClick={triggerCrisis} disabled={busy}>
            {busy ? "Triggering…" : "Trigger crisis"}
          </button>
        </div>
      </header>

      {note && <p className={styles.reasoning} style={{ marginBottom: 16 }}>{note}</p>}

      <div className={styles.canvasShell} style={{ background: "#050914" }}>
        <Canvas camera={{ position: [0, 4.2, 6.4], fov: 55 }} dpr={[1, 2]}>
          <color attach="background" args={["#050914"]} />
          <Scene live={latest} />
        </Canvas>

        {/* Live telemetry panel */}
        <div className={styles.hopOverlay}>
          {hop ? (
            <>
              <div className={styles.hopStat}>
                <span>Hopfield energy</span>
                <strong>{hop.energy.toFixed(3)}</strong>
              </div>
              <div className={styles.hopStat}>
                <span>Risk</span>
                <strong>
                  {hop.risk_level.toUpperCase()} ({hop.risk_score.toFixed(0)})
                </strong>
              </div>
              <div className={styles.hopNeurons}>
                {Object.entries(hop.neurons).map(([k, v]) => (
                  <div key={k} className={styles.hopNeuron}>
                    <span>{k}</span>
                    <div className={styles.hopNeuronBar}>
                      <div
                        className={styles.hopNeuronFill}
                        style={{ transform: `translateX(${((v + 1) / 2) * 100}%)` }}
                        data-neg={v < 0}
                      />
                    </div>
                    <em>{v.toFixed(2)}</em>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className={styles.hopStat}>Waiting for live broadcast…</p>
          )}
          {flow && (
            <div className={styles.hopStat}>
              <span>Balance</span>
              <strong className={flow.energy_balance_kw >= 0 ? styles.positive : styles.negative}>
                {flow.energy_balance_kw.toFixed(0)} kW
              </strong>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
