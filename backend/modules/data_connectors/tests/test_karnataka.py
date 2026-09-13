"""
Tests for the Karnataka grid data path.

Covers:
- Live API precedent when configured and enabled
- Historical CSV fallback when enabled and available
- Deterministic simulation fallback as last resort
- GridStateRecord persistence + event emission
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import httpx
import pytest

from backend.common.config import settings
from backend.common.events import Events, event_bus
from backend.common.schemas.enums import DataSourceType
from backend.modules.data_connectors.grid import GridClient
from backend.modules.data_connectors.schemas import GridDataResponse


@pytest.fixture(autouse=True)
def clear_event_bus():
    event_bus.clear_all()
    yield
    event_bus.clear_all()


class TestGridClientLivePrecedence:
    """Live API is preferred when it is configured and enabled."""

    def test_live_precedence_when_configured_and_enabled(self):
        client = GridClient()
        target = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)

        with mock.patch.object(client, "_use_live_api", return_value=True):
            with mock.patch.object(client, "_fetch_live_grid_state", return_value=GridDataResponse(timestamp=target, total_demand_mw=8200.0, total_generation_mw=8300.0, solar_generation_mw=2100.0, wind_generation_mw=1200.0, grid_frequency_hz=49.95, status="STRESSED", is_simulated=False, source=DataSourceType.LIVE.value)) as live_mock:
                with mock.patch.object(client, "_fetch_historical_grid_state") as hist_mock:
                    resp = client.fetch_current_grid_state(target_time=target)

        assert resp.total_demand_mw == 8200.0
        assert resp.source == DataSourceType.LIVE.value
        assert resp.is_simulated is False
        live_mock.assert_called_once()
        hist_mock.assert_not_called()


class TestGridClientHistoricalFallback:
    """Historical CSV fallback is used when live is disabled/missing."""

    csv_path = Path(settings.PROJECT_ROOT) / "data_storage" / "datasets" / "historical_microgrid_data.csv"

    def test_historical_fallback_selected(self):
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
        hist_mock.assert_called_once()
        sim_mock.assert_not_called()

    def test_historical_missing_falls_to_simulation(self):
        client = GridClient()
        target = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)

        with mock.patch.object(client, "_use_live_api", return_value=False):
            with mock.patch.object(client, "_fetch_historical_grid_state", return_value=None):
                with mock.patch.object(client, "_simulate_grid_data") as sim_mock:
                    sim_mock.return_value = GridDataResponse(
                        timestamp=target,
                        total_demand_mw=6000.0,
                        total_generation_mw=6100.0,
                        solar_generation_mw=0.0,
                        wind_generation_mw=1000.0,
                        grid_frequency_hz=50.0,
                        status="NORMAL",
                        is_simulated=True,
                        source=DataSourceType.SIMULATED.value,
                    )
                    resp = client.fetch_current_grid_state(target_time=target)

        assert resp.is_simulated is True
        sim_mock.assert_called_once()


class TestGridClientSimulationShape:
    """Deterministic fallback produces valid Karnataka-shaped grid data."""

    def test_simulation_outputs_reasonable_karnataka_profile(self):
        client = GridClient()
        noon = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
        night = datetime(2026, 6, 15, 2, 0, tzinfo=timezone.utc)

        noon_resp = client._simulate_grid_data(noon)
        night_resp = client._simulate_grid_data(night)

        assert noon_resp.solar_generation_mw > 0
        assert night_resp.solar_generation_mw == 0.0
        assert noon_resp.total_demand_mw > 0
        assert night_resp.total_demand_mw > 0
        assert 49.0 < noon_resp.grid_frequency_hz < 51.0


class TestGridClientPersistenceAndEvents:
    """Successful reads persist a GridStateRecord and emit DATA_KARNATAKA_UPDATED."""

    def test_persist_and_publish_emits_event_and_record(self):
        client = GridClient()
        resp = GridDataResponse(
            timestamp=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
            total_demand_mw=7500.0,
            total_generation_mw=7600.0,
            solar_generation_mw=2000.0,
            wind_generation_mw=1200.0,
            grid_frequency_hz=50.0,
            status="NORMAL",
            is_simulated=False,
            source=DataSourceType.LIVE.value,
        )

        record = client.persist_and_publish(resp, condition="NORMAL", source=DataSourceType.LIVE)

        history = event_bus.get_history(limit=10, event_filter=Events.DATA_KARNATAKA_UPDATED)
        assert len(history) >= 1
        latest = history[-1]
        assert latest["event"] == Events.DATA_KARNATAKA_UPDATED
        assert latest["data"]["demand_mw"] == 7500.0
        assert latest["data"]["data_source"] == DataSourceType.LIVE.value
        assert record.condition == "NORMAL"
        assert record.demand_mw == 7500.0
