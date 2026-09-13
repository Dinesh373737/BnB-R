"""
Wind Forecasting — XGBoost Model Wrapper
===========================================
Wraps ``xgboost.XGBRegressor`` for wind generation prediction.
"""

from pathlib import Path
from typing import Optional, List

import joblib
import numpy as np
import xgboost as xgb

from backend.common.logger import get_module_logger

log = get_module_logger("ml_forecasting.wind.model")


class WindForecaster:
    """XGBoost regression model for wind generation forecasting."""

    DEFAULT_PARAMS = {
        "n_estimators": 250,
        "max_depth": 5,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 3,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "random_state": 42,
        "n_jobs": -1,
    }

    def __init__(self, params: Optional[dict] = None):
        self.params = {**self.DEFAULT_PARAMS, **(params or {})}
        self.model: Optional[xgb.XGBRegressor] = None
        self.feature_columns: Optional[List[str]] = None

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None,
    ) -> "WindForecaster":
        """Train the XGBoost model for wind generation."""
        self.feature_columns = feature_names
        self.model = xgb.XGBRegressor(**self.params)

        fit_kwargs = {}
        if X_val is not None and y_val is not None:
            fit_kwargs["eval_set"] = [(X_val, y_val)]
            fit_kwargs["verbose"] = False

        self.model.fit(X_train, y_train, **fit_kwargs)
        log.info(f"WindForecaster trained — {X_train.shape[0]} samples, "
                 f"{X_train.shape[1]} features")
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Return wind generation predictions (kW). Clipped to ≥ 0."""
        if self.model is None:
            raise RuntimeError("Model not trained. Call fit() or load() first.")
        preds = self.model.predict(X)
        return np.clip(preds, 0, None)

    def save(self, path: Path) -> None:
        """Save model + metadata to disk via joblib."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": self.model,
            "feature_columns": self.feature_columns,
            "params": self.params,
        }
        joblib.dump(payload, path)
        log.info(f"WindForecaster saved -> {path}")

    @classmethod
    def load(cls, path: Path) -> "WindForecaster":
        """Load a previously saved model."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")
        payload = joblib.load(path)
        instance = cls(params=payload.get("params"))
        instance.model = payload["model"]
        instance.feature_columns = payload.get("feature_columns")
        log.info(f"WindForecaster loaded <- {path}")
        return instance
