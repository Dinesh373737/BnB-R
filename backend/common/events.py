"""
GridMind — Event Bus (Pub/Sub)
================================
Simple in-process event system for inter-module communication.
Modules publish events; other modules subscribe to react.

This is NOT a message queue — it's a lightweight synchronous/async
pub/sub system for decoupled communication between isolated modules.

Usage:
    from backend.common.events import event_bus

    # Subscribe (typically in module __init__ or startup)
    def on_risk_update(data):
        print(f"Risk changed to: {data['risk_level']}")

    event_bus.subscribe("risk.updated", on_risk_update)

    # Publish (from any module)
    event_bus.publish("risk.updated", {"risk_level": "HIGH", "score": 78})

    # Async support
    async def on_state_change(data):
        await notify_websockets(data)

    event_bus.subscribe("microgrid.state_changed", on_state_change)
    await event_bus.publish_async("microgrid.state_changed", new_state)

Event Naming Convention:
    <domain>.<action>
    Examples:
        risk.updated
        agent.decision_made
        market.trade_executed
        simulation.step_completed
        microgrid.state_changed
        scenario.triggered
        safety.violation_detected
        system.startup
        system.shutdown
"""

import asyncio
from collections import defaultdict
from typing import Any, Callable
from datetime import datetime, timezone

from backend.common.logger import get_module_logger

log = get_module_logger("events")


class EventBus:
    """
    Lightweight publish/subscribe event bus.
    Supports both sync and async handlers.
    """

    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._event_history: list[dict] = []
        self._max_history: int = 1000  # Keep last N events in memory

    # ── Subscribe ─────────────────────────────────────────────────────

    def subscribe(self, event_name: str, handler: Callable) -> None:
        """
        Register a handler for an event type.
        The handler receives a single `data` argument (dict).
        Supports both sync and async handlers.
        """
        self._subscribers[event_name].append(handler)
        log.debug(
            f"Subscribed to '{event_name}': {handler.__module__}.{handler.__qualname__}"
        )

    def unsubscribe(self, event_name: str, handler: Callable) -> None:
        """Remove a handler from an event type."""
        if event_name in self._subscribers:
            self._subscribers[event_name] = [
                h for h in self._subscribers[event_name] if h != handler
            ]

    # ── Publish (Synchronous) ─────────────────────────────────────────

    def publish(self, event_name: str, data: Any = None) -> None:
        """
        Publish an event synchronously.
        All registered sync handlers are called immediately.
        Async handlers are skipped (use publish_async for those).
        """
        event_record = {
            "event": event_name,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "handler_count": len(self._subscribers.get(event_name, [])),
        }
        self._record_event(event_record)

        handlers = self._subscribers.get(event_name, [])
        if not handlers:
            return

        log.debug(f"Publishing '{event_name}' to {len(handlers)} handler(s)")

        for handler in handlers:
            try:
                if not asyncio.iscoroutinefunction(handler):
                    handler(data)
            except Exception as e:
                log.error(
                    f"Error in event handler for '{event_name}': "
                    f"{handler.__qualname__}: {e}"
                )

    # ── Publish (Asynchronous) ────────────────────────────────────────

    async def publish_async(self, event_name: str, data: Any = None) -> None:
        """
        Publish an event asynchronously.
        Both sync and async handlers are called.
        """
        event_record = {
            "event": event_name,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "handler_count": len(self._subscribers.get(event_name, [])),
        }
        self._record_event(event_record)

        handlers = self._subscribers.get(event_name, [])
        if not handlers:
            return

        log.debug(f"Publishing async '{event_name}' to {len(handlers)} handler(s)")

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                log.error(
                    f"Error in async event handler for '{event_name}': "
                    f"{handler.__qualname__}: {e}"
                )

    # ── Event History ─────────────────────────────────────────────────

    def _record_event(self, event_record: dict) -> None:
        """Store event in history ring buffer."""
        self._event_history.append(event_record)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

    def get_history(self, limit: int = 50, event_filter: str = "") -> list[dict]:
        """
        Get recent event history.
        Optionally filter by event name prefix.
        """
        history = self._event_history
        if event_filter:
            history = [e for e in history if e["event"].startswith(event_filter)]
        return history[-limit:]

    # ── Utility ───────────────────────────────────────────────────────

    def get_subscriber_count(self, event_name: str) -> int:
        """Get number of subscribers for an event type."""
        return len(self._subscribers.get(event_name, []))

    def list_events(self) -> list[str]:
        """List all event types that have subscribers."""
        return sorted(self._subscribers.keys())

    def clear_all(self) -> None:
        """Remove all subscribers and history (used in testing)."""
        self._subscribers.clear()
        self._event_history.clear()


# ---------------------------------------------------------------------------
# Pre-defined Event Names (constants for type-safety)
# ---------------------------------------------------------------------------

class Events:
    """
    Standard event names used across GridMind.
    Use these constants instead of raw strings for consistency.
    """

    # ── System ─────────────────────────────────────────────────────────
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_ERROR = "system.error"

    # ── Simulation ─────────────────────────────────────────────────────
    SIMULATION_STARTED = "simulation.started"
    SIMULATION_STEP_COMPLETED = "simulation.step_completed"
    SIMULATION_FINISHED = "simulation.finished"
    SIMULATION_ERROR = "simulation.error"

    # ── Microgrid ──────────────────────────────────────────────────────
    MICROGRID_STATE_CHANGED = "microgrid.state_changed"
    MICROGRID_INITIALIZED = "microgrid.initialized"

    # ── Risk ───────────────────────────────────────────────────────────
    RISK_UPDATED = "risk.updated"
    RISK_CRITICAL = "risk.critical"

    # ── Agents ─────────────────────────────────────────────────────────
    AGENT_DECISION_MADE = "agent.decision_made"
    AGENT_ERROR = "agent.error"
    AGENT_COORDINATOR_RESOLVED = "agent.coordinator_resolved"

    # ── Forecasting ────────────────────────────────────────────────────
    FORECAST_UPDATED = "forecast.updated"
    FORECAST_ERROR = "forecast.error"

    # ── Market ─────────────────────────────────────────────────────────
    MARKET_ORDER_PLACED = "market.order_placed"
    MARKET_TRADE_EXECUTED = "market.trade_executed"
    MARKET_CLEARED = "market.cleared"

    # ── Safety ─────────────────────────────────────────────────────────
    SAFETY_CHECK_PASSED = "safety.check_passed"
    SAFETY_VIOLATION_DETECTED = "safety.violation_detected"

    # ── Scenario ───────────────────────────────────────────────────────
    SCENARIO_TRIGGERED = "scenario.triggered"
    SCENARIO_COMPLETED = "scenario.completed"

    # ── Data ───────────────────────────────────────────────────────────
    DATA_KARNATAKA_UPDATED = "data.karnataka_updated"
    DATA_WEATHER_UPDATED = "data.weather_updated"

    # ── Analytics ──────────────────────────────────────────────────────
    ANALYTICS_COMPUTED = "analytics.computed"


# ---------------------------------------------------------------------------
# Singleton instance — import this everywhere
# ---------------------------------------------------------------------------
event_bus = EventBus()
