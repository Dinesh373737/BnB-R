"""Hopfield energy landscape computation.

Computes a continuous Hopfield energy for the live microgrid using the
standard quadratic energy form:

    E = -1/2 * Σ_{i,j} w_ij s_i s_j + Σ_i θ_i s_i

The microgrid's operating signals are mapped onto Hopfield neurons:

* ``s_i`` (neuron states in [-1, 1]): normalized utilisation signals — solar
  utilisation, wind utilisation, battery SOC position, grid dependency,
  demand pressure, and critical-facility protection.
* ``w_ij`` (weights): coupling matrix built from the physical co-dependence
  of each pair of signals. Positive weight = reinforcing coupling (both high
  is stable); negative = conflicting coupling (both high is unstable).
* ``θ_i`` (thresholds): per-signal bias reflecting how much each signal
  contributes to instability (e.g. high grid dependency raises energy).

A stable, self-sufficient microgrid sits in a low-energy basin; stress
(deficit, grid dependence, depleted battery) raises the energy surface.
"""

from __future__ import annotations

import math

from backend.common.schemas.microgrid_state import MicrogridState

# ── Signal definitions ────────────────────────────────────────────────

SIGNALS = ["solar", "wind", "battery", "grid", "demand", "critical"]


def _clamp(value: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def extract_neuron_states(state: MicrogridState) -> dict[str, float]:
    """Map live microgrid signals to Hopfield neuron states in [-1, 1].

    Positive values indicate the signal pushes the system toward its
    stable configuration; negative values indicate stress contribution.
    """
    solar_util = state.solar.current_output_kw / max(state.solar.capacity_kw, 1.0)
    wind_util = state.wind.current_output_kw / max(state.wind.capacity_kw, 1.0)
    battery_soc = _clamp(state.battery.current_soc, 0.0, 1.0)
    grid_dep = _clamp(state.grid_dependency_pct / 100.0, 0.0, 1.0)
    demand_pressure = _clamp(
        state.total_demand_kw
        / max(state.total_generation_kw + state.grid_connection.import_power_kw, 1.0)
        - 0.5,
        -0.5,
        0.5,
    )
    critical_ok = 1.0 if state.critical_facility.is_protected else -1.0

    return {
        # Renewable contribution (positive when producing)
        "solar": _clamp(solar_util * 2.0 - 0.3),
        "wind": _clamp(wind_util * 2.0 - 0.3),
        # Battery: positive when charged above mid-range, negative when low
        "battery": _clamp(battery_soc * 2.0 - 1.0),
        # Grid dependency: positive *reduces* stability (sign flipped later)
        "grid": _clamp(grid_dep * 2.0 - 1.0),
        # Demand pressure above generation
        "demand": _clamp(-demand_pressure * 2.0),
        # Critical facility protection
        "critical": critical_ok,
    }


# ── Coupling matrix (symmetric, w_ij = w_ji) ──────────────────────────
# Physical interpretation:
#   renewables ↔ battery: positive (charging keeps both stable)
#   renewables ↔ grid:   negative (renewables reduce grid dependence)
#   demand ↔ grid:       positive coupling cost (demand forces imports)
#   demand ↔ battery:    negative (discharge relieves demand stress)
#   critical ↔ others:   mild positive (protection improves with reserves)

_COUPLING: dict[tuple[str, str], float] = {
    ("solar", "battery"): 0.8,
    ("wind", "battery"): 0.7,
    ("solar", "grid"): -0.6,
    ("wind", "grid"): -0.5,
    ("solar", "demand"): -0.4,
    ("wind", "demand"): -0.4,
    ("battery", "demand"): -0.7,
    ("battery", "grid"): -0.5,
    ("demand", "grid"): 0.9,
    ("critical", "battery"): 0.5,
    ("critical", "solar"): 0.3,
    ("critical", "wind"): 0.3,
    ("critical", "grid"): -0.3,
    ("critical", "demand"): -0.4,
    ("solar", "wind"): 0.4,
}

# Per-signal instability thresholds θ_i
_THRESHOLDS = {
    "solar": -0.10,
    "wind": -0.10,
    "battery": -0.05,
    "grid": 0.35,   # relying on the grid raises energy
    "demand": 0.30, # high demand raises energy
    "critical": -0.20,
}


def _weight(i: str, j: str) -> float:
    if i == j:
        return 0.0
    return _COUPLING.get((i, j)) or _COUPLING.get((j, i)) or 0.0


def hopfield_energy(state: MicrogridState) -> dict:
    """Compute the continuous Hopfield energy for a live microgrid state.

    Returns the scalar energy, the neuron states, and the raw terms so the
    frontend can shape its energy landscape surface from the same numbers.
    """
    s = extract_neuron_states(state)

    # Quadratic coupling term: -1/2 Σ w_ij s_i s_j
    quadratic = 0.0
    terms: dict[str, float] = {}
    for i in SIGNALS:
        for j in SIGNALS:
            if i >= j:
                continue
            contribution = _weight(i, j) * s[i] * s[j]
            quadratic += contribution
            key = f"{i}-{j}"
            terms[key] = round(contribution, 4)
    quadratic_term = -0.5 * quadratic

    # Threshold term: Σ θ_i s_i
    threshold_term = sum(_THRESHOLDS[i] * s[i] for i in SIGNALS)

    energy = quadratic_term + threshold_term

    # Normalise to [-1, 1] for surface shaping (tanh keeps it smooth)
    normalized = math.tanh(energy)

    return {
        "energy": round(energy, 4),
        "normalized": round(normalized, 4),
        "neurons": {k: round(v, 4) for k, v in s.items()},
        "coupling_terms": terms,
        "risk_score": state.risk.risk_score,
        "risk_level": (
            state.risk.risk_level.value
            if hasattr(state.risk.risk_level, "value")
            else str(state.risk.risk_level)
        ),
    }
