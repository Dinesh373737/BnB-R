"""Coordinator-to-simulation control bridge.

Converts the multi-agent pipeline's approved ``AgentDecision`` list into
concrete ``ControlInputs`` for the deterministic simulation, so that the
"GridMind" run is actually driven by its agents (unlike the baseline, which
uses naive deterministic control).

Mapping rules:
* ``charge`` / ``discharge`` on the battery  → ``battery_power_kw``
  (discharge is negative because discharging is local generation).
* ``reduce`` on ``household_flexible`` / ``industry_flexible`` /
  ``ev_fleet`` → the *remaining* flexible demand after the reduction
  (the simulation expects absolute levels, not deltas).
* ``delay_ev`` → zero EV flexible demand for this timestep.
* Safety-rejected decisions are ignored before this conversion.

All quantities are clamped to physically valid ranges; a conversion failure
of one decision never blocks the others.
"""

from __future__ import annotations

from backend.common.logger import get_module_logger
from backend.common.schemas.enums import AgentType
from backend.common.schemas.microgrid_state import MicrogridState
from backend.modules.agents.schemas import AgentDecision
from backend.modules.simulation.schemas import ControlInputs

log = get_module_logger("agents.control_bridge")


def decisions_to_controls(
    state: MicrogridState,
    decisions: list[AgentDecision],
) -> ControlInputs:
    """Convert approved agent decisions into simulation control inputs."""
    battery_power: float | None = None
    household_flex: float | None = None
    industry_flex: float | None = None
    ev_flex: float | None = None

    for decision in decisions:
        try:
            agent = decision.agent
            agent_value = agent.value if hasattr(agent, "value") else str(agent)
            action = (decision.action or "").lower()
            resource = (decision.resource or "").lower()
            quantity_kw = decision.quantity_kw

            if quantity_kw is None:
                continue

            # ── Battery ──────────────────────────────────────────────
            if resource == "battery":
                if action == "charge":
                    power = float(quantity_kw)
                elif action == "discharge":
                    power = -float(quantity_kw)
                else:  # "reserve" / hold — no explicit power
                    continue
                # Keep the strongest requested magnitude if multiple
                if battery_power is None or abs(power) > abs(battery_power):
                    battery_power = power

            # ── EV fleet ──────────────────────────────────────────────
            elif resource == "ev_fleet":
                if action in ("delay_ev", "reduce", "defer", "shift"):
                    ev_flex = 0.0 if action == "delay_ev" else max(
                        0.0, state.ev.flexible_demand_kw - float(quantity_kw)
                    )
                elif action == "restore":
                    ev_flex = state.ev.flexible_demand_kw

            # ── Household flexible load ───────────────────────────────
            elif resource == "household_flexible":
                if action in ("reduce", "shift", "defer"):
                    household_flex = max(
                        0.0,
                        state.households.flexible_demand_kw - float(quantity_kw),
                    )
                elif action == "restore":
                    household_flex = state.households.flexible_demand_kw

            # ── Industrial flexible load ──────────────────────────────
            elif resource == "industry_flexible":
                if action in ("reduce", "shift", "defer"):
                    industry_flex = max(
                        0.0,
                        state.industry.flexible_demand_kw - float(quantity_kw),
                    )
                elif action == "restore":
                    industry_flex = state.industry.flexible_demand_kw

            # ── Generic flexible loads ────────────────────────────────
            elif resource == "flexible_loads":
                if action in ("reduce", "shift"):
                    total_flex = (
                        state.households.flexible_demand_kw
                        + state.industry.flexible_demand_kw
                    )
                    if household_flex is None:
                        household_flex = max(
                            0.0,
                            state.households.flexible_demand_kw
                            - float(quantity_kw)
                            * (
                                state.households.flexible_demand_kw
                                / max(total_flex, 1.0)
                            ),
                        )
                    if industry_flex is None:
                        industry_flex = max(
                            0.0,
                            state.industry.flexible_demand_kw
                            - float(quantity_kw)
                            * (
                                state.industry.flexible_demand_kw
                                / max(total_flex, 1.0)
                            ),
                        )

            _ = agent_value  # reserved for future per-agent policies

        except Exception as exc:
            log.warning(
                "Skipping decision conversion (%s/%s): %s",
                decision.action,
                decision.resource,
                exc,
            )

    controls = ControlInputs(
        battery_power_kw=battery_power,
        household_flexible_demand_kw=household_flex,
        industry_flexible_demand_kw=industry_flex,
        ev_flexible_demand_kw=ev_flex,
    )
    log.debug("Converted %d decision(s) -> %s", len(decisions), controls)
    return controls
