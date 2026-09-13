"""
GridMind — API Registry
=========================
Central registry of ALL external APIs used across the project.
Modules look up API details here — they never hardcode URLs.

╔═══════════════════════════════════════════════════════════════╗
║  TOTAL REGISTERED APIs: 3                                    ║
║  ─────────────────────────────────────────────────────────── ║
║  EXTERNAL APIs (2):                                          ║
║    1. Open-Meteo Weather API — FREE, no key required         ║
║       • Forecast: temperature, cloud, solar radiation, wind  ║
║       • Historical: archive weather data                     ║
║    2. Karnataka Grid Data API — configurable source          ║
║       • Falls back to simulated data if URL not set          ║
║  ─────────────────────────────────────────────────────────── ║
║  INTERNAL APIs (1):                                          ║
║    3. GridMind Backend (FastAPI) — 15 REST + 5 WebSocket     ║
║       • REST: /api/health, /api/grid, /api/agents, etc.     ║
║       • WS:   /ws/microgrid, /ws/agents, /ws/market, etc.   ║
╚═══════════════════════════════════════════════════════════════╝

This file serves as:
  1. Documentation of every API GridMind connects to
  2. Runtime lookup for endpoints, keys, and rate limits
  3. Health-check targets

Usage:
    from backend.common.api_registry import api_registry

    weather_api = api_registry.get("open_meteo")
    url = weather_api["forecast_url"]

    all_apis = api_registry.list_all()
"""

from dataclasses import dataclass, field
from backend.common.config import settings


@dataclass
class APIEntry:
    """Describes a single external API."""

    name: str                           # Human-readable name
    key: str                            # Lookup key (snake_case)
    base_url: str                       # Base URL
    endpoints: dict[str, str]           # Named endpoints
    api_key: str = ""                   # API key (empty if free)
    requires_key: bool = False          # Whether an API key is mandatory
    is_free: bool = True                # Whether it's free to use
    rate_limit: str = ""                # Rate limit info (human-readable)
    docs_url: str = ""                  # Link to API documentation
    notes: str = ""                     # Additional notes
    headers: dict[str, str] = field(default_factory=dict)  # Default headers


class APIRegistry:
    """
    Central registry of all external APIs.
    Populated at startup from config. Modules query this, never hardcode.
    """

    def __init__(self):
        self._apis: dict[str, APIEntry] = {}
        self._register_all()

    def _register_all(self):
        """Register every external API GridMind uses."""

        # ── Open-Meteo Weather API ─────────────────────────────────────
        self.register(
            APIEntry(
                name="Open-Meteo Weather API",
                key="open_meteo",
                base_url=settings.OPEN_METEO_BASE_URL,
                endpoints={
                    "forecast": settings.OPEN_METEO_FORECAST_URL,
                    "historical": settings.OPEN_METEO_HISTORICAL_URL,
                },
                api_key="",
                requires_key=False,
                is_free=True,
                rate_limit="10,000 requests/day (non-commercial)",
                docs_url="https://open-meteo.com/en/docs",
                notes=(
                    "Free weather API. No API key required. "
                    "Provides current weather, forecasts, and historical data. "
                    "Used for: temperature, cloud_cover, solar_radiation, "
                    "wind_speed, weather_condition. "
                    "Location: Bangalore (12.9716°N, 77.5946°E)."
                ),
                headers={"Accept": "application/json"},
            )
        )

        # ── Open-Meteo Forecast Parameters ─────────────────────────────
        # These are the query parameters we use most often:
        #   ?latitude=12.9716
        #   &longitude=77.5946
        #   &hourly=temperature_2m,cloud_cover,direct_radiation,
        #           windspeed_10m,weathercode
        #   &forecast_days=2
        #   &timezone=Asia/Kolkata

        # ── Karnataka Grid Data API ────────────────────────────────────
        self.register(
            APIEntry(
                name="Karnataka Grid Data",
                key="karnataka_grid",
                base_url=settings.KARNATAKA_GRID_API_URL or "N/A (simulated)",
                endpoints={
                    "current_state": (
                        f"{settings.KARNATAKA_GRID_API_URL}/current"
                        if settings.KARNATAKA_GRID_API_URL
                        else ""
                    ),
                    "historical": (
                        f"{settings.KARNATAKA_GRID_API_URL}/historical"
                        if settings.KARNATAKA_GRID_API_URL
                        else ""
                    ),
                },
                api_key=settings.KARNATAKA_GRID_API_KEY,
                requires_key=bool(settings.KARNATAKA_GRID_API_URL),
                is_free=True,
                rate_limit="Depends on source",
                docs_url="",
                notes=(
                    "Karnataka state electricity grid data. "
                    "Provides: demand, generation (solar, wind, hydro, thermal), "
                    "frequency, renewable contribution, grid condition. "
                    "If KARNATAKA_GRID_API_URL is empty in .env, the system "
                    "automatically falls back to simulated/historical data. "
                    "Possible sources: KPTCL, CEA, POSOCO/NLDC open data."
                ),
            )
        )

        # ── Internal APIs (FastAPI Backend) ────────────────────────────
        # These are NOT external — they're documented here for reference
        # so the frontend team knows what endpoints exist.
        self.register(
            APIEntry(
                name="GridMind Backend API",
                key="gridmind_backend",
                base_url=f"http://{settings.HOST}:{settings.PORT}",
                endpoints={
                    "health": "/api/health",
                    "status": "/api/status",
                    "grid": "/api/grid",
                    "weather": "/api/weather",
                    "predictions": "/api/predictions",
                    "risk": "/api/risk",
                    "agents": "/api/agents",
                    "market": "/api/market",
                    "microgrid": "/api/microgrid",
                    "simulation": "/api/simulation",
                    "scenarios": "/api/scenarios",
                    "analytics": "/api/analytics",
                    "events": "/api/events",
                    "settings": "/api/settings",
                    # WebSocket endpoints
                    "ws_microgrid": "/ws/microgrid",
                    "ws_agents": "/ws/agents",
                    "ws_market": "/ws/market",
                    "ws_events": "/ws/events",
                    "ws_risk": "/ws/risk",
                },
                requires_key=False,
                is_free=True,
                docs_url=f"http://{settings.HOST}:{settings.PORT}/docs",
                notes="FastAPI auto-generates Swagger docs at /docs",
            )
        )

    # ── Registry Methods ──────────────────────────────────────────────

    def register(self, api: APIEntry) -> None:
        """Register an API entry."""
        self._apis[api.key] = api

    def get(self, key: str) -> APIEntry | None:
        """Look up an API by its key."""
        return self._apis.get(key)

    def get_url(self, key: str, endpoint: str = "") -> str:
        """Get the URL for a specific API endpoint."""
        api = self._apis.get(key)
        if not api:
            return ""
        if endpoint and endpoint in api.endpoints:
            return api.endpoints[endpoint]
        return api.base_url

    def is_available(self, key: str) -> bool:
        """Check if an API is configured and has a valid base URL."""
        api = self._apis.get(key)
        if not api:
            return False
        if api.requires_key and not api.api_key:
            return False
        return api.base_url not in ("", "N/A (simulated)")

    def list_all(self) -> dict[str, dict]:
        """Return summary of all registered APIs (safe for logging/display)."""
        result = {}
        for key, api in self._apis.items():
            result[key] = {
                "name": api.name,
                "base_url": api.base_url,
                "endpoints": list(api.endpoints.keys()),
                "requires_key": api.requires_key,
                "has_key": bool(api.api_key),
                "is_free": api.is_free,
                "is_available": self.is_available(key),
                "rate_limit": api.rate_limit,
                "docs_url": api.docs_url,
                "notes": api.notes,
            }
        return result

    def get_external_apis(self) -> dict[str, dict]:
        """Return only external APIs (excludes gridmind_backend)."""
        return {
            k: v for k, v in self.list_all().items() if k != "gridmind_backend"
        }


# ---------------------------------------------------------------------------
# Singleton instance — import this everywhere
# ---------------------------------------------------------------------------
api_registry = APIRegistry()
