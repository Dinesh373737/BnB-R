"""
Data Connectors — Schemas
Pydantic models for weather and macro-grid responses.

The ``source`` and ``source_confidence`` fields follow the project-wide
datasource labeling convention: live, historical, simulated, derived, unavailable.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, ConfigDict


def _default_now() -> datetime:
    return datetime.now(tz=timezone.utc)


class WeatherResponse(BaseModel):
    """Schema for current weather data from Open-Meteo or historical fallback."""

    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime = Field(default_factory=_default_now, description="Time of the weather reading")
    temperature_c: float = Field(..., description="Temperature in Celsius")
    cloud_cover_percent: float = Field(..., ge=0.0, le=100.0, description="Cloud cover percentage (0-100)")
    wind_speed_kmh: float = Field(..., ge=0.0, description="Wind speed in km/h")
    solar_radiation_wm2: float = Field(0.0, ge=0.0, description="Solar radiation in W/m² (if available)")
    is_forecast: bool = Field(False, description="True if this is a future forecast, False if live/historical")
    weather_condition: str = Field("unknown", description="Simplified weather condition label")
    source: str = Field("simulated", description="Data source label: live | historical | simulated")
    source_confidence: float | None = Field(
        None, ge=0.0, le=1.0, description="Confidence in the data source"
    )
    _weather_context: dict[str, Any] | None = None  # internal metadata, not serialized


class GridDataResponse(BaseModel):
    """Schema for macro grid state (e.g., Karnataka State Grid)."""

    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime = Field(default_factory=_default_now, description="Time of the grid reading")
    total_demand_mw: float = Field(..., ge=0.0, description="Total grid demand in MW")
    total_generation_mw: float = Field(..., ge=0.0, description="Total grid generation in MW")
    solar_generation_mw: float = Field(0.0, ge=0.0, description="Solar generation in MW")
    wind_generation_mw: float = Field(0.0, ge=0.0, description="Wind generation in MW")
    grid_frequency_hz: float = Field(50.0, description="Grid frequency in Hz (typically 50Hz in India)")
    status: str = Field("NORMAL", description="Status of the grid (e.g., NORMAL, STRESSED, OUTAGE)")
    is_simulated: bool = Field(False, description="True if this is fallback/mock data, False if real API")
    source: str = Field("simulated", description="Data source label: live | historical | simulated")
    source_confidence: float | None = Field(
        None, ge=0.0, le=1.0, description="Confidence in the data source"
    )
    _weather_context: dict[str, Any] | None = None  # internal metadata for downstream reuse

    @property
    def condition_label(self) -> str:
        """Human-friendly grid condition derived from ``status``."""
        value = (self.status or "").upper()
        if "OUT" in value or value in {"OUTAGE", "DOWN"}:
            return "OUTAGE"
        if "STRESS" in value or value in {"STRESSED", "STRESS"}:
            return "STRESSED"
        return "NORMAL"
