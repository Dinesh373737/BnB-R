"""
GridMind — 🔋 Energy Resource Agent
=======================================
Manages solar, wind, battery, and EV charging.

Key rules:
  - Battery charge/discharge amounts are calculated DETERMINISTICALLY.
  - Emergency battery reserve is always preserved.
  - EV charging is deferred during high-risk periods.
  - LLM is used for strategic reasoning only (e.g., "should we discharge now?").
"""

import json
from typing import Any

from backend.common.schemas.enums import AgentType, RiskLevel
from backend.common.schemas.microgrid_state import MicrogridState
from backend.common.schemas.messages import AgentDecision
from backend.modules.agents.base_agent import BaseAgent


class EnergyResourceAgent(BaseAgent):
    """Manages battery, solar, wind, and EV resource decisions."""

    def __init__(self):
        super().__init__(
            agent_type=AgentType.ENERGY_RESOURCE,
            name="Energy Resource Agent",
            description=(
                "Maximises renewable utilisation, recommends battery charge/discharge, "
                "preserves emergency reserve, defers EV charging during high risk."
            ),
        )

    # ── Observe ───────────────────────────────────────────────────────────

    def observe(self, state: MicrogridState) -> dict[str, Any]:
        inputs = {
            "solar_output_kw": state.solar.current_output_kw,
            "solar_capacity_kw": state.solar.capacity_kw,
            "wind_output_kw": state.wind.current_output_kw,
            "wind_capacity_kw": state.wind.capacity_kw,
            "battery_soc": state.battery.current_soc,
            "battery_capacity_kwh": state.battery.capacity_kwh,
            "battery_min_soc": state.battery.min_soc,
            "battery_max_soc": state.battery.max_soc,
            "battery_charge_rate_kw": state.battery.charge_rate_kw,
            "battery_discharge_rate_kw": state.battery.discharge_rate_kw,
            "battery_energy_available_kwh": state.battery.energy_available_kwh,
            "ev_connected": state.ev.connected_count,
            "ev_charging": state.ev.charging_count,
            "ev_demand_kw": state.ev.total_demand_kw,
            "ev_flexible_kw": state.ev.flexible_demand_kw,
            "total_demand_kw": state.total_demand_kw,
            "total_generation_kw": state.total_generation_kw,
            "energy_balance_kw": state.energy_balance_kw,
            "risk_level": state.risk.risk_level.value,
            "risk_score": state.risk.risk_score,
            "grid_connected": state.grid_connection.is_connected,
        }
        self._last_inputs = inputs
        return inputs

    # ── Decide ────────────────────────────────────────────────────────────

    async def decide(self, state: MicrogridState) -> list[AgentDecision]:
        inputs = self._last_inputs
        decisions: list[AgentDecision] = []

        risk_level = inputs["risk_level"]
        is_high_risk = risk_level in (RiskLevel.HIGH.value, RiskLevel.CRITICAL.value)
        energy_balance = inputs["energy_balance_kw"]

        soc = inputs["battery_soc"]
        min_soc = inputs["battery_min_soc"]
        max_soc = inputs["battery_max_soc"]
        capacity = inputs["battery_capacity_kwh"]
        charge_rate = inputs["battery_charge_rate_kw"]
        discharge_rate = inputs["battery_discharge_rate_kw"]

        # ── 1. BATTERY DECISIONS (deterministic) ──────────────────────

        # Emergency reserve threshold — keep at least 20% during high risk
        emergency_soc = 0.20 if is_high_risk else min_soc

        if energy_balance > 0:
            # Surplus energy → charge battery
            available_headroom_kwh = (max_soc - soc) * capacity
            charge_kw = min(energy_balance, charge_rate, available_headroom_kwh * 60)

            if charge_kw > 1.0 and soc < max_soc:
                decisions.append(self._make_decision(
                    action="charge",
                    resource="battery",
                    quantity_kw=round(charge_kw, 2),
                    reason=f"Surplus {energy_balance:.1f} kW. Charging battery (SOC={soc:.1%}).",
                    expected_effect=f"Battery SOC increases towards {max_soc:.0%}.",
                    confidence=0.95,
                    priority=6,
                ))

        elif energy_balance < 0:
            # Deficit → consider discharging battery
            deficit_kw = abs(energy_balance)
            dischargeable_kwh = (soc - emergency_soc) * capacity
            discharge_kw = min(deficit_kw, discharge_rate, dischargeable_kwh * 60)

            if discharge_kw > 1.0 and soc > emergency_soc:
                decisions.append(self._make_decision(
                    action="discharge",
                    resource="battery",
                    quantity_kw=round(discharge_kw, 2),
                    reason=(
                        f"Deficit {deficit_kw:.1f} kW. Discharging battery "
                        f"(SOC={soc:.1%}, emergency_floor={emergency_soc:.0%})."
                    ),
                    expected_effect="Reduce grid dependency.",
                    confidence=0.90,
                    priority=7 if is_high_risk else 5,
                ))
            elif soc <= emergency_soc:
                # Reserve the battery
                decisions.append(self._make_decision(
                    action="reserve",
                    resource="battery",
                    reason=(
                        f"Battery SOC ({soc:.1%}) at or below emergency reserve "
                        f"({emergency_soc:.0%}). Holding."
                    ),
                    expected_effect="Emergency energy preserved for critical loads.",
                    confidence=1.0,
                    priority=9 if is_high_risk else 7,
                ))

        # ── 2. EV CHARGING DECISIONS (deterministic) ──────────────────

        ev_demand = inputs["ev_demand_kw"]
        ev_flexible = inputs["ev_flexible_kw"]

        if is_high_risk and ev_flexible > 0:
            # Defer flexible EV charging during high risk
            decisions.append(self._make_decision(
                action="delay_ev",
                resource="ev_fleet",
                quantity_kw=round(ev_flexible, 2),
                reason=f"Risk level {risk_level}. Deferring {ev_flexible:.1f} kW flexible EV load.",
                expected_effect=f"Reduce total demand by {ev_flexible:.1f} kW.",
                confidence=0.90,
                priority=7,
            ))

        # ── 3. RENEWABLE UTILIZATION SIGNAL ───────────────────────────

        solar_util = inputs["solar_output_kw"] / max(inputs["solar_capacity_kw"], 1)
        wind_util = inputs["wind_output_kw"] / max(inputs["wind_capacity_kw"], 1)

        if solar_util > 0.8 and wind_util > 0.5 and energy_balance > 0:
            decisions.append(self._make_decision(
                action="use_local",
                resource="renewables",
                quantity_kw=round(inputs["solar_output_kw"] + inputs["wind_output_kw"], 2),
                reason="High renewable availability — maximising local consumption.",
                expected_effect="Reduce grid imports, lower cost.",
                confidence=0.95,
                priority=5,
            ))

        # ── 4. LLM STRATEGY (optional — only for complex situations) ──

        reason_summary = "; ".join(d.reason for d in decisions) if decisions else "No actions needed."
        effect_summary = "; ".join(d.expected_effect for d in decisions) if decisions else "Stable."

        if is_high_risk or abs(energy_balance) > inputs["total_demand_kw"] * 0.3:
            llm_result = await self._call_llm(
                system_prompt=(
                    "You are a microgrid energy resource manager. Given the current "
                    "state and the deterministic decisions already made, provide strategic "
                    "reasoning. Respond in JSON with keys: reason (string), "
                    "expected_effect (string)."
                ),
                user_message=json.dumps({
                    "observations": inputs,
                    "deterministic_decisions": [d.action for d in decisions],
                }),
            )
            if llm_result:
                reason_summary = llm_result.get("reason", reason_summary)
                effect_summary = llm_result.get("expected_effect", effect_summary)

        self._last_reason = reason_summary
        self._last_expected_effect = effect_summary

        return decisions
