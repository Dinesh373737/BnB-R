"""
Tests for the Open-Meteo weather data path.

Covers:
- Live API precedence when enabled
- Historical CSV fallback when enabled
- Deterministic fallback when nothing else is available
- WMO weather code mapping
"""

from datetime import datetime, timezone
from unittest import mock

import pytest

from backend.common.config import settings
from backend.common.events import Events, event_bus
from backend.common.schemas.enums import DataSourceType
from backend.modules.data_connectors.schemas import WeatherResponse
from backend.modules.data_connectors.weather import WeatherClient, _weather_code_to_condition


@pytest.fixture(autouse=True)
def clear_event_bus():
    event_bus.clear_all()
    yield
    event_bus.clear_all()


class TestWeatherClientLivePrecedence:
    """Open-Meteo is preferred when WEATHER_LIVE_DATA_ENABLED is true."""

    def test_live_fetch_when_enabled(self):
        client = WeatherClient()
        target = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
        payload = {
            "current": {
                "time": target.isoformat(),
                "temperature_2m": 31.4,
                "cloud_cover": 18.0,
                "wind_speed_10m": 4.2,
                "shortwave_radiation": 680.0,
                "weather_code": 0,
            }
        }

        with mock.patch.object(client, "_fetch_live_weather", return_value=WeatherResponse(
            timestamp=target,
            temperature_c=31.4,
            cloud_cover_percent=18.0,
            wind_speed_kmh=4.2,
            solar_radiation_wm2=680.0,
            weather_condition="clear",
            is_forecast=False,
            source=DataSourceType.LIVE.value,
        )) as live_mock:
            with mock.patch("backend.modules.data_connectors.weather.settings.WEATHER_LIVE_DATA_ENABLED", True):
                with mock.patch.object(client, "_fetch_historical_weather") as hist_mock:
                    resp = client.fetch_current_weather(target_time=target)

        assert resp.temperature_c == 31.4
        assert resp.source == DataSourceType.LIVE.value
        live_mock.assert_called_once()
        hist_mock.assert_not_called()


class TestWeatherClientHistoricalFallback:
    """Historical CSV is used when live is disabled or unavailable."""

    def test_historical_fallback_selected(self):
        client = WeatherClient()
        target = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)

        with mock.patch("backend.modules.data_connectors.weather.settings.WEATHER_LIVE_DATA_ENABLED", False):
            with mock.patch.object(client, "_fetch_historical_weather") as hist_mock:
                hist_mock.return_value = WeatherResponse(
                    timestamp=target,
                    temperature_c=33.0,
                    cloud_cover_percent=40.0,
                    wind_speed_kmh=15.0,
                    solar_radiation_wm2=520.0,
                    weather_condition="partly_cloudy",
                    is_forecast=False,
                    source=DataSourceType.HISTORICAL.value,
                )
                with mock.patch.object(client, "_get_fallback_weather") as fallback_mock:
                    resp = client.fetch_current_weather(target_time=target)

        assert resp.source == DataSourceType.HISTORICAL.value
        assert resp.temperature_c == 33.0
        hist_mock.assert_called_once()
        fallback_mock.assert_not_called()

    def test_historical_missing_falls_to_fallback(self):
        client = WeatherClient()
        target = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)

        with mock.patch("backend.modules.data_connectors.weather.settings.WEATHER_LIVE_DATA_ENABLED", False):
            with mock.patch.object(client, "_fetch_historical_weather", return_value=None):
                with mock.patch.object(client, "_get_fallback_weather") as fallback_mock:
                    fallback_mock.return_value = WeatherResponse(
                        timestamp=target,
                        temperature_c=25.0,
                        cloud_cover_percent=20.0,
                        wind_speed_kmh=10.0,
                        solar_radiation_wm2=500.0,
                        weather_condition="clear",
                        is_forecast=False,
                        source=DataSourceType.SIMULATED.value,
                    )
                    resp = client.fetch_current_weather(target_time=target)

        assert resp.is_forecast is False
        fallback_mock.assert_called_once()


class TestWeatherClientFallbackShape:
    """Fallback weather uses a realistic default profile."""

    def test_fallback_profile(self):
        client = WeatherClient()
        target = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
        resp = client._get_fallback_weather(target)

        assert resp.temperature_c == 25.0
        assert resp.cloud_cover_percent == 20.0
        assert resp.wind_speed_kmh == 10.0
        assert resp.solar_radiation_wm2 == 500.0
        assert resp.weather_condition == "clear"
        assert resp.source == DataSourceType.SIMULATED.value


class TestWMOWeatherCodeMapping:
    """WMO weather interpretation codes map to GridMind condition labels."""

    def test_clear_sky(self):
        assert _weather_code_to_condition(0) == "clear"

    def test_partly_cloudy_range(self):
        assert _weather_code_to_condition(2) == "partly_cloudy"
        assert _weather_code_to_condition(3) == "partly_cloudy"

    def test_fog_range(self):
        assert _weather_code_to_condition(45) == "fog"
        assert _weather_code_to_condition(49) == "fog"

    def test_rain_range(self):
        assert _weather_code_to_condition(51) == "rain"
        assert _weather_code_to_condition(67) == "rain"

    def test_thunderstorm_range(self):
        assert _weather_code_to_condition(95) == "thunderstorm"
        assert _weather_code_to_condition(99) == "thunderstorm"

    def test_unknown_for_unrecognized(self):
        assert _weather_code_to_condition(999) == "unknown"
