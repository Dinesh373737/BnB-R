"""The fixed 13-step GridMind simulation loop.

Each timestep runs the full multi-agent pipeline (risk → resources → demand →
market → critical → coordinator → safety validation) and feeds the approved
decisions into the simulation as ``ControlInputs``.  This is what
distinguishes the GridMind run from the analytics baseline, which uses naive
deterministic control.
"""

from typing import TYPE_CHECKING

from backend.common.events import Events, event_bus
from backend.common.logger import get_module_logger
from backend.common.schemas.microgrid_state import MicrogridState

if TYPE_CHECKING:
    from backend.modules.simulation.service import SimulationService

SIMULATION_LOOP_STEPS = 13

log = get_module_logger("simulation.loop")


class SimulationLoop:
    """Runs thirteen agent-driven physical transitions."""

    def __init__(self, service: "SimulationService") -> None:
        self.service = service

    def run(self) -> list[MicrogridState]:
        """Initialize if needed, publish lifecycle events, and run 13 steps."""
        if not self.service.is_initialized:
            self.service.initialize()
        event_bus.publish(
            Events.SIMULATION_STARTED,
            {"simulation_run_id": self.service.config.simulation_run_id, "steps": SIMULATION_LOOP_STEPS},
        )
        states: list[MicrogridState] = []
        try:
            for step in range(SIMULATION_LOOP_STEPS):
                controls = self._agent_controls(step)
                if controls is not None:
                    states.append(self.service.step(controls))
                else:
                    states.append(self.service.step())
        except Exception as error:
            event_bus.publish(
                Events.SIMULATION_ERROR,
                {"timestep": self.service.get_state().timestep, "error": str(error)},
            )
            raise
        event_bus.publish(
            Events.SIMULATION_FINISHED,
            {"simulation_run_id": self.service.config.simulation_run_id, "steps": SIMULATION_LOOP_STEPS},
        )
        return states

    # ------------------------------------------------------------------
    #  Agent pipeline integration
    # ------------------------------------------------------------------

    def _agent_controls(self, step: int):
        """Run the agent pipeline on the current state and return controls.

        Returns ``None`` when the pipeline is unavailable (e.g. an import
        error in the agents package) so the loop still completes with
        uncontrolled physics rather than failing outright.
        """
        try:
            import asyncio

            from backend.modules.agents.control_bridge import decisions_to_controls
            from backend.modules.agents.router import (
                coordinator_agent,
                risk_agent,
                energy_agent,
                demand_agent,
                market_agent,
                critical_agent,
            )
            from backend.modules.safety.service import SafetyService

            state = self.service.get_state()

            async def _pipeline():
                # 1. Risk assessment (also injects risk into state)
                risk_decisions = await risk_agent.run(state)
                risk_info = risk_agent.risk_output
                from backend.common.schemas.enums import RiskLevel

                state.risk.risk_score = risk_info.get("risk_score", 0)
                state.risk.risk_level = RiskLevel(
                    risk_info.get("risk_level", "low")
                )
                state.risk.drivers = risk_info.get("drivers", [])

                # 2-5. Specialist agents
                all_decisions = list(risk_decisions)
                for agent in (energy_agent, demand_agent, market_agent, critical_agent):
                    decisions = await agent.run(state)
                    all_decisions.extend(decisions)

                # 6. Coordinator conflict resolution
                coordinator_agent.set_agent_decisions(all_decisions, risk_info)
                approved = await coordinator_agent.run(state)

                # Safety validation — final gatekeeper
                safety = SafetyService()
                validation = safety.validate(state, approved)
                return validation.approved_decisions

            approved = asyncio.run(_pipeline())
            log.debug(
                "Step %s: agents approved %d decision(s)", step, len(approved)
            )
            return decisions_to_controls(state, approved)
        except Exception as exc:
            log.warning(
                "Agent pipeline unavailable at step %s (%s); running uncontrolled",
                step,
                exc,
            )
            return None
