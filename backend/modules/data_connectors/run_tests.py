#!/usr/bin/env python
"""
Quick test runner for Module 1: Data Connectors

Run with:
    python backend/modules/data_connectors/run_tests.py

This exercises:
- WeatherClient (live -> historical -> fallback)
- GridClient (live -> historical -> fallback)
- DataConnectorService
"""

import sys
from datetime import datetime, timezone
from unittest import mock

# Add parent to path
sys.path.insert(0, 'backend')

from backend.modules.data_connectors.service import DataConnectorService
from backend.modules.data_connectors.grid import GridClient
from backend.modules.data_connectors.weather import WeatherClient
from backend.modules.data_connectors.schemas import GridDataResponse, WeatherResponse
from backend.common.schemas.enums import DataSourceType


def test_weather_live_path():
    """Simulate live Open-Meteo response."""
    print("Testing weather live path...", end=" ")
    client = WeatherClient()
    target = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
    payload = {
        "current": {
            "time": target.isoformat(),
            "temperature_2m": 31.0,
            "cloud_cover": 15.0,
            "wind_speed_10m": 3.5,
            "shortwave_radiation": 720.0,
            "weather_code": 0,
        }
    }

    with mock.patch.object(client, "_fetch_live_weather") as live_mock:
        live_mock.return_value = client._map_live_payload(payload, target)
        with mock.patch("backend.modules.data_connectors.weather.settings.WEATHER_LIVE_DATA_ENABLED", True):
            with mock.patch.object(client, "_fetch_historical_weather") as hist_mock:
                resp = client.fetch_current_weather(target_time=target)

    assert resp.source == DataSourceType.LIVE.value, f"Expected live source, got {resp.source}"
    assert resp.temperature_c == 31.0
    assert resp.cloud_cover_percent == 15.0
    assert resp.wind_speed_kmh == 3.5
    assert resp.solar_radiation_wm2 == 720.0
    assert resp.weather_condition == "clear"
    print("✓")


def test_weather_historical_path():
    """Test historical CSV path."""
    print("Testing weather historical path...", end=" ")
    client = WeatherClient()
    target = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)

    with mock.patch("backend.modules.data_connectors.weather.settings.WEATHER_LIVE_DATA_ENABLED", False):
        with mock.patch.object(client, "_fetch_historical_weather") as hist_mock:
            hist_mock.return_value = WeatherResponse(
                timestamp=target,
                temperature_c=32.0,
                cloud_cover_percent=45.0,
                wind_speed_kmh=12.0,
                solar_radiation_wm2=550.0,
                weather_condition="partly_cloudy",
                is_forecast=False,
                source=DataSourceType.HISTORICAL.value,
            )
            with mock.patch.object(client, "_get_fallback_weather") as fb_mock:
                resp = client.fetch_current_weather(target_time=target)

    assert resp.source == DataSourceType.HISTORICAL.value
    assert resp.temperature_c == 32.0
    print("✓")


def test_grid_live_path():
    """Test live Karnataka grid path."""
    print("Testing grid live path...", end=" ")
    client = GridClient()
    target = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
    payload = {
        "demand": 7500.0,
        "generation": 7600.0,
        "solar": 2000.0,
        "wind": 1200.0,
        "frequency": 49.95,
        "status": "STRESSED",
    }

    with mock.patch.object(client, "_use_live_api", return_value=True):
        with mock.patch.object(client, "_fetch_live_grid_state") as live_mock:
            live_mock.return_value = client._map_live_payload(payload, target, source=DataSourceType.LIVE)
            with mock.patch.object(client, "_fetch_historical_grid_state") as hist_mock:
                resp = client.fetch_current_grid_state(target_time=target)

    assert resp.source == DataSourceType.LIVE.value
    assert resp.total_demand_mw == 7500.0
    assert resp.status == "STRESSED"
    print("✓")


def test_grid_historical_path():
    """Test historical CSV fallback path."""
    print("Testing grid historical path...", end=" ")
    client = GridClient()
    target = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)

    with mock.patch.object(client, "_use_live_api", return_value=False):
        with mock.patch.object(client, "_fetch_historical_grid_state") as hist_mock:
            hist_mock.return_value = GridDataResponse(
                timestamp=target,
                total_demand_mw=2.9,
                total_generation_mw=3.0,
                solar_generation_mw=0.3,
                wind_generation_mw=0.05,
                grid_frequency_hz=50.0,
                status="NORMAL",
                is_simulated=False,
                source=DataSourceType.HISTORICAL.value,
            )
            with mock.patch.object(client, "_simulate_grid_data") as sim_mock:
                resp = client.fetch_current_grid_state(target_time=target)

    assert resp.source == DataSourceType.HISTORICAL.value
    assert resp.is_simulated is False
    print("✓")


def test_grid_simulation_fallback():
    """Test deterministic simulation fallback."""
    print("Testing grid simulation fallback...", end=" ")
    client = GridClient()
    noon = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
    resp = client._simulate_grid_data(noon)

    assert resp.solar_generation_mw > 0
    assert resp.total_demand_mw > 0
    assert resp.is_simulated is True
    print("✓")


def test_service_integration():
    """Test the service layer orchestrates correctly."""
    print("Testing service integration...", end=" ")
    service = DataConnectorService()

    with mock.patch.object(service.weather_client, "fetch_current_weather") as wf:
        wf.return_value = WeatherResponse(
            timestamp=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
            temperature_c=30.0,
            cloud_cover_percent=30.0,
            wind_speed_kmh=8.0,
            solar_radiation_wm2=600.0,
            weather_condition="partly_cloudy",
            is_forecast=False,
            source=DataSourceType.HISTORICAL.value,
        )
        with mock.patch.object(service.grid_client, "fetch_current_grid_state") as gf:
            gf.return_value = GridDataResponse(
                timestamp=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
                total_demand_mw=7000.0,
                total_generation_mw=7100.0,
                solar_generation_mw=1800.0,
                wind_generation_mw=1000.0,
                grid_frequency_hz=50.0,
                status="NORMAL",
                is_simulated=False,
                source=DataSourceType.HISTORICAL.value,
            )
            # Patch persist_and_publish to avoid DB calls
            with mock.patch.object(service.grid_client, "persist_and_publish") as pp:
                pp.return_value = mock.MagicMock()
                weather = service.get_current_weather()
                grid = service.get_current_grid_state()

    assert weather.source == DataSourceType.HISTORICAL.value
    assert grid.source == DataSourceType.HISTORICAL.value
    print("✓")


if __name__ == "__main__":
    print("=" * 60)
    print("Module 1: Data Connectors - Data Flow Tests")
    print("=" * 60)
    print()

    try:
        test_weather_live_path()
        test_weather_historical_path()
        test_grid_live_path()
        test_grid_historical_path()
        test_grid_simulation_fallback()
        test_service_integration()

        print()
        print("=" * 60)
        print("All Module 1 data flow tests passed!")
        print("=" * 60)
    except Exception as e:
        print()
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
