"""
ML Forecasting — Service Orchestrator
=======================================
Orchestrates demand, solar, and wind forecasting pipelines.
Handles model loading, auto-training, feature vector construction,
inference with uncertainty estimation, and database record logging.
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
import math
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from backend.common.config import settings
from backend.common.logger import get_module_logger
from backend.common.models.forecast import ForecastRecord
from backend.common.schemas.microgrid_state import ForecastState

from backend.modules.ml_forecasting.schemas import (
    ForecastRequest,
    ForecastResult,
    PredictionsSummary,
    TrainResult,
    TrainResponse,
)
from backend.modules.ml_forecasting.data_generator import load_historical_data
from backend.modules.ml_forecasting.feature_engineering import (
    prepare_features,
    get_feature_columns,
    get_target_column,
    DEFAULT_LAGS,
    DEFAULT_WINDOWS,
)
from backend.modules.ml_forecasting.demand.model import DemandForecaster
from backend.modules.ml_forecasting.demand.trainer import train_demand_model, MODEL_FILENAME as DEMAND_MODEL_FILE
from backend.modules.ml_forecasting.solar.model import SolarForecaster
from backend.modules.ml_forecasting.solar.trainer import train_solar_model, MODEL_FILENAME as SOLAR_MODEL_FILE
from backend.modules.ml_forecasting.wind.model import WindForecaster
from backend.modules.ml_forecasting.wind.trainer import train_wind_model, MODEL_FILENAME as WIND_MODEL_FILE
from backend.modules.ml_forecasting.uncertainty.estimator import UncertaintyEstimator

log = get_module_logger("ml_forecasting.service")


class ForecastingService:
    """Central service coordinating ML forecasting models and pipelines."""

    _instance: Optional["ForecastingService"] = None

    def __init__(self, model_dir: Optional[str] = None):
        self.model_dir = Path(model_dir or settings.ML_MODEL_DIR)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        self.demand_model: Optional[DemandForecaster] = None
        self.solar_model: Optional[SolarForecaster] = None
        self.wind_model: Optional[WindForecaster] = None

        self.demand_uncertainty = UncertaintyEstimator(forecast_type="demand", model_dir=str(self.model_dir))
        self.solar_uncertainty = UncertaintyEstimator(forecast_type="solar", model_dir=str(self.model_dir))
        self.wind_uncertainty = UncertaintyEstimator(forecast_type="wind", model_dir=str(self.model_dir))

        self._historical_data_cache: Optional[pd.DataFrame] = None
        self.load_models()

    @classmethod
    def get_instance(cls, model_dir: Optional[str] = None) -> "ForecastingService":
        """Singleton accessor for ForecastingService."""
        if cls._instance is None:
            cls._instance = cls(model_dir=model_dir)
        return cls._instance

    # ── Model Lifecycle ──────────────────────────────────────────────────

    def load_models(self) -> None:
        """Load trained models from disk, or initialize empty models."""
        # Demand
        demand_path = self.model_dir / DEMAND_MODEL_FILE
        if demand_path.exists():
            try:
                self.demand_model = DemandForecaster.load(demand_path)
                log.info(f"Loaded Demand model from {demand_path}")
            except Exception as e:
                log.warning(f"Failed to load demand model: {e}")
                self.demand_model = None
        else:
            self.demand_model = None

        # Solar
        solar_path = self.model_dir / SOLAR_MODEL_FILE
        if solar_path.exists():
            try:
                self.solar_model = SolarForecaster.load(solar_path)
                log.info(f"Loaded Solar model from {solar_path}")
            except Exception as e:
                log.warning(f"Failed to load solar model: {e}")
                self.solar_model = None
        else:
            self.solar_model = None

        # Wind
        wind_path = self.model_dir / WIND_MODEL_FILE
        if wind_path.exists():
            try:
                self.wind_model = WindForecaster.load(wind_path)
                log.info(f"Loaded Wind model from {wind_path}")
            except Exception as e:
                log.warning(f"Failed to load wind model: {e}")
                self.wind_model = None
        else:
            self.wind_model = None

    def ensure_models_trained(self) -> None:
        """Ensure all three models are trained and loaded into memory."""
        needs_training = []
        if self.demand_model is None:
            needs_training.append("demand")
        if self.solar_model is None:
            needs_training.append("solar")
        if self.wind_model is None:
            needs_training.append("wind")

        if needs_training:
            log.info(f"Models {needs_training} not loaded; running training pipeline...")
            self.train(forecast_types=needs_training, force=False)

    def train(
        self,
        forecast_types: Optional[List[str]] = None,
        force: bool = False,
    ) -> TrainResponse:
        """
        Train specified models (or all if not specified) and reload them.
        """
        targets = forecast_types or ["demand", "solar", "wind"]
        results: List[TrainResult] = []

        # Pre-load or generate data once for all models
        df = self.get_historical_data()

        if "demand" in targets:
            try:
                res = train_demand_model(df=df, model_dir=str(self.model_dir), force=force)
                self.demand_model = DemandForecaster.load(self.model_dir / DEMAND_MODEL_FILE)
                self.demand_uncertainty = UncertaintyEstimator(forecast_type="demand", model_dir=str(self.model_dir))
                results.append(TrainResult(
                    forecast_type="demand",
                    status="success",
                    mae=res.get("mae"),
                    rmse=res.get("rmse"),
                    mape=res.get("mape"),
                    train_samples=res.get("train_samples"),
                    val_samples=res.get("val_samples"),
                    test_samples=res.get("test_samples"),
                    message=res.get("message"),
                ))
            except Exception as e:
                log.error(f"Demand model training failed: {e}")
                results.append(TrainResult(
                    forecast_type="demand",
                    status="error",
                    message=str(e),
                ))

        if "solar" in targets:
            try:
                res = train_solar_model(df=df, model_dir=str(self.model_dir), force=force)
                self.solar_model = SolarForecaster.load(self.model_dir / SOLAR_MODEL_FILE)
                self.solar_uncertainty = UncertaintyEstimator(forecast_type="solar", model_dir=str(self.model_dir))
                results.append(TrainResult(
                    forecast_type="solar",
                    status="success",
                    mae=res.get("mae"),
                    rmse=res.get("rmse"),
                    mape=res.get("mape"),
                    train_samples=res.get("train_samples"),
                    val_samples=res.get("val_samples"),
                    test_samples=res.get("test_samples"),
                    message=res.get("message"),
                ))
            except Exception as e:
                log.error(f"Solar model training failed: {e}")
                results.append(TrainResult(
                    forecast_type="solar",
                    status="error",
                    message=str(e),
                ))

        if "wind" in targets:
            try:
                res = train_wind_model(df=df, model_dir=str(self.model_dir), force=force)
                self.wind_model = WindForecaster.load(self.model_dir / WIND_MODEL_FILE)
                self.wind_uncertainty = UncertaintyEstimator(forecast_type="wind", model_dir=str(self.model_dir))
                results.append(TrainResult(
                    forecast_type="wind",
                    status="success",
                    mae=res.get("mae"),
                    rmse=res.get("rmse"),
                    mape=res.get("mape"),
                    train_samples=res.get("train_samples"),
                    val_samples=res.get("val_samples"),
                    test_samples=res.get("test_samples"),
                    message=res.get("message"),
                ))
            except Exception as e:
                log.error(f"Wind model training failed: {e}")
                results.append(TrainResult(
                    forecast_type="wind",
                    status="error",
                    message=str(e),
                ))

        return TrainResponse(results=results, models_dir=str(self.model_dir))

    # ── Historical Data Access ───────────────────────────────────────────

    def get_historical_data(self) -> pd.DataFrame:
        """Fetch or generate historical data."""
        if self._historical_data_cache is None or len(self._historical_data_cache) == 0:
            self._historical_data_cache = load_historical_data()
        return self._historical_data_cache

    # ── Feature Construction for Inference ───────────────────────────────

    def _build_feature_row(
        self,
        forecast_type: str,
        target_timestamp: datetime,
        current_value: Optional[float] = None,
        weather_override: Optional[Dict[str, float]] = None,
    ) -> pd.DataFrame:
        """
        Construct a single-row DataFrame containing all features required by the model.
        Uses historical data to compute lag and rolling values, updated with current values.
        """
        data = self.get_historical_data().copy()
        target_col = get_target_column(forecast_type)
        expected_cols = get_feature_columns(forecast_type)

        # Recent slice of history to compute lags and rolling windows
        recent = data.tail(30).copy()

        # If current value is provided, append/replace last observation
        if current_value is not None:
            last_row = recent.iloc[-1].copy()
            last_row[target_col] = float(current_value)
            last_row["timestamp"] = target_timestamp - timedelta(hours=1)
            recent = pd.concat([recent, pd.DataFrame([last_row])], ignore_index=True)

        hour = target_timestamp.hour
        day_of_week = target_timestamp.weekday()
        month = target_timestamp.month
        is_weekend = 1 if day_of_week >= 5 else 0

        features: Dict[str, Any] = {
            "hour": hour,
            "day_of_week": day_of_week,
            "month": month,
            "is_weekend": is_weekend,
            "hour_sin": math.sin(2 * math.pi * hour / 24.0),
            "hour_cos": math.cos(2 * math.pi * hour / 24.0),
        }

        # Lag features
        target_series = recent[target_col].values
        n_samples = len(target_series)
        for k in DEFAULT_LAGS:
            col_name = f"{target_col}_lag_{k}"
            idx = n_samples - k
            if idx >= 0:
                features[col_name] = float(target_series[idx])
            else:
                features[col_name] = float(target_series[0])

        # Rolling features
        shifted = pd.Series(target_series)
        for w in DEFAULT_WINDOWS:
            col_name = f"{target_col}_rolling_{w}h"
            val = float(shifted.tail(w).mean())
            features[col_name] = val
        features[f"{target_col}_rolling_24h_std"] = float(shifted.tail(24).std() or 0.0)

        # Weather features
        last_weather = recent.iloc[-1]
        temp = last_weather.get("temperature_c", 27.0)
        cloud = last_weather.get("cloud_cover_pct", 30.0)
        wind_sp = last_weather.get("wind_speed_ms", 5.0)
        solar_rad = last_weather.get("solar_radiation_wm2", 0.0)

        if weather_override:
            temp = weather_override.get("temperature_c", temp)
            cloud = weather_override.get("cloud_cover_pct", cloud)
            wind_sp = weather_override.get("wind_speed_ms", wind_sp)
            solar_rad = weather_override.get("solar_radiation_wm2", solar_rad)

        features["temperature_c"] = float(temp)
        features["cloud_cover_pct"] = float(cloud)
        features["wind_speed_ms"] = float(wind_sp)
        features["solar_radiation_wm2"] = float(solar_rad)

        row_df = pd.DataFrame([features])
        # Select only expected columns
        cols_to_use = [c for c in expected_cols if c in row_df.columns]
        return row_df[cols_to_use]

    # ── Prediction Methods ───────────────────────────────────────────────

    def predict_demand(
        self,
        request: Optional[ForecastRequest] = None,
        db: Optional[Session] = None,
    ) -> ForecastResult:
        """Generate demand forecast with uncertainty intervals."""
        self.ensure_models_trained()
        req = request or ForecastRequest(forecast_type="demand")

        now = datetime.now(timezone.utc)
        horizon = req.horizon_minutes or 60
        target_time = now + timedelta(minutes=horizon)

        weather_override = {}
        if req.temperature_c is not None:
            weather_override["temperature_c"] = req.temperature_c

        feat_df = self._build_feature_row(
            "demand",
            target_timestamp=target_time,
            current_value=req.current_value,
            weather_override=weather_override,
        )

        pred_val = float(self.demand_model.predict(feat_df.values)[0])
        lower, upper, confidence = self.demand_uncertainty.estimate(pred_val)

        result = ForecastResult(
            forecast_type="demand",
            timestamp=target_time,
            current_value=req.current_value,
            prediction=round(pred_val, 2),
            lower=lower,
            upper=upper,
            confidence=confidence,
            horizon_minutes=horizon,
            model_type=settings.ML_MODEL_TYPE,
            unit="kW",
        )

        self._save_record_to_db(result, db)
        return result

    def predict_solar(
        self,
        request: Optional[ForecastRequest] = None,
        db: Optional[Session] = None,
    ) -> ForecastResult:
        """Generate solar forecast with uncertainty intervals."""
        self.ensure_models_trained()
        req = request or ForecastRequest(forecast_type="solar")

        now = datetime.now(timezone.utc)
        horizon = req.horizon_minutes or 60
        target_time = now + timedelta(minutes=horizon)

        # Solar night-time physical constraint check (6:00 to 18:00 daylight)
        local_hour = (target_time.hour + 5.5) % 24  # Approximate IST
        is_night = local_hour < 6 or local_hour > 18.5

        weather_override = {}
        if req.temperature_c is not None:
            weather_override["temperature_c"] = req.temperature_c
        if req.cloud_cover_pct is not None:
            weather_override["cloud_cover_pct"] = req.cloud_cover_pct
        if req.solar_radiation_wm2 is not None:
            weather_override["solar_radiation_wm2"] = req.solar_radiation_wm2

        feat_df = self._build_feature_row(
            "solar",
            target_timestamp=target_time,
            current_value=req.current_value,
            weather_override=weather_override,
        )

        raw_pred = float(self.solar_model.predict(feat_df.values)[0])
        pred_val = 0.0 if is_night else max(0.0, raw_pred)

        lower, upper, confidence = self.solar_uncertainty.estimate(pred_val)
        if is_night:
            lower, upper, confidence = 0.0, 0.0, "high"

        result = ForecastResult(
            forecast_type="solar",
            timestamp=target_time,
            current_value=req.current_value,
            prediction=round(pred_val, 2),
            lower=lower,
            upper=upper,
            confidence=confidence,
            horizon_minutes=horizon,
            model_type=settings.ML_MODEL_TYPE,
            unit="kW",
        )

        self._save_record_to_db(result, db)
        return result

    def predict_wind(
        self,
        request: Optional[ForecastRequest] = None,
        db: Optional[Session] = None,
    ) -> ForecastResult:
        """Generate wind forecast with uncertainty intervals."""
        self.ensure_models_trained()
        req = request or ForecastRequest(forecast_type="wind")

        now = datetime.now(timezone.utc)
        horizon = req.horizon_minutes or 60
        target_time = now + timedelta(minutes=horizon)

        weather_override = {}
        if req.temperature_c is not None:
            weather_override["temperature_c"] = req.temperature_c
        if req.wind_speed_ms is not None:
            weather_override["wind_speed_ms"] = req.wind_speed_ms

        feat_df = self._build_feature_row(
            "wind",
            target_timestamp=target_time,
            current_value=req.current_value,
            weather_override=weather_override,
        )

        pred_val = float(self.wind_model.predict(feat_df.values)[0])
        lower, upper, confidence = self.wind_uncertainty.estimate(pred_val)

        result = ForecastResult(
            forecast_type="wind",
            timestamp=target_time,
            current_value=req.current_value,
            prediction=round(pred_val, 2),
            lower=lower,
            upper=upper,
            confidence=confidence,
            horizon_minutes=horizon,
            model_type=settings.ML_MODEL_TYPE,
            unit="kW",
        )

        self._save_record_to_db(result, db)
        return result

    def predict_all(self, db: Optional[Session] = None) -> PredictionsSummary:
        """Generate demand, solar, and wind forecasts together with summary balance."""
        demand = self.predict_demand(db=db)
        solar = self.predict_solar(db=db)
        wind = self.predict_wind(db=db)

        tot_gen = round(solar.prediction + wind.prediction, 2)
        net_pos = round(tot_gen - demand.prediction, 2)

        return PredictionsSummary(
            timestamp=datetime.now(timezone.utc),
            demand=demand,
            solar=solar,
            wind=wind,
            total_generation_forecast=tot_gen,
            net_position=net_pos,
        )

    def get_forecast_state(self, db: Optional[Session] = None) -> ForecastState:
        """
        Produce a ForecastState object ready to populate MicrogridState.forecast.
        """
        summary = self.predict_all(db=db)
        confidences = [summary.demand.confidence, summary.solar.confidence, summary.wind.confidence]
        if "low" in confidences:
            system_uncertainty = "high"
        elif "medium" in confidences:
            system_uncertainty = "medium"
        else:
            system_uncertainty = "low"

        return ForecastState(
            demand_forecast_kw=summary.demand.prediction,
            demand_lower_kw=summary.demand.lower,
            demand_upper_kw=summary.demand.upper,
            solar_forecast_kw=summary.solar.prediction,
            solar_lower_kw=summary.solar.lower,
            solar_upper_kw=summary.solar.upper,
            wind_forecast_kw=summary.wind.prediction,
            wind_lower_kw=summary.wind.lower,
            wind_upper_kw=summary.wind.upper,
            forecast_horizon_minutes=60,
            uncertainty_level=system_uncertainty,
        )

    def _save_record_to_db(self, result: ForecastResult, db: Optional[Session]) -> None:
        """Persist a ForecastRecord to the database if a session is provided."""
        if db is None:
            return
        try:
            record = ForecastRecord(
                timestamp=result.timestamp,
                forecast_type=result.forecast_type,
                current_value=result.current_value,
                forecast_value=result.prediction,
                lower_bound=result.lower,
                upper_bound=result.upper,
                confidence=result.confidence,
                horizon_minutes=result.horizon_minutes,
                model_type=result.model_type,
                data_source="simulated",
            )
            db.add(record)
            db.commit()
        except Exception as e:
            log.warning(f"Failed to persist ForecastRecord to DB: {e}")
            db.rollback()
