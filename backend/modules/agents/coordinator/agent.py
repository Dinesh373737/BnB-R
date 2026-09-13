"""
GridMind — 🧠 Coordinator Agent
====================================
Central coordinator that collects all agent recommendations,
resolves conflicts, and outputs a unified CoordinationResult.

Priority order (per spec):
    Safety > Critical Facilities > Stability > Emergency Reserve
    > Energy Balance > Peak Reduction > Cost > Trading Profit

Key rules:
  - Receives decisions from all 5 other agents.
  - Applies deterministic priority ordering.
  - Uses LLM for complex multi-agent conflict resolution reasoning.
  - Outputs approved, rejected, and modified decision lists.
"""

import json
from typing import Any

from backend.common.schemas.enums import AgentType, RiskLevel
from backend.common.schemas.microgrid_state import MicrogridState
from backend.common.schemas.messages import AgentDecision, CoordinationResult
from backend.modules.agents.base_agent import BaseAgent


# ── Priority map — higher number = higher priority ───────────────────────
_PRIORITY_MAP = {
    "safety": 100,
    "critical_facilities": 90,
    "stability": 80,
    "emergency_reserve": 70,
    "energy_balance": 60,
    "peak_reduction": 50,
    "cost": 40,
    "trading_profit": 30,
}

# Map action types to priority categories
_ACTION_CATEGORY = {
    # Critical Facility Agent
    "emergency": "critical_facilities",
    "protect": "critical_facilities",
    "reserve": "emergency_reserve",
    "normal": "stability",
    # Energy Resource Agent
    "charge": "energy_balance",
    "discharge": "energy_balance",
    "hold": "stability",
    "delay_ev": "peak_reduction",
    "use_local": "energy_balance",
    # Demand Management Agent
    "reduce": "peak_reduction",
    "shift": "peak_reduction",
    "delay": "peak_reduction",
    "pause": "peak_reduction",
    "run": "stability",
    # Market Trading Agent
    "place_bid": "trading_profit",
    "place_ask": "trading_profit",
    "cancel_order": "cost",
    "execute_trade": "trading_profit",
    # Risk Agent
    "RISK_ASSESSMENT": "safety",
}


class CoordinatorAgent(BaseAgent):
    """
    Central coordinator: collects, resolves conflicts, prioritises.
    """

    def __init__(self):
        super().__init__(
            agent_type=AgentType.COORDINATOR,
            name="Coordinator Agent",
            description=(
                "Central coordinator that collects agent recommendations, "
                "resolves conflicts using priority ordering, and coordinates "
                "battery, demand response, EVs, and P2P trading."
            ),
        )
        self._all_decisions: list[AgentDecision] = []
        self._risk_info: dict[str, Any] = {}
        self._coordination_result: CoordinationResult | None = None

    # ── Observe (collects all agent decisions) ────────────────────────────

    def observe(self, state: MicrogridState) -> dict[str, Any]:
        inputs = {
            "total_decisions": len(self._all_decisions),
            "risk_level": state.risk.risk_level.value,
            "risk_score": state.risk.risk_score,
            "energy_balance_kw": state.energy_balance_kw,
            "battery_soc": state.battery.current_soc,
            "critical_supply_ratio": (
                state.critical_facility.current_supply_kw
                / max(state.critical_facility.required_power_kw, 1.0)
            ),
        }
        self._last_inputs = inputs
        return inputs

    def set_agent_decisions(
        self,
        decisions: list[AgentDecision],
        risk_info: dict[str, Any] | None = None,
    ):
        """Called by the pipeline to inject all other agents' decisions."""
        self._all_decisions = decisions
        self._risk_info = risk_info or {}

    # ── Decide (conflict resolution) ──────────────────────────────────────

    async def decide(self, state: MicrogridState) -> list[AgentDecision]:
        if not self._all_decisions:
            self._last_reason = "No decisions to coordinate."
            self._last_expected_effect = "No action."
            self._coordination_result = CoordinationResult(
                resolution_reason="No agent decisions received."
            )
            return []

        risk_level = state.risk.risk_level.value
        is_high_risk = risk_level in (RiskLevel.HIGH.value, RiskLevel.CRITICAL.value)

        # ── 1. DETERMINISTIC PRIORITY SORTING ─────────────────────────

        scored: list[tuple[int, AgentDecision]] = []
        for d in self._all_decisions:
            category = _ACTION_CATEGORY.get(d.action, "cost")
            base_priority = _PRIORITY_MAP.get(category, 30)
            # Boost by agent-assigned priority (1-10)
            score = base_priority + d.priority
            scored.append((score, d))

        # Sort descending by priority score
        scored.sort(key=lambda x: x[0], reverse=True)

        # ── 2. CONFLICT RESOLUTION (deterministic rules) ──────────────

        approved: list[AgentDecision] = []
        rejected: list[AgentDecision] = []
        modified: list[AgentDecision] = []

        # Track resource commitments to detect conflicts
        battery_committed_kw = 0.0
        total_demand_reduction_kw = 0.0

        for score, decision in scored:
            category = _ACTION_CATEGORY.get(decision.action, "cost")

            # RULE 1: Critical facility actions always approved
            if category == "critical_facilities":
                decision.coordinator_approved = True
                approved.append(decision)
                continue

            # RULE 2: Safety / risk assessments always approved
            if category == "safety":
                decision.coordinator_approved = True
                approved.append(decision)
                continue

            # RULE 3: During HIGH risk — reject aggressive trading
            if is_high_risk and decision.action == "place_ask":
                decision.coordinator_approved = False
                rejected.append(decision)
                continue

            # RULE 4: Battery conflict — don't both charge AND discharge
            if decision.action in ("charge", "discharge"):
                kw = decision.quantity_kw or 0
                if decision.action == "discharge":
                    if battery_committed_kw < 0:
                        # Already discharging — add
                        battery_committed_kw -= kw
                    elif battery_committed_kw > 0:
                        # Conflict: someone wants charge, someone wants discharge
                        # In high risk → prefer discharge; otherwise prefer charge
                        if is_high_risk:
                            # Reject the charge, keep discharge
                            decision.coordinator_approved = True
                            approved.append(decision)
                            battery_committed_kw = -kw
                        else:
                            decision.coordinator_approved = False
                            rejected.append(decision)
                        continue
                    else:
                        battery_committed_kw = -kw
                else:  # charge
                    if battery_committed_kw > 0:
                        battery_committed_kw += kw
                    elif battery_committed_kw < 0:
                        if is_high_risk:
                            decision.coordinator_approved = False
                            rejected.append(decision)
                            continue
                        battery_committed_kw = kw
                    else:
                        battery_committed_kw = kw

                decision.coordinator_approved = True
                approved.append(decision)
                continue

            # RULE 5: Demand reduction — cap at 50% of original flexible load
            if decision.action == "reduce":
                kw = decision.quantity_kw or 0
                total_demand_reduction_kw += kw
                if total_demand_reduction_kw > state.total_demand_kw * 0.5:
                    # Too much reduction — modify to cap
                    excess = total_demand_reduction_kw - state.total_demand_kw * 0.5
                    new_kw = max(0, kw - excess)
                    if new_kw > 0:
                        decision.quantity_kw = round(new_kw, 2)
                        decision.reason += " [MODIFIED by Coordinator: capped reduction]"
                        decision.coordinator_approved = True
                        modified.append(decision)
                    else:
                        decision.coordinator_approved = False
                        rejected.append(decision)
                    continue

            # DEFAULT: approve
            decision.coordinator_approved = True
            approved.append(decision)

        # ── 3. LLM REASONING (optional — for complex conflicts) ──────

        resolution_reason = (
            f"Coordinated {len(self._all_decisions)} decisions: "
            f"{len(approved)} approved, {len(rejected)} rejected, "
            f"{len(modified)} modified. Risk={risk_level}."
        )

        if rejected or modified:
            llm_result = await self._call_llm(
                system_prompt=(
                    "You are the central coordinator for a community microgrid. "
                    "You resolved conflicts between agent decisions using priority: "
                    "Safety > Critical Facilities > Stability > Emergency Reserve "
                    "> Energy Balance > Peak Reduction > Cost > Trading Profit. "
                    "Explain the resolution concisely. Respond in JSON with keys: "
                    "resolution_reason (string)."
                ),
                user_message=json.dumps({
                    "risk_level": risk_level,
                    "total_decisions": len(self._all_decisions),
                    "approved_actions": [d.action for d in approved],
                    "rejected_actions": [d.action for d in rejected],
                    "modified_actions": [d.action for d in modified],
                }),
            )
            if llm_result:
                resolution_reason = llm_result.get(
                    "resolution_reason", resolution_reason
                )

        # ── 4. BUILD RESULT ───────────────────────────────────────────

        self._coordination_result = CoordinationResult(
            approved_decisions=approved,
            rejected_decisions=rejected,
            modified_decisions=modified,
            resolution_reason=resolution_reason,
            priorities={k: v for k, v in _PRIORITY_MAP.items()},
        )

        self._last_reason = resolution_reason
        self._last_expected_effect = (
            f"{len(approved)} decisions will execute. "
            f"{len(rejected)} blocked for safety/conflict."
        )
        self._last_decisions = approved

        return approved

    @property
    def coordination_result(self) -> CoordinationResult | None:
        return self._coordination_result
