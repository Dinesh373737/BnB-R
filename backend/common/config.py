"""
GridMind — Centralized Configuration
======================================
Loads ALL settings from environment variables (.env file).
This is the SINGLE source of truth for every config value.

Usage by modules:
    from backend.common.config import settings
    print(settings.APP_MODE)
    print(settings.DATABASE_URL)
"""

import os
from pathlib import Path
from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# Resolve project root (BitNBuild-Energy/) — two levels up from this file
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class Settings:
    """
    All application settings loaded from environment variables.
    Modules read from this — never from os.getenv() directly.
    """

    # ── Application ───────────────────────────────────────────────────────
    APP_NAME: str = os.getenv("APP_NAME", "GridMind")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    APP_MODE: str = os.getenv("APP_MODE", "local")  # local | cloud
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # ── Server ────────────────────────────────────────────────────────────
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
    ).split(",")

    # ── Database ──────────────────────────────────────────────────────────
    DATABASE_MODE: str = os.getenv("DATABASE_MODE", "sqlite")  # sqlite | postgres
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{PROJECT_ROOT / 'data_storage' / 'gridmind.db'}",
    )

    # ── Location (Bangalore, Karnataka) ───────────────────────────────────
    LATITUDE: float = float(os.getenv("LATITUDE", "12.9716"))
    LONGITUDE: float = float(os.getenv("LONGITUDE", "77.5946"))
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Kolkata")

    # ── Weather API (Open-Meteo — free, no API key) ───────────────────────
    OPEN_METEO_BASE_URL: str = os.getenv(
        "OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1"
    )
    OPEN_METEO_FORECAST_URL: str = os.getenv(
        "OPEN_METEO_FORECAST_URL", "https://api.open-meteo.com/v1/forecast"
    )
    OPEN_METEO_HISTORICAL_URL: str = os.getenv(
        "OPEN_METEO_HISTORICAL_URL", "https://archive-api.open-meteo.com/v1/archive"
    )

    # ── Karnataka Grid Data ───────────────────────────────────────────────
    KARNATAKA_GRID_API_URL: str = os.getenv("KARNATAKA_GRID_API_URL", "")
    KARNATAKA_GRID_API_KEY: str = os.getenv("KARNATAKA_GRID_API_KEY", "")

    # ── Data Source Settings (priority: live → historical → simulated) ────
    KARNATAKA_LIVE_DATA_ENABLED: bool = (
        os.getenv("KARNATAKA_LIVE_DATA_ENABLED", "false").lower() == "true"
    )
    WEATHER_LIVE_DATA_ENABLED: bool = (
        os.getenv("WEATHER_LIVE_DATA_ENABLED", "true").lower() == "true"
    )
    USE_HISTORICAL_DATA: bool = (
        os.getenv("USE_HISTORICAL_DATA", "true").lower() == "true"
    )
    USE_SIMULATED_DATA: bool = (
        os.getenv("USE_SIMULATED_DATA", "true").lower() == "true"
    )

    # ── Simulation Defaults ───────────────────────────────────────────────
    SIMULATION_TIMESTEP_SECONDS: int = int(
        os.getenv("SIMULATION_TIMESTEP_SECONDS", "60")
    )
    DEFAULT_NUM_HOUSEHOLDS: int = int(os.getenv("DEFAULT_NUM_HOUSEHOLDS", "50"))
    DEFAULT_SOLAR_CAPACITY_KW: float = float(
        os.getenv("DEFAULT_SOLAR_CAPACITY_KW", "500.0")
    )
    DEFAULT_WIND_CAPACITY_KW: float = float(
        os.getenv("DEFAULT_WIND_CAPACITY_KW", "200.0")
    )
    DEFAULT_BATTERY_CAPACITY_KWH: float = float(
        os.getenv("DEFAULT_BATTERY_CAPACITY_KWH", "1000.0")
    )
    DEFAULT_BATTERY_MIN_SOC: float = float(
        os.getenv("DEFAULT_BATTERY_MIN_SOC", "0.10")
    )
    DEFAULT_BATTERY_MAX_SOC: float = float(
        os.getenv("DEFAULT_BATTERY_MAX_SOC", "0.95")
    )
    DEFAULT_BATTERY_CHARGE_RATE_KW: float = float(
        os.getenv("DEFAULT_BATTERY_CHARGE_RATE_KW", "100.0")
    )
    DEFAULT_BATTERY_DISCHARGE_RATE_KW: float = float(
        os.getenv("DEFAULT_BATTERY_DISCHARGE_RATE_KW", "100.0")
    )
    DEFAULT_EV_COUNT: int = int(os.getenv("DEFAULT_EV_COUNT", "20"))
    DEFAULT_EV_BATTERY_KWH: float = float(
        os.getenv("DEFAULT_EV_BATTERY_KWH", "60.0")
    )
    DEFAULT_INDUSTRIAL_LOAD_KW: float = float(
        os.getenv("DEFAULT_INDUSTRIAL_LOAD_KW", "1500.0")
    )
    DEFAULT_CRITICAL_LOAD_KW: float = float(
        os.getenv("DEFAULT_CRITICAL_LOAD_KW", "500.0")
    )
    DEFAULT_GRID_IMPORT_LIMIT_KW: float = float(
        os.getenv("DEFAULT_GRID_IMPORT_LIMIT_KW", "5000.0")
    )
    DEFAULT_GRID_EXPORT_LIMIT_KW: float = float(
        os.getenv("DEFAULT_GRID_EXPORT_LIMIT_KW", "2000.0")
    )

    # ── ML Models ─────────────────────────────────────────────────────────
    ML_MODEL_DIR: str = os.getenv(
        "ML_MODEL_DIR", str(PROJECT_ROOT / "data_storage" / "trained_models")
    )
    ML_MODEL_TYPE: str = os.getenv("ML_MODEL_TYPE", "xgboost")
    FORECAST_HORIZON_MINUTES: int = int(
        os.getenv("FORECAST_HORIZON_MINUTES", "60")
    )

    # ── WebSocket ─────────────────────────────────────────────────────────
    WEBSOCKET_ENABLED: bool = os.getenv("WEBSOCKET_ENABLED", "true").lower() == "true"
    POLLING_INTERVAL_SECONDS: int = int(
        os.getenv("POLLING_INTERVAL_SECONDS", "2")
    )

    # ── Logging ───────────────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv(
        "LOG_FILE", str(PROJECT_ROOT / "data_storage" / "gridmind.log")
    )

    # ── Groq LLM (Module 6: Agents) ───────────────────────────────────────
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    COORDINATOR_MODEL: str = os.getenv("COORDINATOR_MODEL", "openai/gpt-oss-120b")
    RISK_MODEL: str = os.getenv("RISK_MODEL", "openai/gpt-oss-120b")
    RESOURCE_MODEL: str = os.getenv("RESOURCE_MODEL", "openai/gpt-oss-120b")
    DEMAND_MODEL: str = os.getenv("DEMAND_MODEL", "openai/gpt-oss-120b")
    MARKET_MODEL: str = os.getenv("MARKET_MODEL", "openai/gpt-oss-120b")
    CRITICAL_MODEL: str = os.getenv("CRITICAL_MODEL", "openai/gpt-oss-120b")

    # ── Project Root (exposed for modules) ────────────────────────────────
    PROJECT_ROOT: Path = PROJECT_ROOT


# ---------------------------------------------------------------------------
# Singleton instance — import this everywhere
# ---------------------------------------------------------------------------
settings = Settings()
