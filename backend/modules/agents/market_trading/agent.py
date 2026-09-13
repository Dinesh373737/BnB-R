"""
GridMind — 💰 Market & Trading Agent
=========================================
Handles P2P energy trading strategy.

Key rules:
  - Decides buy/sell/hold based on surplus, risk, reserves, price.
  - Generates bids/offers with deterministic price/quantity.
  - The Market Engine (Module 4) does actual matching/clearing — NOT this agent.
  - LLM is used for trading strategy reasoning.
"""

import json
from typing import Any

from backend.common.schemas.enums import AgentType, RiskLevel
from backend.common.schemas.microgrid_state import MicrogridState
from backend.common.schemas.messages import AgentDecision
from backend.modules.agents.base_agent import BaseAgent


class MarketTradingAgent(BaseAgent):
    """P2P energy trading strategy agent."""

    def __init__(self):
        super().__init__(
            agent_type=AgentType.MARKET_TRADING,
            name="Market & Trading Agent",
            description=(
                "Decides buy/sell strategy, generates P2P bids/offers, "
                "considers price, risk, reserves, and local supply/demand."
            ),
        )

    # ── Observe ───────────────────────────────────────────────────────────

    def observe(self, state: MicrogridState) -> dict[str, Any]:
        inputs = {
            "energy_balance_kw": state.energy_balance_kw,
            "total_demand_kw": state.total_demand_kw,
            "total_generation_kw": state.total_generation_kw,
            "battery_soc": state.battery.current_soc,
            "battery_min_soc": state.battery.min_soc,
            "battery_energy_available_kwh": state.battery.energy_available_kwh,
            "risk_level": state.risk.risk_level.value,
            "risk_score": state.risk.risk_score,
            "grid_price_per_kwh": state.grid_connection.electricity_price_per_kwh,
            "grid_connected": state.grid_connection.is_connected,
            "market_active": state.market.is_active,
            "market_last_clearing_price": state.market.last_clearing_price,
            "market_active_bids": state.market.active_bids,
            "market_active_asks": state.market.active_asks,
            "renewable_pct": state.renewable_percentage,
        }
        self._last_inputs = inputs
        return inputs

    # ── Decide ────────────────────────────────────────────────────────────

    async def decide(self, state: MicrogridState) -> list[AgentDecision]:
        inputs = self._last_inputs
        decisions: list[AgentDecision] = []

        if not inputs["market_active"]:
            self._last_reason = "P2P market is inactive."
            self._last_expected_effect = "No trading activity."
            return decisions

        risk_level = inputs["risk_level"]
        is_high_risk = risk_level in (RiskLevel.HIGH.value, RiskLevel.CRITICAL.value)
        energy_balance = inputs["energy_balance_kw"]
        grid_price = inputs["grid_price_per_kwh"]
        last_clearing = inputs["market_last_clearing_price"]
        soc = inputs["battery_soc"]

        # Reference price: use last clearing price or grid price
        ref_price = last_clearing if last_clearing > 0 else grid_price

        # ── 1. TRADING STRATEGY (deterministic) ──────────────────────

        if is_high_risk:
            # HIGH RISK: conservative — only buy if desperate, don't sell reserves
            if energy_balance < 0 and soc < 0.30:
                # Need energy urgently — place a buy bid at premium
                buy_kw = min(abs(energy_balance) * 0.5, 100.0)
                buy_price = round(ref_price * 1.15, 2)  # Willing to pay 15% premium
                decisions.append(self._make_decision(
                    action="place_bid",
                    resource="p2p_market",
                    quantity_kw=round(buy_kw, 2),
                    reason=f"High risk + deficit + low battery. Bidding for {buy_kw:.1f} kW at ₹{buy_price}/kWh.",
                    expected_effect="Secure additional energy from P2P market.",
                    confidence=0.80,
                    priority=7,
                ))
                decisions[-1].quantity_kwh = buy_price  # Store price in kwh field
            else:
                # High risk but stable — HOLD, don't trade
                decisions.append(self._make_decision(
                    action="hold",
                    resource="p2p_market",
                    reason=f"Risk level {risk_level}. Holding — preserving reserves.",
                    expected_effect="Reserves protected during high-risk period.",
                    confidence=0.95,
                    priority=6,
                ))

        elif energy_balance > 50:
            # SURPLUS: sell excess on P2P market
            # Keep some headroom — sell at most 70% of surplus
            sell_kw = round(energy_balance * 0.70, 2)
            # Price slightly below grid for competitive advantage
            sell_price = round(ref_price * 0.92, 2)

            decisions.append(self._make_decision(
                action="place_ask",
                resource="p2p_market",
                quantity_kw=sell_kw,
                reason=(
                    f"Surplus {energy_balance:.1f} kW. Selling {sell_kw:.1f} kW "
                    f"at ₹{sell_price}/kWh (grid=₹{grid_price}/kWh)."
                ),
                expected_effect=f"Generate revenue of ~₹{sell_kw * sell_price:.0f}.",
                confidence=0.85,
                priority=4,
            ))
            decisions[-1].quantity_kwh = sell_price  # Store price

        elif energy_balance < -20:
            # DEFICIT: buy from P2P market (cheaper than grid)
            buy_kw = min(abs(energy_balance) * 0.60, 200.0)
            buy_price = round(ref_price * 0.98, 2)  # Slightly below grid price

            decisions.append(self._make_decision(
                action="place_bid",
                resource="p2p_market",
                quantity_kw=round(buy_kw, 2),
                reason=(
                    f"Deficit {abs(energy_balance):.1f} kW. Bidding for {buy_kw:.1f} kW "
                    f"at ₹{buy_price}/kWh (cheaper than grid ₹{grid_price}/kWh)."
                ),
                expected_effect=f"Reduce grid import cost, save ~₹{(grid_price - buy_price) * buy_kw:.0f}.",
                confidence=0.80,
                priority=5,
            ))
            decisions[-1].quantity_kwh = buy_price

        else:
            # Balanced — hold
            decisions.append(self._make_decision(
                action="hold",
                resource="p2p_market",
                reason="Energy roughly balanced. No trading needed.",
                expected_effect="Stable operations, no market activity.",
                confidence=0.90,
                priority=3,
            ))

        # ── 2. LLM STRATEGY (optional) ───────────────────────────────

        reason = "; ".join(d.reason for d in decisions)
        effect = "; ".join(d.expected_effect for d in decisions)

        if is_high_risk or abs(energy_balance) > inputs["total_demand_kw"] * 0.3:
            llm_result = await self._call_llm(
                system_prompt=(
                    "You are a P2P energy market trading strategist for a community "
                    "microgrid. Given the state and trading decisions, provide strategic "
                    "reasoning. The Market Engine handles actual order matching — you "
                    "only advise. Respond in JSON with keys: reason (string), "
                    "expected_effect (string)."
                ),
                user_message=json.dumps({
                    "observations": inputs,
                    "decisions": [d.action for d in decisions],
                }),
            )
            if llm_result:
                reason = llm_result.get("reason", reason)
                effect = llm_result.get("expected_effect", effect)

        self._last_reason = reason
        self._last_expected_effect = effect

        return decisions
