"""
GridMind — 🏥 Critical Facility Agent
=========================================
Protects hospitals, emergency infrastructure, and water systems.

Key rules:
  - ALL constraints are DETERMINISTIC — cannot be overridden by LLM.
  - Critical facility minimum supply must ALWAYS be maintained.
  - Requests priority energy when supply is insufficient.
  - LLM is used ONLY for generating human-readable explanations.
"""

import json
from typing import Any

from backend.common.schemas.enums import AgentType, RiskLevel, CriticalLoadStatus
from backend.common.schemas.microgrid_state import MicrogridState
from backend.common.schemas.messages import AgentDecision
from backend.modules.agents.base_agent import BaseAgent


class CriticalFacilityAgent(BaseAgent):
    """Protects critical facilities — hospitals, emergency services, water."""

    def __init__(self):
        super().__init__(
            agent_type=AgentType.CRITICAL_FACILITY,
            name="Critical Facility Agent",
            description=(
                "Monitors critical load, requests priority energy, "
                "maintains minimum required supply. All constraints are "
                "deterministic and cannot be overridden by LLM."
            ),
        )

    # ── Observe ───────────────────────────────────────────────────────────

    def observe(self, state: MicrogridState) -> dict[str, Any]:
        cf = state.critical_facility
        inputs = {
            "required_power_kw": cf.required_power_kw,
            "current_supply_kw": cf.current_supply_kw,
            "backup_energy_kwh": cf.backup_energy_kwh,
            "reserve_power_kw": cf.reserve_power_kw,
            "is_protected": cf.is_protected,
            "status": cf.status.value,
            "supply_ratio": cf.current_supply_kw / max(cf.required_power_kw, 1.0),
            "total_generation_kw": state.total_generation_kw,
            "total_demand_kw": state.total_demand_kw,
            "battery_soc": state.battery.current_soc,
            "battery_energy_available_kwh": state.battery.energy_available_kwh,
            "risk_level": state.risk.risk_level.value,
            "risk_score": state.risk.risk_score,
            "grid_connected": state.grid_connection.is_connected,
            "energy_balance_kw": state.energy_balance_kw,
        }
        self._last_inputs = inputs
        return inputs

    # ── Decide ────────────────────────────────────────────────────────────

    async def decide(self, state: MicrogridState) -> list[AgentDecision]:
        inputs = self._last_inputs
        decisions: list[AgentDecision] = []

        required = inputs["required_power_kw"]
        current_supply = inputs["current_supply_kw"]
        supply_ratio = inputs["supply_ratio"]
        backup = inputs["backup_energy_kwh"]
        battery_available = inputs["battery_energy_available_kwh"]
        risk_level = inputs["risk_level"]
        is_high_risk = risk_level in (RiskLevel.HIGH.value, RiskLevel.CRITICAL.value)

        # ── 1. CRITICAL PROTECTION CHECK (fully deterministic) ────────

        if supply_ratio >= 1.0 and inputs["is_protected"]:
            # Fully protected — maintain status
            decisions.append(self._make_decision(
                action="normal",
                resource="critical_facilities",
                reason=f"Critical facilities fully supplied ({current_supply:.1f}/{required:.1f} kW).",
                expected_effect="Normal operations for hospitals and emergency services.",
                confidence=1.0,
                priority=8,
            ))

        elif supply_ratio >= 0.8:
            # Slightly below — reserve additional energy
            deficit_kw = required - current_supply
            reserve_kw = round(deficit_kw * 1.2, 2)  # 20% safety margin

            decisions.append(self._make_decision(
                action="reserve",
                resource="critical_facilities",
                quantity_kw=reserve_kw,
                reason=(
                    f"Critical supply at {supply_ratio:.0%} ({current_supply:.1f}/{required:.1f} kW). "
                    f"Reserving {reserve_kw:.1f} kW with safety margin."
                ),
                expected_effect="Maintain minimum critical facility supply.",
                confidence=0.95,
                priority=9,
            ))

        elif supply_ratio >= 0.5:
            # At risk — protect immediately
            deficit_kw = required - current_supply

            decisions.append(self._make_decision(
                action="protect",
                resource="critical_facilities",
                quantity_kw=round(deficit_kw, 2),
                reason=(
                    f"CRITICAL: Supply at {supply_ratio:.0%}. "
                    f"Deficit of {deficit_kw:.1f} kW. Requesting priority energy."
                ),
                expected_effect="Restore critical facility power to minimum required level.",
                confidence=1.0,
                priority=10,  # Highest priority
            ))

            # Request battery support if available
            if battery_available > deficit_kw / 60:  # at least 1 min of coverage
                decisions.append(self._make_decision(
                    action="emergency",
                    resource="battery_for_critical",
                    quantity_kw=round(deficit_kw, 2),
                    reason=f"Requesting {deficit_kw:.1f} kW from battery for critical facilities.",
                    expected_effect="Battery supports critical load until supply is restored.",
                    confidence=0.95,
                    priority=10,
                ))

        else:
            # EMERGENCY — below 50% supply
            deficit_kw = required - current_supply

            decisions.append(self._make_decision(
                action="emergency",
                resource="critical_facilities",
                quantity_kw=round(deficit_kw, 2),
                reason=(
                    f"EMERGENCY: Critical facility supply at {supply_ratio:.0%}! "
                    f"Need {deficit_kw:.1f} kW immediately. "
                    f"Hospitals and emergency services at risk."
                ),
                expected_effect="Emergency power restoration for critical infrastructure.",
                confidence=1.0,
                priority=10,
            ))

        # ── 2. HIGH RISK PREEMPTIVE PROTECTION ────────────────────────

        if is_high_risk and supply_ratio < 1.2:
            # During high risk, maintain 120% buffer for critical facilities
            buffer_kw = round(required * 0.20, 2)
            decisions.append(self._make_decision(
                action="reserve",
                resource="critical_reserve",
                quantity_kw=buffer_kw,
                reason=(
                    f"High risk ({risk_level}). Pre-emptively reserving "
                    f"{buffer_kw:.1f} kW buffer for critical facilities."
                ),
                expected_effect="Critical facilities have additional buffer during high-risk period.",
                confidence=0.95,
                priority=9,
            ))

        # ── 3. LLM EXPLANATION (optional — for human readability) ─────

        reason = "; ".join(d.reason for d in decisions)
        effect = "; ".join(d.expected_effect for d in decisions)

        if supply_ratio < 0.8:
            llm_result = await self._call_llm(
                system_prompt=(
                    "You are a critical infrastructure protection specialist. "
                    "Given the facility state, provide a concise explanation of the "
                    "protection actions. All constraints are deterministic — you "
                    "provide explanation only. Respond in JSON with keys: "
                    "reason (string), expected_effect (string)."
                ),
                user_message=json.dumps(inputs),
            )
            if llm_result:
                reason = llm_result.get("reason", reason)
                effect = llm_result.get("expected_effect", effect)

        self._last_reason = reason
        self._last_expected_effect = effect

        return decisions
