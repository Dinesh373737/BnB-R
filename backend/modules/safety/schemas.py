from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from backend.common.schemas.enums import RiskLevel, SafetyStatus
from backend.common.schemas.messages import AgentDecision


class SafetyDecisionOutcome(BaseModel):
    """Per-decision outcome used during validation."""

    status: SafetyStatus = SafetyStatus.APPROVED
    risk_level: RiskLevel = RiskLevel.LOW
    original_decision: AgentDecision | None = None
    safe_decision: AgentDecision | None = None
    reason: str = ""
    rule: str = ""
    limit: float | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class SafetyValidationResult(BaseModel):
    """Aggregated safety validation response."""

    overall_status: SafetyStatus = SafetyStatus.APPROVED
    approved_decisions: list[AgentDecision] = Field(default_factory=list)
    modified_decisions: list[AgentDecision] = Field(default_factory=list)
    rejected_decisions: list[AgentDecision] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    reasons: list[str] = Field(default_factory=list)
    violations: list[str] = Field(default_factory=list)
    validation_details: list[SafetyDecisionOutcome] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SafetyValidationRequest(BaseModel):
    """HTTP request for validating a microgrid state against agent decisions."""

    state: Any | None = None
    decisions: list[AgentDecision] = Field(default_factory=list)
    simulation_run_id: int | None = None
    timestep: int | None = None
