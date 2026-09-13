"""
GridMind — Feature Flags & Master Switch Control
===================================================
Central control panel for toggling EVERY feature in GridMind:
  - Application mode (local/cloud)
  - Database backend (sqlite/postgres)
  - Individual AI agents (on/off)
  - ML model types
  - Data sources (live/historical/simulated)
  - System features (market, safety, analytics, etc.)
  - Cloud services (AWS, S3, TwinMaker — all OFF)
  - Optional features (LangGraph, etc. — all OFF)

Usage:
    from backend.common.feature_flags import flags

    if flags.AGENT_RISK_FORECAST_ENABLED:
        run_risk_agent()

    if flags.is_local_mode:
        use_sqlite()

    print(flags.get_status_summary())
"""

import os
from backend.common.config import settings


class FeatureFlags:
    """
    Master switch board for the entire GridMind system.
    Every toggleable feature is controlled from here.
    Reads from .env, defaults to sensible values.
    """

    # ══════════════════════════════════════════════════════════════════════
    #  APPLICATION MODE
    # ══════════════════════════════════════════════════════════════════════

    @property
    def is_local_mode(self) -> bool:
        """True when running locally (SQLite, no cloud)."""
        return settings.APP_MODE == "local"

    @property
    def is_cloud_mode(self) -> bool:
        """True when deployed to cloud (PostgreSQL, AWS)."""
        return settings.APP_MODE == "cloud"

    # ══════════════════════════════════════════════════════════════════════
    #  DATABASE
    # ══════════════════════════════════════════════════════════════════════

    @property
    def use_sqlite(self) -> bool:
        return settings.DATABASE_MODE == "sqlite"

    @property
    def use_postgres(self) -> bool:
        return settings.DATABASE_MODE == "postgres"

    # ══════════════════════════════════════════════════════════════════════
    #  AI AGENTS (all ON by default)
    # ══════════════════════════════════════════════════════════════════════

    AGENT_COORDINATOR_ENABLED: bool = (
        os.getenv("AGENT_COORDINATOR_ENABLED", "true").lower() == "true"
    )
    AGENT_RISK_FORECAST_ENABLED: bool = (
        os.getenv("AGENT_RISK_FORECAST_ENABLED", "true").lower() == "true"
    )
    AGENT_MARKET_TRADING_ENABLED: bool = (
        os.getenv("AGENT_MARKET_TRADING_ENABLED", "true").lower() == "true"
    )
    AGENT_ENERGY_RESOURCE_ENABLED: bool = (
        os.getenv("AGENT_ENERGY_RESOURCE_ENABLED", "true").lower() == "true"
    )
    AGENT_DEMAND_MANAGEMENT_ENABLED: bool = (
        os.getenv("AGENT_DEMAND_MANAGEMENT_ENABLED", "true").lower() == "true"
    )
    AGENT_CRITICAL_FACILITY_ENABLED: bool = (
        os.getenv("AGENT_CRITICAL_FACILITY_ENABLED", "true").lower() == "true"
    )

    # ══════════════════════════════════════════════════════════════════════
    #  ML MODELS
    # ══════════════════════════════════════════════════════════════════════

    ML_DEMAND_FORECASTING_ENABLED: bool = (
        os.getenv("ML_DEMAND_FORECASTING_ENABLED", "true").lower() == "true"
    )
    ML_SOLAR_FORECASTING_ENABLED: bool = (
        os.getenv("ML_SOLAR_FORECASTING_ENABLED", "true").lower() == "true"
    )
    ML_WIND_FORECASTING_ENABLED: bool = (
        os.getenv("ML_WIND_FORECASTING_ENABLED", "true").lower() == "true"
    )
    ML_UNCERTAINTY_ENABLED: bool = (
        os.getenv("ML_UNCERTAINTY_ENABLED", "true").lower() == "true"
    )

    @property
    def ml_model_type(self) -> str:
        """Current ML model type: xgboost | lightgbm | sklearn"""
        return settings.ML_MODEL_TYPE

    # ══════════════════════════════════════════════════════════════════════
    #  DATA SOURCES
    # ══════════════════════════════════════════════════════════════════════

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

    # ══════════════════════════════════════════════════════════════════════
    #  CORE FEATURES
    # ══════════════════════════════════════════════════════════════════════

    WEBSOCKET_ENABLED: bool = (
        os.getenv("WEBSOCKET_ENABLED", "true").lower() == "true"
    )
    P2P_MARKET_ENABLED: bool = (
        os.getenv("P2P_MARKET_ENABLED", "true").lower() == "true"
    )
    SAFETY_VALIDATION_ENABLED: bool = (
        os.getenv("SAFETY_VALIDATION_ENABLED", "true").lower() == "true"
    )
    DIGITAL_TWIN_ENABLED: bool = (
        os.getenv("DIGITAL_TWIN_ENABLED", "true").lower() == "true"
    )
    ANALYTICS_ENABLED: bool = (
        os.getenv("ANALYTICS_ENABLED", "true").lower() == "true"
    )
    BASELINE_COMPARISON_ENABLED: bool = (
        os.getenv("BASELINE_COMPARISON_ENABLED", "true").lower() == "true"
    )
    SCENARIO_ENGINE_ENABLED: bool = (
        os.getenv("SCENARIO_ENGINE_ENABLED", "true").lower() == "true"
    )

    # ══════════════════════════════════════════════════════════════════════
    #  CLOUD / FUTURE (all OFF by default)
    # ══════════════════════════════════════════════════════════════════════

    AWS_ENABLED: bool = os.getenv("AWS_ENABLED", "false").lower() == "true"
    TWINMAKER_ENABLED: bool = (
        os.getenv("TWINMAKER_ENABLED", "false").lower() == "true"
    )
    S3_STORAGE_ENABLED: bool = (
        os.getenv("S3_STORAGE_ENABLED", "false").lower() == "true"
    )

    # ══════════════════════════════════════════════════════════════════════
    #  OPTIONAL (all OFF by default)
    # ══════════════════════════════════════════════════════════════════════

    LANGGRAPH_ENABLED: bool = (
        os.getenv("LANGGRAPH_ENABLED", "false").lower() == "true"
    )
    CONFORMAL_PREDICTION_ENABLED: bool = (
        os.getenv("CONFORMAL_PREDICTION_ENABLED", "false").lower() == "true"
    )
    LLM_EXPLANATIONS_ENABLED: bool = (
        os.getenv("LLM_EXPLANATIONS_ENABLED", "false").lower() == "true"
    )

    # ══════════════════════════════════════════════════════════════════════
    #  HELPER METHODS
    # ══════════════════════════════════════════════════════════════════════

    def get_enabled_agents(self) -> list[str]:
        """Return list of currently enabled agent names."""
        agents = []
        if self.AGENT_COORDINATOR_ENABLED:
            agents.append("coordinator")
        if self.AGENT_RISK_FORECAST_ENABLED:
            agents.append("risk_forecast")
        if self.AGENT_MARKET_TRADING_ENABLED:
            agents.append("market_trading")
        if self.AGENT_ENERGY_RESOURCE_ENABLED:
            agents.append("energy_resource")
        if self.AGENT_DEMAND_MANAGEMENT_ENABLED:
            agents.append("demand_management")
        if self.AGENT_CRITICAL_FACILITY_ENABLED:
            agents.append("critical_facility")
        return agents

    def get_enabled_forecasts(self) -> list[str]:
        """Return list of currently enabled forecast types."""
        forecasts = []
        if self.ML_DEMAND_FORECASTING_ENABLED:
            forecasts.append("demand")
        if self.ML_SOLAR_FORECASTING_ENABLED:
            forecasts.append("solar")
        if self.ML_WIND_FORECASTING_ENABLED:
            forecasts.append("wind")
        return forecasts

    def get_status_summary(self) -> dict:
        """
        Return a complete dictionary of all feature flag states.
        Useful for the /api/status endpoint and debugging.
        """
        return {
            "app_mode": settings.APP_MODE,
            "database_mode": settings.DATABASE_MODE,
            "agents": {
                "coordinator": self.AGENT_COORDINATOR_ENABLED,
                "risk_forecast": self.AGENT_RISK_FORECAST_ENABLED,
                "market_trading": self.AGENT_MARKET_TRADING_ENABLED,
                "energy_resource": self.AGENT_ENERGY_RESOURCE_ENABLED,
                "demand_management": self.AGENT_DEMAND_MANAGEMENT_ENABLED,
                "critical_facility": self.AGENT_CRITICAL_FACILITY_ENABLED,
            },
            "ml": {
                "demand_forecasting": self.ML_DEMAND_FORECASTING_ENABLED,
                "solar_forecasting": self.ML_SOLAR_FORECASTING_ENABLED,
                "wind_forecasting": self.ML_WIND_FORECASTING_ENABLED,
                "uncertainty": self.ML_UNCERTAINTY_ENABLED,
                "model_type": self.ml_model_type,
            },
            "data_sources": {
                "karnataka_live": self.KARNATAKA_LIVE_DATA_ENABLED,
                "weather_live": self.WEATHER_LIVE_DATA_ENABLED,
                "historical_data": self.USE_HISTORICAL_DATA,
                "simulated_data": self.USE_SIMULATED_DATA,
            },
            "features": {
                "websocket": self.WEBSOCKET_ENABLED,
                "p2p_market": self.P2P_MARKET_ENABLED,
                "safety_validation": self.SAFETY_VALIDATION_ENABLED,
                "digital_twin": self.DIGITAL_TWIN_ENABLED,
                "analytics": self.ANALYTICS_ENABLED,
                "baseline_comparison": self.BASELINE_COMPARISON_ENABLED,
                "scenario_engine": self.SCENARIO_ENGINE_ENABLED,
            },
            "cloud": {
                "aws": self.AWS_ENABLED,
                "twinmaker": self.TWINMAKER_ENABLED,
                "s3": self.S3_STORAGE_ENABLED,
            },
            "optional": {
                "langgraph": self.LANGGRAPH_ENABLED,
                "conformal_prediction": self.CONFORMAL_PREDICTION_ENABLED,
                "llm_explanations": self.LLM_EXPLANATIONS_ENABLED,
            },
        }


# ---------------------------------------------------------------------------
# Singleton instance — import this everywhere
# ---------------------------------------------------------------------------
flags = FeatureFlags()
