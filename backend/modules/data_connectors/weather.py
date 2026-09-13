"""
Data Connectors — Weather Client
Fetches weather from Open-Meteo (live) with historical CSV fallback.
"""

from datetime import datetime, timezone
from pathlib import Path

import httpx

from backend.common.config import settings
from backend.common.events import Events, event_bus
from backend.common.logger import get_module_logger
from backend.common.schemas.enums import DataSourceType
from backend.modules.data_connectors.schemas import WeatherResponse

log = get_module_logger("modules.data_connectors.weather")


class WeatherClient:
    """Open-Meteo client with historical fallback from the bundled dataset."""

    DATASET_PATH = (
        Path(settings.PROJECT_ROOT)
        / "data_storage"
        / "datasets"
        / "historical_microgrid_data.csv"
    )

    def __init__(self):
        self.lat = settings.LATITUDE
        self.lon = settings.LONGITUDE
        self.timezone = settings.TIMEZONE
        self.forecast_url = settings.OPEN_METEO_FORECAST_URL
        self.archive_url = settings.OPEN_METEO_HISTORICAL_URL

    # ── Public API ────────────────────────────────────────────────

    def fetch_current_weather(self, *, target_time: datetime | None = None) -> WeatherResponse:
        """Return current weather, preferring live API when available."""
        target = target_time or datetime.now(timezone.utc)

        if settings.WEATHER_LIVE_DATA_ENABLED:
            try:
                resp = self._fetch_live_weather(target)
                if resp is not None:
                    return resp
            except Exception as exc:  # noqa: PERF203
                log.warning("Open-Meteo live fetch failed, falling back: %s", exc)

        if settings.USE_HISTORICAL_DATA:
            try:
                resp = self._fetch_historical_weather(target)
                if resp is not None:
                    return resp
            except Exception as exc:  # noqa: PERF203
                log.warning("Historical weather unavailable, falling back: %s", exc)

        return self._get_fallback_weather(target)

    # ── Live Open-Meteo ──────────────────────────────────────────

    def _fetch_live_weather(self, target: datetime) -> WeatherResponse | None:
        params = {
            "latitude": self.lat,
            "longitude": self.lon,
            "current": "temperature_2m,cloud_cover,wind_speed_10m,shortwave_radiation,weather_code",
            "timezone": self.timezone,
        }

        with httpx.Client(timeout=10.0) as client:
            response = client.get(self.forecast_url, params=params)
            response.raise_for_status()
            payload = response.json()

        log.info("Fetched live weather from Open-Meteo")
        return self._map_live_payload(payload, target)

    def _map_live_payload(self, payload: dict, target: datetime) -> WeatherResponse:
        current = payload.get("current", {})

        def _float(value, default=0.0) -> float:
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        time_str = current.get("time")
        if time_str:
            dt = datetime.fromisoformat(time_str)
        else:
            dt = target

        weather_code = int(current.get("weather_code", 0) or 0)
        condition = _weather_code_to_condition(weather_code)

        return WeatherResponse(
            timestamp=dt,
            temperature_c=_float(current.get("temperature_2m")),
            cloud_cover_percent=_float(current.get("cloud_cover")),
            wind_speed_kmh=_float(current.get("wind_speed_10m")),
            solar_radiation_wm2=_float(current.get("shortwave_radiation")),
            weather_condition=condition,
            is_forecast=False,
            source=DataSourceType.LIVE.value,
        )

    # ── Historical fallback ───────────────────────────────────────

    def _fetch_historical_weather(self, target: datetime) -> WeatherResponse | None:
        row = _load_nearest_weather_row(target, self.DATASET_PATH)
        if row is None:
            return None

        timestamp = row.get("timestamp") or target
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        return WeatherResponse(
            timestamp=timestamp,
            temperature_c=float(row.get("temperature_c", 0.0) or 0.0),
            cloud_cover_percent=float(row.get("cloud_cover_pct", 0.0) or 0.0),
            wind_speed_kmh=float(row.get("wind_speed_ms", 0.0) or 0.0) * 3.6,
            solar_radiation_wm2=float(row.get("solar_radiation_wm2", 0.0) or 0.0),
            weather_condition=row.get("weather_condition", "unknown") or "unknown",
            is_forecast=False,
            source=DataSourceType.HISTORICAL.value,
        )

    # ── Fallback ──────────────────────────────────────────────────

    def _get_fallback_weather(self, target: datetime | None = None) -> WeatherResponse:
        now = target or datetime.now(timezone.utc)
        return WeatherResponse(
            timestamp=now,
            temperature_c=25.0,
            cloud_cover_percent=20.0,
            wind_speed_kmh=10.0,
            solar_radiation_wm2=500.0,
            weather_condition="clear",
            is_forecast=False,
            source=DataSourceType.SIMULATED.value,
        )


def _weather_code_to_condition(code: int) -> str:
    """WMO weather interpretation codes -> GridMind weather condition enum values."""
    if code == 0:
        return "clear"
    if code <= 3:
        return "partly_cloudy"
    if code <= 49:
        return "fog"
    if code <= 59:
        return "rain"
    if code <= 79:
        return "rain"
    if code <= 99:
        return "thunderstorm"
    return "unknown"


def _load_nearest_weather_row(target: datetime, path: Path) -> dict | None:
    """Return the closest hourly row whose timestamp <= target."""
    if not path.exists():
        return None

    best: dict | None = None
    best_delta = None

    with path.open(newline="", encoding="utf-8") as handle:
        from csv import DictReader
        reader = DictReader(handle)
        for row in reader:
            try:
                ts = datetime.fromisoformat(row.get("timestamp", "").strip())
            except (ValueError, TypeError):
                continue

            if ts > target:
                continue

            delta = target - ts
            if best_delta is None or delta < best_delta:
                best_delta = delta
                best = dict(row)

    return best
