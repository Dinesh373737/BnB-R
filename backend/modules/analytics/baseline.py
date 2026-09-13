"""Analytics module — Simple deterministic baseline controller.

The baseline represents basic, rule-based control logic that any microgrid
could follow **without** intelligent multi-agent coordination.  It reuses the
existing ``SimulationService`` so that the same physical model and constraints
apply; only the control inputs differ.

Baseline strategy (per timestep):
    1. Use all available renewable generation.
    2. Meet demand with local generation first.
    3. Discharge battery when generation is insufficient.
    4. Import from the grid as a last resort.
    5. Charge the battery with surplus generation (no smart scheduling).
    6. No P2P trading optimisation.
    7. No coordinated demand response (flexible loads stay at scenario defaults).
    8. No intelligent EV charging optimisation.
    9. Respect all physical and safety constraints (handled by the simulation).

This module does NOT use an LLM, AI agent, or any external service.
"""

from __future__ import annotations

from backend.common.logger import get_module_logger
from backend.modules.analytics.schemas import (
    TimestepSnapshot,
    snapshot_from_step_result,
)

log = get_module_logger("analytics.baseline")


class BaselineController:
    """Run the same simulation scenario with naïve deterministic control.

    Usage::

        controller = BaselineController()
        snapshots = controller.run(config, scenario)
    """

    def run(
        self,
        config=None,
        scenario=None,
        *,
        num_steps: int = 13,
    ) -> list[TimestepSnapshot]:
        """Execute a full baseline simulation and return timestep snapshots.

        Parameters
        ----------
        config:
            A ``SimulationConfig`` (or ``None`` for defaults).  The baseline
            receives exactly the same physical configuration as GridMind.
        scenario:
            An optional ``CrisisScenario`` to apply — must be the same
            scenario that GridMind faced.
        num_steps:
            Number of simulation timesteps to run.

        Returns
        -------
        list[TimestepSnapshot]
            One snapshot per timestep, ready for metric calculations.
        """
        # Import lazily so that the analytics module stays decoupled from the
        # simulation package at import time.
        from backend.modules.simulation.service import SimulationService
        from backend.modules.simulation.schemas import (
            ControlInputs,
            SimulationConfig,
        )

        cfg = config if config is not None else SimulationConfig()
        timestep_seconds = cfg.timestep_seconds

        service = SimulationService(cfg)
        service.initialize()

        if scenario is not None:
            service.apply_scenario(scenario)

        snapshots: list[TimestepSnapshot] = []

        # Capture the initial state (timestep 0)
        init_result = service.get_last_result()
        snapshots.append(
            snapshot_from_step_result(init_result, timestep_seconds=timestep_seconds)
        )

        for _ in range(num_steps):
            controls = self._decide(service)
            state = service.step(controls)
            step_result = service.get_last_result()
            snapshots.append(
                snapshot_from_step_result(
                    step_result, timestep_seconds=timestep_seconds
                )
            )

        log.info(
            "Baseline simulation completed: %d timesteps", len(snapshots)
        )
        return snapshots

    # ------------------------------------------------------------------
    #  Simple deterministic control logic
    # ------------------------------------------------------------------

    @staticmethod
    def _decide(service) -> "ControlInputs":
        """Produce naïve deterministic ``ControlInputs`` for one timestep.

        Strategy:
          • If local generation < demand → discharge battery to cover deficit
          • If local generation > demand → charge battery with surplus
          • Flexible loads are left at *None* (scenario defaults; no DR).
        """
        from backend.modules.simulation.schemas import ControlInputs

        state = service.get_state()

        renewable_gen = state.renewable_generation_kw
        demand = state.total_demand_kw
        deficit = demand - renewable_gen

        if deficit > 0:
            # Discharge battery to help cover the gap (capped by physics)
            available_discharge = min(
                state.battery.discharge_rate_kw,
                state.battery.energy_available_kwh
                * (3600.0 / service.config.timestep_seconds),
            )
            battery_power = -min(deficit, available_discharge)
        else:
            # Surplus: charge battery (capped by physics)
            surplus = -deficit
            max_chargeable_kwh = (
                (state.battery.max_soc - state.battery.current_soc)
                * state.battery.capacity_kwh
            )
            max_charge_kw = min(
                state.battery.charge_rate_kw,
                max_chargeable_kwh
                * (3600.0 / service.config.timestep_seconds),
            )
            battery_power = min(surplus, max_charge_kw)

        return ControlInputs(
            battery_power_kw=battery_power,
            # None = keep scenario/default flexible demand (no DR)
            household_flexible_demand_kw=None,
            industry_flexible_demand_kw=None,
            ev_flexible_demand_kw=None,
        )
