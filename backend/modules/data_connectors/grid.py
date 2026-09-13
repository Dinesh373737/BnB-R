"""
Data Connectors — Grid Client

Priority chain (per project spec / live-data feature flag):
1. Real Karnataka Grid API when KARNATAKA_GRID_API_URL is configured in .env
   and settings.KARNATAKA_LIVE_DATA_ENABLED is True.
2. Historical microgrid CSV when settings.USE_HISTORICAL_DATA is True.
3. Deterministic fallback simulation otherwise.

Every successful fetch publishes the DATA_KARNATAKA_UPDATED event and persists
a GridStateRecord so downstream modules and the UI can label the data source.
"""

import csv
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from backend.common.config import settings
from backend.common.events import Events, event_bus
from backend.common.logger import get_module_logger
from backend.common.models.grid_state import GridStateRecord
from backend.common.schemas.enums import DataSourceType, GridCondition
from backend.common.database import get_db_session_context
from backend.modules.data_connectors.schemas import GridDataResponse

log = get_module_logger("modules.data_connectors.grid")


class GridClient:
    """Client for Karnataka macro-grid state with live / historical / fallback modes."""

    DATASET_PATH = Path(settings.PROJECT_ROOT) / "data_storage" / "datasets" / "historical_microgrid_data.csv"

    def __init__(self):
        self.api_url = settings.KARNATAKA_GRID_API_URL
        self.api_key = settings.KARNATAKA_GRID_API_KEY

    # ── Public API ──────────────────────────────────────────────────

    def fetch_current_grid_state(self, *, target_time: datetime | None = None) -> GridDataResponse:
        """Return the current macro grid state, preferring real data when available."""
        target = target_time or datetime.now(timezone.utc)

        if self._use_live_api():
            try:
                resp = self._fetch_live_grid_state(target)
                if resp is not None:
                    return resp
            except Exception as exc:  # noqa: PERF203
                log.warning("Karnataka grid API unavailable, falling back: %s", exc)

        if settings.USE_HISTORICAL_DATA:
            try:
                resp = self._fetch_historical_grid_state(target)
                if resp is not None:
                    return resp
            except Exception as exc:  # noqa: PERF203
                log.warning("Historical grid data unavailable, falling back: %s", exc)

        resp = self._simulate_grid_data(target)
        resp.is_simulated = True
        return resp

    # ── Mode helpers ────────────────────────────────────────────────

    def _use_live_api(self) -> bool:
        return (
            bool(self.api_url)
            and settings.KARNATAKA_LIVE_DATA_ENABLED
        )

    # ── Live API (placeholder, wired for a REST-style Karnataka endpoint) ──

    def _fetch_live_grid_state(self, target: datetime) -> GridDataResponse | None:
        """Fetch from the configured Karnataka grid API.

        The existing project configuration assumes a REST-style endpoint with a
        ``/current`` path.  The implementation mirrors the schema in
        GridDataResponse so it can be adapted to the real source without
        changing callers.
        """
        url = self.api_url.rstrip("/")
        params = {
            "timestamp": target.isoformat(),
        }
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        with httpx.Client(timeout=10.0) as client:
            response = client.get(url + "/current", params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()

        log.info("Fetched live Karnataka grid state from %s", self.api_url)
        return self._map_live_payload(payload, target, source=DataSourceType.LIVE)

    def _map_live_payload(
        self,
        payload: dict,
        target: datetime,
        *,
        source: DataSourceType,
    ) -> GridDataResponse:
        """Map a real Karnataka API payload onto GridDataResponse.

        Adapts common shapes.  Missing fields fall back to sensible defaults
        instead of failing hard.
        """
        now = target or datetime.now(timezone.utc)

        def _float(value, default=0.0) -> float:
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        demand = _float(payload.get("demand") or payload.get("demand_mw") or payload.get("total_demand"))
        generation = _float(payload.get("generation") or payload.get("total_generation_mw") or payload.get("total_generation"))
        solar = _float(payload.get("solar") or payload.get("solar_mw") or payload.get("solar_generation_mw"))
        wind = _float(payload.get("wind") or payload.get("wind_mw") or payload.get("wind_generation_mw"))
        frequency = _float(payload.get("frequency") or payload.get("grid_frequency_hz") or 50.0)

        condition_raw = payload.get("status") or payload.get("condition") or "NORMAL"
        condition = str(condition_raw).upper()
        if "OUT" in condition or condition in {"OUTAGE", "DOWN"}:
            status = GridCondition.OUTAGE.value.upper()
        elif "STRESS" in condition or condition in {"STRESSED", "STRESS"}:
            status = GridCondition.STRESSED.value.upper()
        else:
            status = GridCondition.STABLE.value.upper()

        resp = GridDataResponse(
            timestamp=now,
            total_demand_mw=demand,
            total_generation_mw=generation,
            solar_generation_mw=solar,
            wind_generation_mw=wind,
            grid_frequency_hz=frequency,
            status=status,
            is_simulated=False,
            source=source.value if hasattr(source, "value") else str(source),
        )
        return resp

    # ── Historical fallback ─────────────────────────────────────────

    def _fetch_historical_grid_state(self, target: datetime) -> GridDataResponse | None:
        """Return an interpolated observation from the bundled hourly CSV.

        The nearest *previous* and *next* hourly rows bracket the target time;
        the reading is linearly interpolated between them so consecutive
        fetches within an hour show smooth variation instead of repeating the
        same hourly value.  When the target is past the dataset end, the last
        row is blended with the deterministic diurnal model so readings keep
        evolving instead of freezing.
        """
        prev_row, next_row = _load_bracketing_grid_rows(target, self.DATASET_PATH)
        if prev_row is None:
            return None

        def _row_ts(row: dict) -> datetime:
            ts = row.get("timestamp")
            return datetime.fromisoformat(ts) if isinstance(ts, str) else ts

        prev_ts = _row_ts(prev_row)
        next_ts = _row_ts(next_row) if next_row else None

        if next_ts is not None and next_ts > prev_ts:
            fraction = (target - prev_ts).total_seconds() / (
                next_ts - prev_ts
            ).total_seconds()
            fraction = min(max(fraction, 0.0), 1.0)
            past_dataset = False
        else:
            # Target is beyond the dataset: keep evolving from the last row
            # using the deterministic diurnal model, weighted by how far past
            # the dataset we are (capped so values stay near the last reading).
            hours_past = max(0.0, (target - prev_ts).total_seconds() / 3600.0)
            fraction = min(hours_past / 24.0, 1.0)
            past_dataset = True

        def _lerp(field: str, scale: float = 1.0) -> float:
            prev_val = float(prev_row.get(field, 0.0) or 0.0)
            if next_row is None or next_ts is None:
                return prev_val
            next_val = float(next_row.get(field, 0.0) or 0.0)
            return prev_val + (next_val - prev_val) * fraction * scale

        if past_dataset:
            # Blend last historical reading with the deterministic model so
            # polls past the dataset end still vary with the time of day.
            sim = self._simulate_grid_data(target)
            w = fraction
            solar_mw = _lerp("solar_kw", 1.0) / 1000.0 * (1 - w) + sim.solar_generation_mw * w
            wind_mw = _lerp("wind_kw", 1.0) / 1000.0 * (1 - w) + sim.wind_generation_mw * w
            demand_mw = _lerp("demand_kw", 1.0) / 1000.0 * (1 - w) + sim.total_demand_mw * w
            timestamp = target
            source_confidence = 0.7
        else:
            solar_mw = _lerp("solar_kw") / 1000.0
            wind_mw = _lerp("wind_kw") / 1000.0
            demand_mw = _lerp("demand_kw") / 1000.0
            timestamp = target
            source_confidence = 0.9

        solar_mw = max(0.0, solar_mw)
        wind_mw = max(0.0, wind_mw)
        demand_mw = max(0.0, demand_mw)

        temperature_c = float(prev_row.get("temperature_c", 0.0) or 0.0)
        cloud_cover_pct = float(prev_row.get("cloud_cover_pct", 0.0) or 0.0)
        wind_speed_ms = float(prev_row.get("wind_speed_ms", 0.0) or 0.0)
        solar_radiation_wm2 = float(prev_row.get("solar_radiation_wm2", 0.0) or 0.0)

        generation_mw = max(demand_mw, solar_mw + wind_mw)

        hour = target.hour + target.minute / 60.0
        status = self._status_for(hour, demand_mw, generation_mw)

        resp = GridDataResponse(
            timestamp=timestamp,
            total_demand_mw=round(demand_mw, 3),
            total_generation_mw=round(generation_mw, 3),
            solar_generation_mw=round(solar_mw, 3),
            wind_generation_mw=round(wind_mw, 3),
            grid_frequency_hz=round(50.0 + 0.02 * math.sin(target.minute * math.pi / 30.0), 3),
            status=status,
            is_simulated=False,
        )
        resp.source = DataSourceType.HISTORICAL.value
        resp.source_confidence = source_confidence
        resp._weather_context = {
            "temperature_c": temperature_c,
            "cloud_cover_pct": cloud_cover_pct,
            "wind_speed_ms": wind_speed_ms,
            "solar_radiation_wm2": solar_radiation_wm2,
        }
        return resp

    # ── Deterministic fallback simulation ──────────────────────────

    def _simulate_grid_data(self, target: datetime) -> GridDataResponse:
        now = target or datetime.now(timezone.utc)
        hour = now.hour + now.minute / 60.0

        base_demand = 6000.0
        demand_fluctuation = math.sin(math.pi * (hour - 7) / 12) * 2000.0
        current_demand = max(0.0, base_demand + demand_fluctuation)

        if 6 <= hour <= 18:
            solar_generation = math.sin(math.pi * (hour - 6) / 12) * 3000.0
        else:
            solar_generation = 0.0

        wind_generation = 1000.0 + math.sin(math.pi * hour / 12) * 500.0
        total_generation = max(current_demand, solar_generation + wind_generation)
        frequency = 50.0 + math.sin(hour * math.pi) * 0.05

        status = self._status_for(hour, current_demand, total_generation)

        return GridDataResponse(
            timestamp=now,
            total_demand_mw=round(current_demand, 2),
            total_generation_mw=round(total_generation, 2),
            solar_generation_mw=round(solar_generation, 2),
            wind_generation_mw=round(wind_generation, 2),
            grid_frequency_hz=round(frequency, 3),
            status=status,
            is_simulated=True,
        )

    @staticmethod
    def _status_for(hour: float, demand_mw: float, generation_mw: float) -> str:
        if demand_mw <= 0:
            return GridCondition.OUTAGE.value.upper()
        if generation_mw < demand_mw * 0.85:
            return GridCondition.STRESSED.value.upper()
        if demand_mw > 8000.0:
            return GridCondition.STRESSED.value.upper()
        return GridCondition.STABLE.value.upper()

    # ── Persistence + event emission ────────────────────────────────

    def persist_and_publish(
        self,
        response: GridDataResponse,
        *,
        condition: str | None = None,
        raw_data: dict | None = None,
        source: DataSourceType | str | None = None,
    ) -> GridStateRecord | None:
        """Write the reading to ``grid_states`` and emit DATA_KARNATAKA_UPDATED.

        Duplicate readings (same timestamp + source) are skipped so that
        polling the same hourly historical row does not flood the table.
        """
        # Normalize callers that pass the raw string label (e.g. "live")
        # instead of the DataSourceType enum — both are accepted.
        if isinstance(source, str):
            source = DataSourceType(source)
        if source is None:
            source = (
                DataSourceType.SIMULATED
                if response.is_simulated
                else DataSourceType.LIVE
            )
        condition = condition or response.status

        # Skip inserting duplicate readings (same timestamp + source) so that
        # polling the same hourly historical row does not flood the table.
        # The DATA_KARNATAKA_UPDATED event still fires on every call so
        # downstream consumers (WebSocket layers, forecasts) stay in sync.
        stamp = response.timestamp.replace(tzinfo=None) if response.timestamp.tzinfo else response.timestamp
        with get_db_session_context() as db:
            existing = (
                db.query(GridStateRecord)
                .filter(
                    GridStateRecord.timestamp == stamp,
                    GridStateRecord.data_source == source.value,
                )
                .first()
            )

            if existing is not None:
                event_bus.publish(
                    Events.DATA_KARNATAKA_UPDATED,
                    {
                        "timestamp": response.timestamp.isoformat(),
                        "demand_mw": response.total_demand_mw,
                        "generation_mw": response.total_generation_mw,
                        "solar_mw": response.solar_generation_mw,
                        "wind_mw": response.wind_generation_mw,
                        "frequency_hz": response.grid_frequency_hz,
                        "condition": condition,
                        "data_source": source.value,
                        "record_id": existing.id,
                    },
                )
                return existing

        raw = raw_data or {
            "status": response.status,
            "demand_mw": response.total_demand_mw,
            "generation_mw": response.total_generation_mw,
            "solar_mw": response.solar_generation_mw,
            "wind_mw": response.wind_generation_mw,
            "frequency_hz": response.grid_frequency_hz,
            "is_simulated": response.is_simulated,
        }

        record = GridStateRecord(
            timestamp=response.timestamp,
            demand_mw=response.total_demand_mw,
            total_generation_mw=response.total_generation_mw,
            solar_mw=response.solar_generation_mw,
            wind_mw=response.wind_generation_mw,
            frequency_hz=response.grid_frequency_hz,
            condition=condition,
            data_source=source.value,
            raw_data=json.dumps(raw, default=str),
        )

        with get_db_session_context() as db:
            db.add(record)

        event_bus.publish(
            Events.DATA_KARNATAKA_UPDATED,
            {
                "timestamp": response.timestamp.isoformat(),
                "demand_mw": response.total_demand_mw,
                "generation_mw": response.total_generation_mw,
                "solar_mw": response.solar_generation_mw,
                "wind_mw": response.wind_generation_mw,
                "frequency_hz": response.grid_frequency_hz,
                "condition": condition,
                "data_source": source.value,
                "record_id": record.id,
            },
        )
        return record


# ── Historical CSV helper ───────────────────────────────────────────────

def _load_bracketing_grid_rows(
    target: datetime, path: Path
) -> tuple[dict | None, dict | None]:
    """Return the (previous, next) hourly rows bracketing ``target``.

    ``next`` is None when ``target`` is at or past the dataset end.
    """
    if not path.exists():
        return None, None

    best_prev: dict | None = None
    best_prev_delta = timedelta.max
    best_next: dict | None = None
    best_next_delta = timedelta.max

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                ts = datetime.fromisoformat(row.get("timestamp", "").strip())
            except (ValueError, TypeError):
                continue

            if ts <= target:
                delta = target - ts
                if delta < best_prev_delta:
                    best_prev_delta = delta
                    best_prev = dict(row)
            else:
                delta = ts - target
                if delta < best_next_delta:
                    best_next_delta = delta
                    best_next = dict(row)

    return best_prev, best_next


def get_historical_grid_dataframe() -> list[dict]:
    """Convenience helper for other modules that need the full historical series."""
    path = GridClient.DATASET_PATH
    if not path.exists():
        return []

    rows: list[dict] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(dict(row))
    return rows
