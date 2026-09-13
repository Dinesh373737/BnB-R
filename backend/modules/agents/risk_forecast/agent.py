"""
GridMind — ⚠️ Risk & Forecast Agent
=======================================
Consumes Module 2 ML predictions from MicrogridState.
Computes risk score DETERMINISTICALLY.
Uses LLM ONLY for interpreting complex multi-factor situations.

Does NOT do forecasting — it interprets forecasts from the ML module.
"""

import json
from typing import Any

from backend.common.schemas.enums import AgentType, RiskLevel
from backend.common.schemas.microgrid_state import MicrogridState
from backend.common.schemas.messages import AgentDecision
from backend.modules.agents.base_agent import BaseAgent


class RiskForecastAgent(BaseAgent):
    """Evaluates system risk based on forecasts and current state."""

    def __init__(self):
        super().__init__(
            agent_type=AgentType.RISK_FORECAST,
            name="Risk & Forecast Agent",
            description=(
                "Interprets demand/solar/wind forecasts, evaluates uncertainty, "
                "detects demand spikes and renewable drops, produces risk assessment."
            ),
        )

    # ── Observe ───────────────────────────────────────────────────────────

    def observe(self, state: MicrogridState) -> dict[str, Any]:
        total_demand = state.total_demand_kw
        total_gen = state.total_generation_kw
        solar = state.solar.current_output_kw
        solar_cap = state.solar.capacity_kw
        wind = state.wind.current_output_kw
        wind_cap = state.wind.capacity_kw
        battery_soc = state.battery.current_soc
        forecast = state.forecast
        grid_connected = state.grid_connection.is_connected

        # Derived signals
        supply_demand_ratio = total_gen / max(total_demand, 1.0)
        solar_utilization = solar / max(solar_cap, 1.0)
        wind_utilization = wind / max(wind_cap, 1.0)
        energy_balance = state.energy_balance_kw

        inputs = {
            "total_demand_kw": total_demand,
            "total_generation_kw": total_gen,
            "solar_output_kw": solar,
            "solar_capacity_kw": solar_cap,
            "solar_utilization": round(solar_utilization, 3),
            "wind_output_kw": wind,
            "wind_capacity_kw": wind_cap,
            "wind_utilization": round(wind_utilization, 3),
            "battery_soc": battery_soc,
            "energy_balance_kw": energy_balance,
            "supply_demand_ratio": round(supply_demand_ratio, 3),
            "grid_connected": grid_connected,
            "demand_forecast_kw": forecast.demand_forecast_kw,
            "solar_forecast_kw": forecast.solar_forecast_kw,
            "wind_forecast_kw": forecast.wind_forecast_kw,
            "uncertainty_level": forecast.uncertainty_level,
            "critical_required_kw": state.critical_facility.required_power_kw,
            "critical_supply_kw": state.critical_facility.current_supply_kw,
        }
        self._last_inputs = inputs
        return inputs

    # ── Decide (deterministic risk scoring + optional LLM reasoning) ──────

    async def decide(self, state: MicrogridState) -> list[AgentDecision]:
        inputs = self._last_inputs

        # ── 1. DETERMINISTIC RISK SCORING ─────────────────────────────
        risk_score = 0.0
        drivers: list[str] = []
        recommended_actions: list[str] = []

        # Supply-demand imbalance
        ratio = inputs["supply_demand_ratio"]
        if ratio < 0.5:
            risk_score += 35
            drivers.append("energy_shortage")
            recommended_actions.extend(["preserve_battery", "reduce_flexible_load"])
        elif ratio < 0.75:
            risk_score += 20
            drivers.append("supply_demand_imbalance")
            recommended_actions.append("reduce_flexible_load")
        elif ratio < 0.9:
            risk_score += 10
            drivers.append("supply_demand_imbalance")

        # Solar drop
        solar_util = inputs["solar_utilization"]
        if solar_util < 0.2 and inputs["solar_capacity_kw"] > 0:
            risk_score += 20
            drivers.append("solar_decline")
            recommended_actions.append("preserve_battery")
        elif solar_util < 0.5 and inputs["solar_capacity_kw"] > 0:
            risk_score += 10
            drivers.append("solar_decline")

        # Wind drop
        wind_util = inputs["wind_utilization"]
        if wind_util < 0.15 and inputs["wind_capacity_kw"] > 0:
            risk_score += 15
            drivers.append("wind_decline")
        elif wind_util < 0.4 and inputs["wind_capacity_kw"] > 0:
            risk_score += 8
            drivers.append("wind_decline")

        # Battery low
        soc = inputs["battery_soc"]
        if soc < 0.15:
            risk_score += 20
            drivers.append("battery_shortage")
            recommended_actions.append("preserve_battery")
        elif soc < 0.30:
            risk_score += 10
            drivers.append("battery_shortage")

        # Grid outage
        if not inputs["grid_connected"]:
            risk_score += 25
            drivers.append("grid_outage")
            recommended_actions.extend([
                "preserve_battery", "reduce_flexible_load", "delay_ev_charging"
            ])

        # Critical facility threat
        crit_req = inputs["critical_required_kw"]
        crit_sup = inputs["critical_supply_kw"]
        if crit_req > 0 and crit_sup < crit_req * 0.8:
            risk_score += 15
            drivers.append("critical_load_threat")
            recommended_actions.append("protect_critical_facilities")

        # Forecast uncertainty
        if inputs["uncertainty_level"] == "high":
            risk_score += 10
            drivers.append("high_forecast_uncertainty")

        # Demand forecast spike
        demand_fc = inputs.get("demand_forecast_kw")
        if demand_fc and demand_fc > inputs["total_demand_kw"] * 1.25:
            risk_score += 12
            drivers.append("demand_increase")
            recommended_actions.append("reduce_flexible_load")

        # Clamp to [0, 100]
        risk_score = min(100.0, max(0.0, risk_score))

        # Map score → level
        if risk_score >= 80:
            risk_level = RiskLevel.CRITICAL
        elif risk_score >= 55:
            risk_level = RiskLevel.HIGH
        elif risk_score >= 30:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        # Deduplicate recommended_actions
        recommended_actions = list(dict.fromkeys(recommended_actions))

        # ── 2. LLM REASONING (optional — for explanation only) ────────
        reason = (
            f"Risk score {risk_score:.0f}/100 ({risk_level.value}). "
            f"Drivers: {', '.join(drivers) if drivers else 'none'}."
        )
        expected_effect = "System awareness of current risk posture."

        if risk_score >= 40:
            llm_result = await self._call_llm(
                system_prompt=(
                    "You are a microgrid risk analyst. Given the current microgrid "
                    "observations, provide a concise risk assessment. Respond in JSON "
                    "with keys: reason (string), expected_effect (string), "
                    "additional_recommendations (list of strings)."
                ),
                user_message=json.dumps(inputs),
            )
            if llm_result:
                reason = llm_result.get("reason", reason)
                expected_effect = llm_result.get("expected_effect", expected_effect)
                extra = llm_result.get("additional_recommendations", [])
                recommended_actions.extend(extra)
                recommended_actions = list(dict.fromkeys(recommended_actions))

        self._last_reason = reason
        self._last_expected_effect = expected_effect

        # ── 3. BUILD DECISION ─────────────────────────────────────────
        decision = self._make_decision(
            action="RISK_ASSESSMENT",
            resource="system",
            reason=reason,
            expected_effect=expected_effect,
            confidence=min(1.0, 0.6 + (risk_score / 200)),
            priority=min(10, max(1, int(risk_score / 10))),
        )
        # Attach risk metadata as extra fields via the existing schema
        decision.quantity_kwh = risk_score  # overload: risk_score in quantity_kwh

        # Store enriched info for other agents / coordinator
        self._risk_output = {
            "risk_score": risk_score,
            "risk_level": risk_level.value,
            "drivers": drivers,
            "recommended_actions": recommended_actions,
        }

        return [decision]

    # ── Public accessor for coordinator / other agents ─────────────────

    @property
    def risk_output(self) -> dict[str, Any]:
        return getattr(self, "_risk_output", {
            "risk_score": 0,
            "risk_level": "low",
            "drivers": [],
            "recommended_actions": [],
        })
