"""
Data Connectors — API Router
Exposes live/historical/simulated weather and Karnataka grid endpoints.

Public surface:
    GET /api/data/weather          current weather (with source label)
    GET /api/data/grid             current macro-grid state (with source label)
    GET /api/data/grid/history     recent grid-state snapshots from DB
    GET /api/data/weather/history  recent weather snapshots from DB
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.common.database import get_db_session
from backend.common.logger import get_module_logger
from backend.common.models.grid_state import GridStateRecord
from backend.common.schemas.base import DataSourceLabel
from backend.modules.data_connectors.schemas import GridDataResponse, WeatherResponse
from backend.modules.data_connectors.service import DataConnectorService

log = get_module_logger("modules.data_connectors.router")

router = APIRouter(prefix="/api/data", tags=["Data Connectors"])


def get_data_service() -> DataConnectorService:
    return DataConnectorService()


# ── Live / latest data ─────────────────────────────────────────────


@router.get("/weather", response_model=WeatherResponse)
def get_weather(
    service: DataConnectorService = Depends(get_data_service),
    as_of: datetime | None = Query(
        None, description="Timestamp to use as 'now' for testing/historical lookups"
    ),
):
    """Retrieve current weather for the configured location (Bangalore).

    The response includes a ``source`` label so the UI can display whether the
    value came from a live API, historical data, or a simulation fallback.
    """
    return service.get_current_weather(as_of=as_of)


@router.get("/grid", response_model=GridDataResponse)
def get_grid(
    service: DataConnectorService = Depends(get_data_service),
    as_of: datetime | None = Query(
        None, description="Timestamp to use as 'now' for testing/historical lookups"
    ),
):
    """Retrieve the current macro-level grid status (Karnataka Grid).

    When a real Karnataka API is configured in ``.env``, this returns live data.
    Otherwise it falls back to historical observations or deterministic simulation.
    """
    return service.get_current_grid_state(as_of=as_of)


# ── Historical snapshots (persisted to DB) ─────────────────────────


@router.get("/grid/history", response_model=list[GridDataResponse])
def get_grid_history(
    limit: int = Query(50, ge=1, le=500),
    before: datetime | None = Query(
        None, description="Return snapshots before this timestamp"
    ),
    db: Session = Depends(get_db_session),
):
    """Return recent Karnataka grid snapshots persisted by the module."""
    query = db.query(GridStateRecord).order_by(GridStateRecord.timestamp.desc())
    if before:
        query = query.filter(GridStateRecord.timestamp < before)
    records = query.limit(limit).all()

    def _to_response(record: GridStateRecord) -> GridDataResponse:
        raw = getattr(record, "raw_data", "") or "{}"
        try:
            parsed = __import__("json", fromlist=["loads"]).loads(raw)
        except Exception:
            parsed = {}

        return GridDataResponse(
            timestamp=record.timestamp or datetime.now(timezone.utc),
            total_demand_mw=record.demand_mw or 0.0,
            total_generation_mw=record.total_generation_mw or 0.0,
            solar_generation_mw=record.solar_mw or 0.0,
            wind_generation_mw=record.wind_mw or 0.0,
            grid_frequency_hz=record.frequency_hz or 50.0,
            status=record.condition or "NORMAL",
            is_simulated=(record.data_source == "simulated"),
            source=record.data_source or "simulated",
        )

    return [_to_response(record) for record in records]


@router.get("/weather/history", response_model=list[WeatherResponse])
def get_weather_history(
    limit: int = Query(50, ge=1, le=500),
    before: datetime | None = Query(
        None, description="Return snapshots before this timestamp"
    ),
    db: Session = Depends(get_db_session),
):
    """Return recent weather snapshots from the persisted ``weather_data`` table.

    Weather responses are persisted by the forecasting/simulation layers when
    available; this endpoint gives the UI a stable historical view.
    """
    from backend.common.models.weather import WeatherDataRecord

    query = (
        db.query(WeatherDataRecord)
        .order_by(WeatherDataRecord.timestamp.desc())
        .limit(limit)
    )
    if before:
        query = query.filter(WeatherDataRecord.timestamp < before)

    records = query.all()

    def _to_response(record: WeatherDataRecord) -> WeatherResponse:
        return WeatherResponse(
            timestamp=record.timestamp or datetime.now(timezone.utc),
            temperature_c=record.temperature_c or 0.0,
            cloud_cover_percent=record.cloud_cover_pct or 0.0,
            wind_speed_kmh=(record.wind_speed_ms or 0.0) * 3.6,
            solar_radiation_wm2=record.solar_radiation_wm2 or 0.0,
            is_forecast=False,
            weather_condition=record.weather_condition or "unknown",
            source=record.data_source or "simulated",
        )

    return [_to_response(record) for record in records]
