"""
GridMind — Module 6: Agent Router
====================================
FastAPI routes for the Agentic AI layer.

Endpoints:
    GET  /api/agents/status              — All agent statuses
    POST /api/agents/run                 — Run the full agent pipeline
    GET  /api/agents/{agent_type}/explain — Agent explanation
    GET  /api/agents/{agent_type}/decisions — Recent agent decisions
"""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from backend.common.logger import get_module_logger
from backend.common.schemas.enums import AgentType
from backend.common.schemas.microgrid_state import MicrogridState
from backend.common.schemas.messages import CoordinationResult
from backend.modules.safety.service import SafetyService

from backend.modules.agents.schemas import (
    AgentStatusItem,
    AgentStatusResponse,
    RunAgentsRequest,
    RunAgentsResponse,
    AgentResult,
    AgentExplanationResponse,
    AgentDecisionsResponse,
)

# ── Agent imports ─────────────────────────────────────────────────────────
from backend.modules.agents.risk_forecast.agent import RiskForecastAgent
from backend.modules.agents.energy_resource.agent import EnergyResourceAgent
from backend.modules.agents.demand_management.agent import DemandManagementAgent
from backend.modules.agents.market_trading.agent import MarketTradingAgent
from backend.modules.agents.critical_facility.agent import CriticalFacilityAgent
from backend.modules.agents.coordinator.agent import CoordinatorAgent

log = get_module_logger("agents.router")

router = APIRouter()

# ══════════════════════════════════════════════════════════════════════════
#  AGENT SINGLETONS
# ══════════════════════════════════════════════════════════════════════════

risk_agent = RiskForecastAgent()
energy_agent = EnergyResourceAgent()
demand_agent = DemandManagementAgent()
market_agent = MarketTradingAgent()
critical_agent = CriticalFacilityAgent()
coordinator_agent = CoordinatorAgent()
safety_service = SafetyService()

_AGENTS = {
    AgentType.RISK_FORECAST: risk_agent,
    AgentType.ENERGY_RESOURCE: energy_agent,
    AgentType.DEMAND_MANAGEMENT: demand_agent,
    AgentType.MARKET_TRADING: market_agent,
    AgentType.CRITICAL_FACILITY: critical_agent,
    AgentType.COORDINATOR: coordinator_agent,
}


# ══════════════════════════════════════════════════════════════════════════
#  GET /api/agents/status
# ══════════════════════════════════════════════════════════════════════════


@router.get("/agents/status", response_model=AgentStatusResponse, tags=["Agents"])
def get_agent_status():
    """List all 6 agents and their current status."""
    items = [
        AgentStatusItem(**agent.get_status_dict())
        for agent in _AGENTS.values()
    ]
    return AgentStatusResponse(
        agents=items,
        total_agents=len(items),
    )


# ══════════════════════════════════════════════════════════════════════════
#  POST /api/agents/run
# ══════════════════════════════════════════════════════════════════════════


@router.post("/agents/run", response_model=RunAgentsResponse, tags=["Agents"])
async def run_agent_pipeline(request: RunAgentsRequest):
    """
    Run the full agent pipeline for a given MicrogridState.

    Pipeline order (per spec):
        1. Risk & Forecast Agent  → risk assessment
        2. Energy Resource Agent  → battery/solar/wind/EV decisions
        3. Demand Management Agent → load reduction/shifting
        4. Market & Trading Agent → P2P trading strategy
        5. Critical Facility Agent → protection decisions
        6. Coordinator Agent      → conflict resolution
    """
    state = request.state
    agent_results: list[AgentResult] = []
    all_decisions = []

    try:
        # ── Step 1: Risk Assessment ───────────────────────────────────
        log.info("Pipeline step 1/6: Risk & Forecast Agent")
        risk_decisions = await risk_agent.run(state)
        risk_info = risk_agent.risk_output
        agent_results.append(AgentResult(
            agent_type=AgentType.RISK_FORECAST.value,
            decisions=risk_decisions,
            reasoning=risk_agent._last_reason,
        ))

        # Inject risk into state for downstream agents
        state.risk.risk_score = risk_info.get("risk_score", 0)
        risk_level_str = risk_info.get("risk_level", "low")
        from backend.common.schemas.enums import RiskLevel
        state.risk.risk_level = RiskLevel(risk_level_str)
        state.risk.drivers = risk_info.get("drivers", [])

        # ── Step 2: Energy Resource Agent ─────────────────────────────
        log.info("Pipeline step 2/6: Energy Resource Agent")
        energy_decisions = await energy_agent.run(state)
        all_decisions.extend(energy_decisions)
        agent_results.append(AgentResult(
            agent_type=AgentType.ENERGY_RESOURCE.value,
            decisions=energy_decisions,
            reasoning=energy_agent._last_reason,
        ))

        # ── Step 3: Demand Management Agent ───────────────────────────
        log.info("Pipeline step 3/6: Demand Management Agent")
        demand_decisions = await demand_agent.run(state)
        all_decisions.extend(demand_decisions)
        agent_results.append(AgentResult(
            agent_type=AgentType.DEMAND_MANAGEMENT.value,
            decisions=demand_decisions,
            reasoning=demand_agent._last_reason,
        ))

        # ── Step 4: Market & Trading Agent ────────────────────────────
        log.info("Pipeline step 4/6: Market & Trading Agent")
        market_decisions = await market_agent.run(state)
        all_decisions.extend(market_decisions)
        agent_results.append(AgentResult(
            agent_type=AgentType.MARKET_TRADING.value,
            decisions=market_decisions,
            reasoning=market_agent._last_reason,
        ))

        # ── Step 5: Critical Facility Agent ───────────────────────────
        log.info("Pipeline step 5/6: Critical Facility Agent")
        critical_decisions = await critical_agent.run(state)
        all_decisions.extend(critical_decisions)
        agent_results.append(AgentResult(
            agent_type=AgentType.CRITICAL_FACILITY.value,
            decisions=critical_decisions,
            reasoning=critical_agent._last_reason,
        ))

        # ── Step 6: Coordinator — conflict resolution ─────────────────
        log.info("Pipeline step 6/6: Coordinator Agent")
        coordinator_agent.set_agent_decisions(all_decisions, risk_info)
        approved = await coordinator_agent.run(state)
        coord_result = coordinator_agent.coordination_result

        agent_results.append(AgentResult(
            agent_type=AgentType.COORDINATOR.value,
            decisions=approved,
            reasoning=coordinator_agent._last_reason,
        ))

        safe_validation = safety_service.validate(state, approved)
        approved = safe_validation.approved_decisions
        rejected = safe_validation.rejected_decisions
        modified = safe_validation.modified_decisions

        if coord_result is not None:
            coord_result.approved_decisions = approved
            coord_result.rejected_decisions = rejected
            coord_result.modified_decisions = modified
            coord_result.resolution_reason = (
                coord_result.resolution_reason
                + f" Safety validation: {safe_validation.overall_status.value}."
            )

        log.info(
            f"Pipeline complete: {len(all_decisions)} total decisions, "
            f"{len(approved)} approved, "
            f"{len(rejected)} rejected, "
            f"{len(modified)} modified"
        )

        return RunAgentsResponse(
            success=True,
            agent_results=agent_results,
            coordination=coord_result,
            safety_result=safe_validation,
            risk_level=risk_info.get("risk_level", "low"),
            risk_score=risk_info.get("risk_score", 0),
            total_decisions=len(all_decisions),
            approved_decisions=len(approved),
            rejected_decisions=len(rejected),
        )

    except Exception as e:
        log.error(f"Agent pipeline failed: {e}")
        raise HTTPException(status_code=500, detail=f"Agent pipeline error: {str(e)}")


# ══════════════════════════════════════════════════════════════════════════
#  GET /api/agents/{agent_type}/explain
# ══════════════════════════════════════════════════════════════════════════


@router.get(
    "/agents/{agent_type}/explain",
    response_model=AgentExplanationResponse,
    tags=["Agents"],
)
def get_agent_explanation(agent_type: str):
    """Get the latest explanation from a specific agent."""
    try:
        at = AgentType(agent_type)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown agent type: {agent_type}. "
                   f"Valid: {[a.value for a in AgentType]}",
        )

    agent = _AGENTS.get(at)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_type} not found.")

    explanation = agent.explain()
    return AgentExplanationResponse(
        agent_type=at.value,
        inputs=explanation.inputs,
        decisions=agent._last_decisions,
        reason=explanation.reason,
        expected_effect=explanation.expected_effect,
    )


# ══════════════════════════════════════════════════════════════════════════
#  GET /api/agents/{agent_type}/decisions
# ══════════════════════════════════════════════════════════════════════════


@router.get(
    "/agents/{agent_type}/decisions",
    response_model=AgentDecisionsResponse,
    tags=["Agents"],
)
def get_agent_decisions(agent_type: str):
    """Get recent decisions from a specific agent."""
    try:
        at = AgentType(agent_type)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown agent type: {agent_type}.",
        )

    agent = _AGENTS.get(at)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_type} not found.")

    return AgentDecisionsResponse(
        agent_type=at.value,
        decisions=agent._last_decisions,
        total=len(agent._last_decisions),
    )
