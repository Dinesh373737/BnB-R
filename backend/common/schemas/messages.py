"""
GridMind — Agent Message Schemas
===================================
Structured message formats for agent-to-agent and agent-to-coordinator
communication. Per the doc: use STRUCTURED messages, not natural language.

Usage:
    from backend.common.schemas.messages import AgentMessage, AgentDecision

    msg = AgentMessage(
        sender=AgentType.RISK_FORECAST,
        message_type=MessageType.RISK_UPDATE,
        payload={"risk_score": 82, "risk_level": "high"}
    )
"""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from backend.common.schemas.enums import (
    AgentType,
    SafetyStatus,
)


# ══════════════════════════════════════════════════════════════════════════
#  MESSAGE TYPES
# ══════════════════════════════════════════════════════════════════════════


class MessageType:
    """
    Standard message type constants.
    Used as the `message_type` field in AgentMessage.
    """
    # Risk & Forecast Agent
    RISK_UPDATE = "RISK_UPDATE"
    FORECAST_UPDATE = "FORECAST_UPDATE"

    # Energy Resource Agent
    RESOURCE_ACTION = "RESOURCE_ACTION"
    RESOURCE_STATUS = "RESOURCE_STATUS"

    # Demand Management Agent
    DEMAND_ACTION = "DEMAND_ACTION"
    DEMAND_STATUS = "DEMAND_STATUS"

    # Market & Trading Agent
    MARKET_ORDER = "MARKET_ORDER"
    TRADE_EXECUTED = "TRADE_EXECUTED"
    MARKET_STATUS = "MARKET_STATUS"

    # Critical Facility Agent
    CRITICAL_STATUS = "CRITICAL_STATUS"
    CRITICAL_ACTION = "CRITICAL_ACTION"

    # Coordinator
    COORDINATION_REQUEST = "COORDINATION_REQUEST"
    COORDINATION_RESULT = "COORDINATION_RESULT"
    CONFLICT_RESOLUTION = "CONFLICT_RESOLUTION"

    # Safety
    SAFETY_CHECK_REQUEST = "SAFETY_CHECK_REQUEST"
    SAFETY_CHECK_RESULT = "SAFETY_CHECK_RESULT"

    # System
    STATE_UPDATE = "STATE_UPDATE"
    HEARTBEAT = "HEARTBEAT"


# ══════════════════════════════════════════════════════════════════════════
#  CORE MESSAGE SCHEMA
# ══════════════════════════════════════════════════════════════════════════


class AgentMessage(BaseModel):
    """
    Structured message between agents.
    This is the universal communication format.

    Example:
        {
            "sender": "risk_forecast",
            "receiver": "coordinator",
            "message_type": "RISK_UPDATE",
            "payload": {
                "risk_score": 82,
                "risk_level": "high",
                "drivers": ["solar_decline", "demand_increase"]
            }
        }
    """
    sender: AgentType
    receiver: AgentType | None = None      # None = broadcast to all
    message_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    priority: int = Field(default=5, ge=1, le=10)  # 1=lowest, 10=highest
    simulation_run_id: int | None = None
    timestep: int | None = None


# ══════════════════════════════════════════════════════════════════════════
#  AGENT DECISION SCHEMA
# ══════════════════════════════════════════════════════════════════════════


class AgentDecision(BaseModel):
    """
    A decision made by an agent.
    Sent to the Coordinator for conflict resolution, then to Safety for validation.

    Example:
        {
            "agent": "energy_resource",
            "action": "DISCHARGE",
            "resource": "battery_01",
            "quantity_kwh": 4.2,
            "reason": "HIGH_RISK_UPCOMING_PEAK",
            "expected_effect": "Reduce grid dependency"
        }
    """
    agent: AgentType
    action: str                             # From ResourceAction, DemandAction, etc.
    resource: str = ""                      # Target resource/entity
    quantity_kwh: float | None = None
    quantity_kw: float | None = None
    duration_minutes: float | None = None
    reason: str = ""
    expected_effect: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    priority: int = Field(default=5, ge=1, le=10)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    safety_status: SafetyStatus | None = None
    coordinator_approved: bool | None = None


# ══════════════════════════════════════════════════════════════════════════
#  COORDINATION RESULT
# ══════════════════════════════════════════════════════════════════════════


class CoordinationResult(BaseModel):
    """
    Result of the Coordinator Agent resolving conflicts between agents.

    Example:
        Coordinator receives:
          - Market Agent: "Sell 20 kWh"
          - Energy Resource: "Reserve battery"
          - Critical Facility: "Need reserve"
          - Risk: "HIGH"

        Coordinator outputs:
          - Reject aggressive selling
          - Reserve critical energy
          - Trade only remaining surplus
    """
    approved_decisions: list[AgentDecision] = Field(default_factory=list)
    rejected_decisions: list[AgentDecision] = Field(default_factory=list)
    modified_decisions: list[AgentDecision] = Field(default_factory=list)
    resolution_reason: str = ""
    priorities: dict[str, int] = Field(default_factory=dict)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ══════════════════════════════════════════════════════════════════════════
#  SAFETY VALIDATION REQUEST / RESULT
# ══════════════════════════════════════════════════════════════════════════


class SafetyCheckRequest(BaseModel):
    """Request to validate a set of coordinated decisions."""
    decisions: list[AgentDecision]
    simulation_run_id: int | None = None
    timestep: int | None = None


class SafetyCheckResult(BaseModel):
    """Result of safety validation."""
    overall_status: SafetyStatus = SafetyStatus.APPROVED
    approved_decisions: list[AgentDecision] = Field(default_factory=list)
    rejected_decisions: list[AgentDecision] = Field(default_factory=list)
    violations: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ══════════════════════════════════════════════════════════════════════════
#  AGENT EXPLAINABILITY
# ══════════════════════════════════════════════════════════════════════════


class AgentExplanation(BaseModel):
    """
    Explainability output for an agent's decision.
    Per the doc: user can click any agent and see state, inputs,
    decision, reason, and expected effect.
    """
    agent: AgentType
    current_state: dict[str, Any] = Field(default_factory=dict)
    inputs: dict[str, Any] = Field(default_factory=dict)
    decision: AgentDecision | None = None
    reason: str = ""
    expected_effect: str = ""
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
