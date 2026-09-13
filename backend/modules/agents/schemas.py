"""
GridMind — Agent Module Schemas
=================================
Pydantic request/response models for the /api/agents routes.
"""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from backend.common.schemas.enums import AgentType, AgentStatus, RiskLevel
from backend.common.schemas.messages import AgentDecision, CoordinationResult
from backend.common.schemas.microgrid_state import MicrogridState
from backend.modules.safety.schemas import SafetyValidationResult


# ══════════════════════════════════════════════════════════════════════════
#  STATUS
# ══════════════════════════════════════════════════════════════════════════


class AgentStatusItem(BaseModel):
    """Status of a single agent."""
    agent_type: str
    name: str
    status: str
    description: str = ""
    last_decisions_count: int = 0
    llm_available: bool = False


class AgentStatusResponse(BaseModel):
    """Response for GET /api/agents/status."""
    agents: list[AgentStatusItem] = Field(default_factory=list)
    total_agents: int = 0
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ══════════════════════════════════════════════════════════════════════════
#  RUN AGENTS (the main pipeline endpoint)
# ══════════════════════════════════════════════════════════════════════════


class RunAgentsRequest(BaseModel):
    """Request body for POST /api/agents/run."""
    state: MicrogridState


class AgentResult(BaseModel):
    """Result from a single agent's run."""
    agent_type: str
    decisions: list[AgentDecision] = Field(default_factory=list)
    reasoning: str = ""
    status: str = "success"


class RunAgentsResponse(BaseModel):
    """Response for POST /api/agents/run — full pipeline result."""
    success: bool = True
    agent_results: list[AgentResult] = Field(default_factory=list)
    coordination: CoordinationResult | None = None
    safety_result: SafetyValidationResult | None = None
    risk_level: str = "low"
    risk_score: float = 0.0
    total_decisions: int = 0
    approved_decisions: int = 0
    rejected_decisions: int = 0
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ══════════════════════════════════════════════════════════════════════════
#  EXPLANATION
# ══════════════════════════════════════════════════════════════════════════


class AgentExplanationResponse(BaseModel):
    """Response for GET /api/agents/{agent_type}/explain."""
    agent_type: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    decisions: list[AgentDecision] = Field(default_factory=list)
    reason: str = ""
    expected_effect: str = ""
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ══════════════════════════════════════════════════════════════════════════
#  DECISIONS
# ══════════════════════════════════════════════════════════════════════════


class AgentDecisionsResponse(BaseModel):
    """Response for GET /api/agents/{agent_type}/decisions."""
    agent_type: str
    decisions: list[AgentDecision] = Field(default_factory=list)
    total: int = 0
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
