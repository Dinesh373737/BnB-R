"""WebSocket Layer — Live Telemetry Broadcaster.

Periodically pushes real data to the three WebSocket channels so 3D dashboard
clients (and any other live consumer) receive a continuous stream:

* ``microgrid`` — current microgrid state snapshot (per-asset power, SOC,
  risk, balance). If no simulation is active, a fresh deterministic state is
  published so the 3D twin still animates from real backend logic.
* ``agents``    — live agent statuses and latest approved decisions.
* ``market``    — active bids/asks and the most recent executed trades.

All data comes from the running backend modules — nothing is fabricated.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from backend.common.config import settings
from backend.common.logger import get_module_logger

from .manager import ws_manager

log = get_module_logger("websocket.broadcaster")

_task: asyncio.Task | None = None


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _microgrid_payload() -> dict[str, Any]:
    """Current microgrid state from the simulation module (real data)."""
    try:
        from backend.modules.simulation.router import _service

        if not _service.is_initialized:
            _service.initialize()

        state = _service.get_state()

        # Hopfield energy landscape (same math the analytics endpoint uses)
        from backend.modules.analytics.hopfield import hopfield_energy

        hopfield = hopfield_energy(state)

        return {
            "type": "microgrid_state",
            "timestamp": _utcnow_iso(),
            "state": state.model_dump(mode="json"),
            "hopfield": hopfield,
            "flow": {
                "solar_kw": state.solar.current_output_kw,
                "wind_kw": state.wind.current_output_kw,
                "battery_kw": state.battery.current_power_kw,
                "battery_soc": state.battery.current_soc,
                "grid_import_kw": state.grid_connection.import_power_kw,
                "grid_export_kw": state.grid_connection.export_power_kw,
                "household_kw": state.households.total_demand_kw,
                "industry_kw": state.industry.total_demand_kw,
                "ev_kw": state.ev.total_demand_kw,
                "critical_kw": state.critical_facility.current_supply_kw,
                "total_demand_kw": state.total_demand_kw,
                "total_generation_kw": state.total_generation_kw,
                "energy_balance_kw": state.energy_balance_kw,
            },
            "risk": {
                "score": state.risk.risk_score,
                "level": (
                    state.risk.risk_level.value
                    if hasattr(state.risk.risk_level, "value")
                    else str(state.risk.risk_level)
                ),
            },
        }
    except Exception as exc:
        log.warning("Microgrid broadcast payload failed: %s", exc)
        return {"type": "microgrid_state", "timestamp": _utcnow_iso(), "error": str(exc)}


def _agents_payload() -> dict[str, Any]:
    """Live agent statuses + latest decisions from the agents router."""
    try:
        from backend.modules.agents.router import _AGENTS

        agents = []
        for agent in _AGENTS.values():
            status = agent.get_status_dict()
            status["decisions"] = [
                d.model_dump(mode="json") for d in agent._last_decisions
            ][:5]
            agents.append(status)

        return {
            "type": "agents_status",
            "timestamp": _utcnow_iso(),
            "agents": agents,
        }
    except Exception as exc:
        log.warning("Agents broadcast payload failed: %s", exc)
        return {"type": "agents_status", "timestamp": _utcnow_iso(), "error": str(exc)}


def _market_payload() -> dict[str, Any]:
    """Active orders and recent trades from the market engine (DB-backed)."""
    try:
        from backend.common.database import SessionLocal
        from backend.common.models.market import MarketOrderRecord, TradeRecord
        from backend.common.schemas.enums import OrderStatus

        with SessionLocal() as db:
            pending = (
                db.query(MarketOrderRecord)
                .filter(MarketOrderRecord.status == OrderStatus.PENDING)
                .all()
            )
            trades = (
                db.query(TradeRecord)
                .order_by(TradeRecord.id.desc())
                .limit(10)
                .all()
            )

            return {
                "type": "market_update",
                "timestamp": _utcnow_iso(),
                "pending_orders": [
                    {
                        "id": o.id,
                        "participant_id": o.participant_id,
                        "participant_name": o.participant_name,
                        "order_type": (
                            o.order_type.value
                            if hasattr(o.order_type, "value")
                            else str(o.order_type)
                        ),
                        "energy_kwh": o.energy_kwh,
                        "price_per_kwh": o.price_per_kwh,
                    }
                    for o in pending
                ],
                "trades": [
                    {
                        "id": t.id,
                        "seller_id": t.seller_id,
                        "seller_name": t.seller_name,
                        "buyer_id": t.buyer_id,
                        "buyer_name": t.buyer_name,
                        "energy_kwh": t.energy_kwh,
                        "price_per_kwh": t.price_per_kwh,
                        "total_cost": t.total_cost,
                        "timestamp": (
                            t.timestamp.isoformat() if t.timestamp else None
                        ),
                    }
                    for t in trades
                ],
            }
    except Exception as exc:
        log.warning("Market broadcast payload failed: %s", exc)
        return {"type": "market_update", "timestamp": _utcnow_iso(), "error": str(exc)}


async def _broadcast_loop() -> None:
    """Push each channel's payload at the configured interval."""
    interval = max(1, settings.POLLING_INTERVAL_SECONDS)
    while True:
        try:
            has_microgrid = bool(ws_manager.active_connections.get("microgrid"))
            has_agents = bool(ws_manager.active_connections.get("agents"))
            has_market = bool(ws_manager.active_connections.get("market"))

            if has_microgrid:
                await ws_manager.broadcast("microgrid", _microgrid_payload())
            if has_agents:
                await ws_manager.broadcast("agents", _agents_payload())
            if has_market:
                await ws_manager.broadcast("market", _market_payload())
        except Exception as exc:  # pragma: no cover — never kill the loop
            log.error("Broadcast loop iteration failed: %s", exc)

        await asyncio.sleep(interval)


def start_broadcaster() -> asyncio.Task | None:
    """Start the periodic broadcast task (idempotent)."""
    global _task
    if _task is not None and not _task.done():
        return _task
    try:
        _task = asyncio.get_event_loop().create_task(_broadcast_loop())
        log.info(
            "Broadcaster started (interval=%ss)", settings.POLLING_INTERVAL_SECONDS
        )
        return _task
    except RuntimeError:
        log.warning("No running event loop; broadcaster not started")
        return None


def stop_broadcaster() -> None:
    """Cancel the broadcast task on shutdown."""
    global _task
    if _task is not None:
        _task.cancel()
        _task = None
        log.info("Broadcaster stopped")
