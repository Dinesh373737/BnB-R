"""Simulation persistence layer.

Bridges the in-memory ``SimulationService`` to the database so that the
analytics module (and any other consumer) can read completed runs:

* ``simulation_runs``     — one row per run (created on initialize).
* ``microgrid_states``    — one row per timestep, including a lossless
                            ``full_state_json`` snapshot of the shared state.
* ``market_orders`` / ``trades`` — stamped with the active run id so P2P
                            trades can be attributed to a run's market metrics.

All writes are best-effort: a persistence failure must never break the
deterministic simulation itself.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.common.logger import get_module_logger
from backend.common.models.microgrid import MicrogridStateDBRecord
from backend.common.models.simulation import SimulationRunRecord
from backend.common.schemas.enums import SimulationMode, SimulationStatus
from backend.common.schemas.microgrid_state import MicrogridState

log = get_module_logger("simulation.persistence")

# One DB session at a time; the simulation runs in worker threads.
_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_state(state: MicrogridState) -> str:
    """Lossless JSON serialization of the shared state."""
    return state.model_dump_json()


class SimulationRepository:
    """Persists simulation runs and their per-timestep microgrid states."""

    def __init__(self, session_factory):
        self._session_factory = session_factory

    def _session(self) -> Session:
        return self._session_factory()

    # ------------------------------------------------------------------
    #  Run lifecycle
    # ------------------------------------------------------------------

    def create_run(
        self,
        *,
        config_params: dict[str, Any],
        scenario: str | None = None,
        timestep_seconds: int = 60,
    ) -> int:
        """Insert a ``simulation_runs`` row and return its id."""
        record = SimulationRunRecord(
            mode=SimulationMode.SIMULATION.value,
            scenario=scenario,
            status=SimulationStatus.RUNNING.value,
            start_time=_now(),
            timestep_seconds=timestep_seconds,
            parameters_json=json.dumps(config_params, default=str),
        )
        with _lock, self._session() as db:
            db.add(record)
            db.commit()
            db.refresh(record)
            run_id = int(record.id)
        log.info("Simulation run #%s created", run_id)
        return run_id

    def finish_run(
        self,
        run_id: int,
        *,
        total_timesteps: int,
        scenario: str | None = None,
        results_summary: dict[str, Any] | None = None,
    ) -> None:
        """Mark a run completed and store its summary."""
        with _lock, self._session() as db:
            record = (
                db.query(SimulationRunRecord)
                .filter(SimulationRunRecord.id == run_id)
                .first()
            )
            if record is None:
                return
            record.status = SimulationStatus.COMPLETED.value
            record.end_time = _now()
            record.total_timesteps = total_timesteps
            if scenario:
                record.scenario = scenario
            if results_summary is not None:
                record.results_summary_json = json.dumps(
                    results_summary, default=str
                )
            duration = (
                record.end_time - record.start_time
            ).total_seconds() if record.start_time else None
            record.duration_seconds = duration
            db.commit()

    def set_status(self, run_id: int, status: SimulationStatus) -> None:
        with _lock, self._session() as db:
            record = (
                db.query(SimulationRunRecord)
                .filter(SimulationRunRecord.id == run_id)
                .first()
            )
            if record is not None:
                record.status = status.value
                db.commit()

    # ------------------------------------------------------------------
    #  State persistence
    # ------------------------------------------------------------------

    def save_state(self, run_id: int, state: MicrogridState) -> None:
        """Insert one ``microgrid_states`` row for the given timestep."""
        record = MicrogridStateDBRecord(
            timestamp=state.timestamp,
            simulation_run_id=run_id,
            timestep=state.timestep,
            total_demand_kw=state.total_demand_kw,
            total_generation_kw=state.total_generation_kw,
            renewable_generation_kw=state.renewable_generation_kw,
            renewable_percentage=state.renewable_percentage,
            energy_balance_kw=state.energy_balance_kw,
            battery_soc=state.battery.current_soc,
            ev_demand_kw=state.ev.total_demand_kw,
            grid_import_kw=state.grid_connection.import_power_kw,
            grid_export_kw=state.grid_connection.export_power_kw,
            energy_traded_kwh=state.market.total_energy_traded_kwh,
            solar_output_kw=state.solar.current_output_kw,
            wind_output_kw=state.wind.current_output_kw,
            risk_level=(
                state.risk.risk_level.value
                if hasattr(state.risk.risk_level, "value")
                else str(state.risk.risk_level)
            ),
            risk_score=state.risk.risk_score,
            grid_condition=(
                state.grid_connection.condition.value
                if hasattr(state.grid_connection.condition, "value")
                else str(state.grid_connection.condition)
            ),
            critical_load_status=(
                state.critical_facility.status.value
                if hasattr(state.critical_facility.status, "value")
                else str(state.critical_facility.status)
            ),
            data_source=state.data_source,
            full_state_json=_serialize_state(state),
        )
        with _lock, self._session() as db:
            db.add(record)
            db.commit()

    def save_states_batch(self, run_id: int, states: list[MicrogridState]) -> None:
        """Insert multiple state rows in a single transaction."""
        rows = [
            MicrogridStateDBRecord(
                timestamp=s.timestamp,
                simulation_run_id=run_id,
                timestep=s.timestep,
                total_demand_kw=s.total_demand_kw,
                total_generation_kw=s.total_generation_kw,
                renewable_generation_kw=s.renewable_generation_kw,
                renewable_percentage=s.renewable_percentage,
                energy_balance_kw=s.energy_balance_kw,
                battery_soc=s.battery.current_soc,
                ev_demand_kw=s.ev.total_demand_kw,
                grid_import_kw=s.grid_connection.import_power_kw,
                grid_export_kw=s.grid_connection.export_power_kw,
                energy_traded_kwh=s.market.total_energy_traded_kwh,
                solar_output_kw=s.solar.current_output_kw,
                wind_output_kw=s.wind.current_output_kw,
                risk_level=(
                    s.risk.risk_level.value
                    if hasattr(s.risk.risk_level, "value")
                    else str(s.risk.risk_level)
                ),
                risk_score=s.risk.risk_score,
                grid_condition=(
                    s.grid_connection.condition.value
                    if hasattr(s.grid_connection.condition, "value")
                    else str(s.grid_connection.condition)
                ),
                critical_load_status=(
                    s.critical_facility.status.value
                    if hasattr(s.critical_facility.status, "value")
                    else str(s.critical_facility.status)
                ),
                data_source=s.data_source,
                full_state_json=_serialize_state(s),
            )
            for s in states
        ]
        with _lock, self._session() as db:
            db.add_all(rows)
            db.commit()

    # ------------------------------------------------------------------
    #  Market linkage
    # ------------------------------------------------------------------

    def stamp_market_orders(self, run_id: int) -> int:
        """Stamp PENDING market orders (and their future trades) with a run id.

        Orders placed from the UI during a live run carry no run id; this links
        them so the run's market metrics include real P2P activity.
        """
        from backend.common.models.market import MarketOrderRecord

        with _lock, self._session() as db:
            updated = (
                db.query(MarketOrderRecord)
                .filter(
                    MarketOrderRecord.simulation_run_id.is_(None),
                    MarketOrderRecord.status == "pending",
                )
                .update(
                    {MarketOrderRecord.simulation_run_id: run_id},
                    synchronize_session=False,
                )
            )
            db.commit()
        if updated:
            log.info("Stamped %s pending order(s) with run #%s", updated, run_id)
        return updated or 0


# ── Singleton ────────────────────────────────────────────────────────────

def get_simulation_repository() -> SimulationRepository:
    """Repository backed by the shared SQLAlchemy session factory."""
    from backend.common.database import SessionLocal

    return SimulationRepository(SessionLocal)
