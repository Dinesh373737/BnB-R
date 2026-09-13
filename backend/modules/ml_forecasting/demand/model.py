"""
Demand Forecasting — XGBoost Model Wrapper
=============================================
Wraps ``xgboost.XGBRegressor`` with fit / predict / save / load helpers.
Hyperparameters are tuned for hourly demand patterns.
"""

from pathlib import Path
from typing import Optional, List

import joblib
import numpy as np
import xgboost as xgb

from backend.common.logger import get_module_logger

log = get_module_logger("ml_forecasting.demand.model")


class DemandForecaster:
    """XGBoost regression model for electricity demand forecasting."""

    # Default hyper-parameters — suitable for ~2 k rows of hourly data
    DEFAULT_PARAMS = {
        "n_estimators": 300,
        "max_depth": 6,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 5,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "random_state": 42,
        "n_jobs": -1,
    }

    def __init__(self, params: Optional[dict] = None):
        self.params = {**self.DEFAULT_PARAMS, **(params or {})}
        self.model: Optional[xgb.XGBRegressor] = None
        self.feature_columns: Optional[List[str]] = None

    # ── Training ─────────────────────────────────────────────────────────

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None,
    ) -> "DemandForecaster":
        """
        Train the XGBoost model.

        Parameters
        ----------
        X_train, y_train : array-like
            Training features and target.
        X_val, y_val : array-like, optional
            Validation set for early stopping.
        feature_names : list[str], optional
            Column names (stored for later reference).
        """
        self.feature_columns = feature_names
        self.model = xgb.XGBRegressor(**self.params)

        fit_kwargs = {}
        if X_val is not None and y_val is not None:
            fit_kwargs["eval_set"] = [(X_val, y_val)]
            fit_kwargs["verbose"] = False

        self.model.fit(X_train, y_train, **fit_kwargs)
        log.info(f"DemandForecaster trained — {X_train.shape[0]} samples, "
                 f"{X_train.shape[1]} features")
        return self

    # ── Prediction ───────────────────────────────────────────────────────

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Return demand predictions (kW). Clipped to ≥ 0."""
        if self.model is None:
            raise RuntimeError("Model not trained. Call fit() or load() first.")
        preds = self.model.predict(X)
        return np.clip(preds, 0, None)

    # ── Persistence ──────────────────────────────────────────────────────

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
        log.info(f"DemandForecaster saved -> {path}")

    @classmethod
    def load(cls, path: Path) -> "DemandForecaster":
        """Load a previously saved model."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")
        payload = joblib.load(path)
        instance = cls(params=payload.get("params"))
        instance.model = payload["model"]
        instance.feature_columns = payload.get("feature_columns")
        log.info(f"DemandForecaster loaded <- {path}")
        return instance
