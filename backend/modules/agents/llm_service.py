"""
GridMind — Centralized Groq LLM Service
==========================================
Single entry point for ALL agent LLM calls.
Reads GROQ_API_KEY and per-agent model names from environment.

Architecture:
    Agent → LLMService.call(agent_type, system_prompt, user_msg) → Groq API → JSON

Usage:
    from backend.modules.agents.llm_service import llm_service
    result = await llm_service.call(
        agent_type=AgentType.RISK_FORECAST,
        system_prompt="You are a risk analyst...",
        user_message="Current state: ...",
    )
"""

import json
from typing import Any

try:
    from groq import AsyncGroq
except ModuleNotFoundError:  # pragma: no cover - dependency is optional at runtime
    AsyncGroq = None  # type: ignore[assignment]

from backend.common.logger import get_module_logger
from backend.common.schemas.enums import AgentType
from backend.common.config import settings

log = get_module_logger("agents.llm_service")

# ── Per-agent model environment variable mapping ──────────────────────────
_DEFAULT_MODEL = "openai/gpt-oss-120b"


class LLMService:
    """Centralised Groq LLM wrapper used by all agents."""

    def __init__(self):
        self._api_key: str = settings.GROQ_API_KEY
        self._client: AsyncGroq | None = None
        self._models: dict[AgentType, str] = {
            AgentType.COORDINATOR: settings.COORDINATOR_MODEL,
            AgentType.RISK_FORECAST: settings.RISK_MODEL,
            AgentType.ENERGY_RESOURCE: settings.RESOURCE_MODEL,
            AgentType.DEMAND_MANAGEMENT: settings.DEMAND_MODEL,
            AgentType.MARKET_TRADING: settings.MARKET_MODEL,
            AgentType.CRITICAL_FACILITY: settings.CRITICAL_MODEL,
        }

        if self._api_key and AsyncGroq is not None:
            self._client = AsyncGroq(api_key=self._api_key)
            log.info("Groq LLM service initialised")
        else:
            if not self._api_key:
                log.warning(
                    "GROQ_API_KEY not set — agents will use deterministic fallback only"
                )
            else:
                log.warning(
                    "Groq package is not installed — agents will use deterministic fallback only"
                )

    # ── Public API ────────────────────────────────────────────────────────

    @property
    def is_available(self) -> bool:
        return self._client is not None

    def get_model(self, agent_type: AgentType) -> str:
        return self._models.get(agent_type, _DEFAULT_MODEL)

    async def call(
        self,
        agent_type: AgentType,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        """
        Call the Groq LLM and return the parsed JSON response.

        Falls back to an empty dict on any failure so agents can
        continue with deterministic logic alone.
        """
        if not self._client:
            log.debug(f"[{agent_type.value}] LLM unavailable — skipping")
            return {}

        model = self.get_model(agent_type)

        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )

            raw = response.choices[0].message.content or "{}"
            parsed = json.loads(raw)
            log.debug(
                f"[{agent_type.value}] LLM response OK "
                f"(model={model}, tokens={response.usage.total_tokens if response.usage else '?'})"
            )
            return parsed

        except json.JSONDecodeError as e:
            log.error(f"[{agent_type.value}] LLM returned invalid JSON: {e}")
            return {}
        except Exception as e:
            log.error(f"[{agent_type.value}] LLM call failed: {e}")
            return {}


# ── Singleton ─────────────────────────────────────────────────────────────
llm_service = LLMService()
