"""
GridMind — Base Pydantic Schemas
==================================
Shared base schemas used across all modules.
All module-specific schemas should inherit from these.

Usage:
    from backend.common.schemas.base import BaseResponse, TimestampMixin
"""

from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, ConfigDict


T = TypeVar("T")


# ══════════════════════════════════════════════════════════════════════════
#  MIXINS
# ══════════════════════════════════════════════════════════════════════════


class TimestampMixin(BaseModel):
    """Mixin adding timestamp fields."""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime | None = None


class IDMixin(BaseModel):
    """Mixin adding an integer ID field."""
    id: int


# ══════════════════════════════════════════════════════════════════════════
#  BASE RESPONSE SCHEMAS
# ══════════════════════════════════════════════════════════════════════════


class BaseResponse(BaseModel):
    """Standard API response wrapper."""
    model_config = ConfigDict(from_attributes=True)

    success: bool = True
    message: str = ""


class DataResponse(BaseResponse, Generic[T]):
    """API response with data payload."""
    data: T | None = None


class ErrorResponse(BaseResponse):
    """API error response."""
    success: bool = False
    error_code: str = ""
    detail: str = ""


class PaginatedResponse(BaseResponse, Generic[T]):
    """Paginated API response."""
    data: list[T] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50
    has_next: bool = False
    has_prev: bool = False


# ══════════════════════════════════════════════════════════════════════════
#  HEALTH / STATUS
# ══════════════════════════════════════════════════════════════════════════


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    app_name: str = ""
    version: str = ""
    uptime_seconds: float = 0.0
    database: str = "connected"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StatusResponse(BaseModel):
    """Full system status including feature flags."""
    health: HealthResponse
    feature_flags: dict[str, Any] = Field(default_factory=dict)
    apis: dict[str, Any] = Field(default_factory=dict)
    enabled_agents: list[str] = Field(default_factory=list)
    enabled_forecasts: list[str] = Field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════
#  COMMON REQUEST SCHEMAS
# ══════════════════════════════════════════════════════════════════════════


class PaginationParams(BaseModel):
    """Standard pagination parameters."""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)


class TimeRangeParams(BaseModel):
    """Time range filter parameters."""
    start_time: datetime | None = None
    end_time: datetime | None = None


class DataSourceLabel(BaseModel):
    """
    Labels a data value with its source type.
    Per the doc: show LIVE / HISTORICAL / SIMULATED / DERIVED / UNAVAILABLE
    """
    value: Any
    source: str = "simulated"  # DataSourceType value
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confidence: float | None = None
