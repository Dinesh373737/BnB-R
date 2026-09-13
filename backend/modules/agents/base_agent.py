"""
GridMind — Abstract Base Agent
================================
All 6 agents inherit from this class.

Lifecycle:  observe(state) → decide(state) → explain()

Key design:
  - Deterministic logic handles ALL numerical calculations.
  - LLM is called ONLY for reasoning, strategy, and explanations.
  - If the LLM is unavailable, agents still function via deterministic fallback.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from backend.common.logger import get_module_logger
from backend.common.schemas.enums import AgentType, AgentStatus
from backend.common.schemas.microgrid_state import MicrogridState
from backend.common.schemas.messages import AgentDecision, AgentExplanation
from backend.modules.agents.llm_service import llm_service


class BaseAgent(ABC):
    """Abstract base class for all GridMind agents."""

    def __init__(self, agent_type: AgentType, name: str, description: str = ""):
        self.agent_type = agent_type
        self.name = name
        self.description = description
        self.status: AgentStatus = AgentStatus.IDLE
        self.log = get_module_logger(f"agents.{agent_type.value}")

        # Latest context — populated by observe/decide
        self._last_state: MicrogridState | None = None
        self._last_inputs: dict[str, Any] = {}
        self._last_decisions: list[AgentDecision] = []
        self._last_reason: str = ""
        self._last_expected_effect: str = ""

    # ══════════════════════════════════════════════════════════════════════
    #  PUBLIC INTERFACE
    # ══════════════════════════════════════════════════════════════════════

    async def run(self, state: MicrogridState) -> list[AgentDecision]:
        """
        Full agent lifecycle: observe → decide.
        Returns a list of AgentDecision objects.
        """
        try:
            self.status = AgentStatus.OBSERVING
            self._last_state = state
            self._last_inputs = self.observe(state)

            self.status = AgentStatus.DECIDING
            self._last_decisions = await self.decide(state)

            self.status = AgentStatus.IDLE
            self.log.info(
                f"Agent {self.name} produced {len(self._last_decisions)} decision(s)"
            )
            return self._last_decisions

        except Exception as e:
            self.status = AgentStatus.ERROR
            self.log.error(f"Agent {self.name} failed: {e}")
            return []

    def explain(self) -> AgentExplanation:
        """Return the latest explainability data for this agent."""
        return AgentExplanation(
            agent=self.agent_type,
            current_state=self._last_state.model_dump() if self._last_state else {},
            inputs=self._last_inputs,
            decision=self._last_decisions[0] if self._last_decisions else None,
            reason=self._last_reason,
            expected_effect=self._last_expected_effect,
            timestamp=datetime.now(timezone.utc),
        )

    def get_status_dict(self) -> dict[str, Any]:
        """Serialisable status summary."""
        return {
            "agent_type": self.agent_type.value,
            "name": self.name,
            "status": self.status.value,
            "description": self.description,
            "last_decisions_count": len(self._last_decisions),
            "llm_available": llm_service.is_available,
        }

    # ══════════════════════════════════════════════════════════════════════
    #  ABSTRACT — EACH AGENT IMPLEMENTS THESE
    # ══════════════════════════════════════════════════════════════════════

    @abstractmethod
    def observe(self, state: MicrogridState) -> dict[str, Any]:
        """
        Extract the relevant inputs this agent cares about from the
        central MicrogridState.  Returns a dict of named observations.
        """
        ...

    @abstractmethod
    async def decide(self, state: MicrogridState) -> list[AgentDecision]:
        """
        Produce a list of AgentDecision objects.
        Use deterministic logic for numbers, LLM for reasoning.
        """
        ...

    # ══════════════════════════════════════════════════════════════════════
    #  HELPERS
    # ══════════════════════════════════════════════════════════════════════

    async def _call_llm(
        self, system_prompt: str, user_message: str, **kwargs
    ) -> dict[str, Any]:
        """Convenience wrapper around the shared LLM service."""
        return await llm_service.call(
            agent_type=self.agent_type,
            system_prompt=system_prompt,
            user_message=user_message,
            **kwargs,
        )

    def _make_decision(
        self,
        action: str,
        resource: str = "",
        quantity_kwh: float | None = None,
        quantity_kw: float | None = None,
        duration_minutes: float | None = None,
        reason: str = "",
        expected_effect: str = "",
        confidence: float = 1.0,
        priority: int = 5,
    ) -> AgentDecision:
        """Convenience factory for AgentDecision."""
        return AgentDecision(
            agent=self.agent_type,
            action=action,
            resource=resource,
            quantity_kwh=quantity_kwh,
            quantity_kw=quantity_kw,
            duration_minutes=duration_minutes,
            reason=reason,
            expected_effect=expected_effect,
            confidence=confidence,
            priority=priority,
        )
