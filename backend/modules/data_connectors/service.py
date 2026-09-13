"""
Data Connectors — Service Layer
Orchestrates live / historical / simulated weather and grid data.
"""

from datetime import datetime, timezone

from backend.common.logger import get_module_logger
from backend.modules.data_connectors.grid import GridClient
from backend.modules.data_connectors.schemas import GridDataResponse, WeatherResponse
from backend.modules.data_connectors.weather import WeatherClient

log = get_module_logger("modules.data_connectors.service")


class DataConnectorService:
    """Unified entry point for external data that the rest of GridMind consumes."""

    def __init__(self):
        self.weather_client = WeatherClient()
        self.grid_client = GridClient()
        log.info("DataConnectorService initialized")

    # ── Weather ──────────────────────────────────────────────────

    def get_current_weather(self, *, as_of: datetime | None = None) -> WeatherResponse:
        """Return the current weather for the configured location.

        Priority:
        1. Live Open-Meteo if enabled
        2. Historical CSV nearest to ``as_of`` if enabled
        3. Simulated fallback
        """
        return self.weather_client.fetch_current_weather(target_time=as_of)

    # ── Grid ─────────────────────────────────────────────────────

    def get_current_grid_state(self, *, as_of: datetime | None = None) -> GridDataResponse:
        """Return the current macro-grid state.

        Priority:
        1. Live Karnataka API if configured and enabled
        2. Historical CSV nearest to ``as_of`` if enabled
        3. Deterministic fallback simulation
        """
        response = self.grid_client.fetch_current_grid_state(target_time=as_of)

        # Persist the reading and emit an event so downstream consumers can
        # react to the latest macro-grid state without re-fetching.
        try:
            self.grid_client.persist_and_publish(
                response,
                condition=response.condition_label,
                source=(
                    "live"
                    if response.source == "live"
                    else (
                        "historical"
                        if response.source == "historical"
                        else "simulated"
                    )
                ),
            )
        except Exception as exc:  # noqa: PERF203
            log.warning("GridStateRecord persistence failed: %s", exc)

        return response
