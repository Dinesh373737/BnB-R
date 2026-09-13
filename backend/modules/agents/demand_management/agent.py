"""
GridMind — 🏠 Demand Management Agent
=========================================
Manages household and industrial flexible loads.

Key rules:
  - Demand reduction amounts are calculated DETERMINISTICALLY.
  - Critical loads must NEVER be arbitrarily reduced.
  - LLM is used to reason about WHICH loads to shed/shift and WHY.
"""

import json
from typing import Any

from backend.common.schemas.enums import AgentType, RiskLevel
from backend.common.schemas.microgrid_state import MicrogridState
from backend.common.schemas.messages import AgentDecision
from backend.modules.agents.base_agent import BaseAgent


class DemandManagementAgent(BaseAgent):
    """Manages household and industrial flexible demand."""

    def __init__(self):
        super().__init__(
            agent_type=AgentType.DEMAND_MANAGEMENT,
            name="Demand Management Agent",
            description=(
                "Detects demand spikes, reduces/shifts flexible demand, "
                "minimises user disruption, reduces peak demand. "
                "Critical loads are NEVER reduced."
            ),
        )

    # ── Observe ───────────────────────────────────────────────────────────

    def observe(self, state: MicrogridState) -> dict[str, Any]:
        inputs = {
            "total_demand_kw": state.total_demand_kw,
            "total_generation_kw": state.total_generation_kw,
            "energy_balance_kw": state.energy_balance_kw,
            "household_total_kw": state.households.total_demand_kw,
            "household_flexible_kw": state.households.flexible_demand_kw,
            "household_fixed_kw": state.households.fixed_demand_kw,
            "household_count": state.households.count,
            "industry_total_kw": state.industry.total_demand_kw,
            "industry_flexible_kw": state.industry.flexible_demand_kw,
            "industry_fixed_kw": state.industry.fixed_demand_kw,
            "critical_required_kw": state.critical_facility.required_power_kw,
            "risk_level": state.risk.risk_level.value,
            "risk_score": state.risk.risk_score,
            "battery_soc": state.battery.current_soc,
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
        is_medium_risk = risk_level == RiskLevel.MEDIUM.value
        energy_balance = inputs["energy_balance_kw"]
        deficit = abs(energy_balance) if energy_balance < 0 else 0

        household_flex = inputs["household_flexible_kw"]
        industry_flex = inputs["industry_flexible_kw"]
        total_flex = household_flex + industry_flex

        # ── 1. DETERMINE REDUCTION NEEDED (deterministic) ─────────────

        if deficit <= 0 and not is_high_risk:
            # No deficit and low/medium risk — no action needed
            self._last_reason = "No demand reduction needed — supply meets demand."
            self._last_expected_effect = "Normal operations continue."
            return decisions

        # Calculate how much to reduce based on risk + deficit
        if risk_level == RiskLevel.CRITICAL.value:
            reduction_pct = 0.50  # Reduce up to 50% of flexible load
        elif risk_level == RiskLevel.HIGH.value:
            reduction_pct = 0.30  # Reduce up to 30%
        elif is_medium_risk and deficit > 0:
            reduction_pct = 0.15  # Reduce up to 15%
        elif deficit > 0:
            reduction_pct = min(0.20, deficit / max(total_flex, 1.0))
        else:
            reduction_pct = 0.0

        # ── 2. HOUSEHOLD LOAD REDUCTION (deterministic) ───────────────

        hh_reduction_kw = round(household_flex * reduction_pct, 2)
        if hh_reduction_kw > 1.0:
            decisions.append(self._make_decision(
                action="reduce",
                resource="household_flexible",
                quantity_kw=hh_reduction_kw,
                reason=(
                    f"Risk={risk_level}, deficit={deficit:.1f} kW. "
                    f"Reducing {reduction_pct:.0%} of household flexible load "
                    f"({hh_reduction_kw:.1f} kW of {household_flex:.1f} kW)."
                ),
                expected_effect=(
                    f"Household demand reduced by {hh_reduction_kw:.1f} kW. "
                    f"Fixed/critical loads unaffected."
                ),
                confidence=0.90,
                priority=7 if is_high_risk else 5,
            ))

        # ── 3. INDUSTRIAL LOAD REDUCTION (deterministic) ──────────────

        ind_reduction_kw = round(industry_flex * reduction_pct, 2)
        if ind_reduction_kw > 1.0:
            decisions.append(self._make_decision(
                action="reduce",
                resource="industry_flexible",
                quantity_kw=ind_reduction_kw,
                reason=(
                    f"Risk={risk_level}. Reducing {reduction_pct:.0%} of industrial "
                    f"flexible load ({ind_reduction_kw:.1f} kW of {industry_flex:.1f} kW)."
                ),
                expected_effect=(
                    f"Industrial demand reduced by {ind_reduction_kw:.1f} kW."
                ),
                confidence=0.85,
                priority=6 if is_high_risk else 4,
            ))

        # ── 4. LOAD SHIFTING (if surplus expected later) ──────────────

        demand_fc = state.forecast.demand_forecast_kw
        if demand_fc and demand_fc < inputs["total_demand_kw"] * 0.85 and total_flex > 0:
            # Demand forecast shows future decrease — shift loads forward
            shift_kw = round(total_flex * 0.10, 2)
            if shift_kw > 1.0:
                decisions.append(self._make_decision(
                    action="shift",
                    resource="flexible_loads",
                    quantity_kw=shift_kw,
                    reason="Forecast shows lower demand ahead. Shifting flexible load to off-peak.",
                    expected_effect=f"Peak reduced by {shift_kw:.1f} kW, deferred to low-demand period.",
                    confidence=0.75,
                    priority=4,
                ))

        # ── 5. LLM REASONING (optional) ──────────────────────────────

        total_reduced = sum(d.quantity_kw or 0 for d in decisions)
        reason = (
            f"Demand management: reduced {total_reduced:.1f} kW of flexible load "
            f"({len(decisions)} action(s)). Critical loads untouched."
        )
        effect = f"Total demand reduced by ~{total_reduced:.1f} kW."

        if is_high_risk:
            llm_result = await self._call_llm(
                system_prompt=(
                    "You are a demand management specialist for a community microgrid. "
                    "Given the current state and demand reduction actions, provide strategic "
                    "reasoning about load management. IMPORTANT: critical loads must NEVER "
                    "be reduced. Respond in JSON with keys: reason (string), "
                    "expected_effect (string)."
                ),
                user_message=json.dumps({
                    "observations": inputs,
                    "actions_taken": [d.action for d in decisions],
                    "total_reduced_kw": total_reduced,
                }),
            )
            if llm_result:
                reason = llm_result.get("reason", reason)
                effect = llm_result.get("expected_effect", effect)

        self._last_reason = reason
        self._last_expected_effect = effect

        return decisions
