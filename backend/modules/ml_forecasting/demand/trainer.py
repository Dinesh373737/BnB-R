"""
Demand Forecasting — Training Pipeline
==========================================
Loads data, engineers features, splits chronologically 70/15/15,
trains the XGBoost model, evaluates on the test set, and saves the artefact.
"""

from pathlib import Path
from typing import Optional, Dict, Any

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from backend.common.config import settings
from backend.common.logger import get_module_logger
from backend.modules.ml_forecasting.data_generator import load_historical_data
from backend.modules.ml_forecasting.feature_engineering import (
    prepare_features,
    get_feature_columns,
    get_target_column,
)
from backend.modules.ml_forecasting.demand.model import DemandForecaster

log = get_module_logger("ml_forecasting.demand.trainer")

FORECAST_TYPE = "demand"
MODEL_FILENAME = "demand_xgboost.joblib"


def _safe_mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean Absolute Percentage Error, skipping zeros in y_true."""
    mask = y_true != 0
    if mask.sum() == 0:
        return 0.0
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def train_demand_model(
    df: Optional[pd.DataFrame] = None,
    model_dir: Optional[str] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """
    End-to-end training pipeline for the demand forecaster.

    Parameters
    ----------
    df : DataFrame, optional
        Pre-loaded historical data. If None, loads/generates automatically.
    model_dir : str, optional
        Directory to save the trained model. Default: ``settings.ML_MODEL_DIR``.
    force : bool
        Retrain even if a saved model already exists.

    Returns
    -------
    dict with keys: status, mae, rmse, mape, train_samples, val_samples,
                     test_samples, message, residuals (np.ndarray)
    """
    save_dir = Path(model_dir or settings.ML_MODEL_DIR)
    model_path = save_dir / MODEL_FILENAME

    if model_path.exists() and not force:
        return {
            "status": "success",
            "message": f"Model already exists at {model_path}. Use force=True to retrain.",
            "mae": None, "rmse": None, "mape": None,
            "train_samples": None, "val_samples": None, "test_samples": None,
            "residuals": None,
        }

    # 1. Load data
    data = df if df is not None else load_historical_data()
    log.info(f"Loaded {len(data)} rows for demand training")

    # 2. Feature engineering
    featured = prepare_features(data, FORECAST_TYPE)
    target_col = get_target_column(FORECAST_TYPE)
    feature_cols = get_feature_columns(FORECAST_TYPE)

    # Filter to only columns that exist
    feature_cols = [c for c in feature_cols if c in featured.columns]

    X = featured[feature_cols].values
    y = featured[target_col].values

    # 3. Chronological 70 / 15 / 15 split
    n = len(X)
    train_end = int(n * 0.70)
    val_end = int(n * 0.85)

    X_train, y_train = X[:train_end], y[:train_end]
    X_val, y_val = X[train_end:val_end], y[train_end:val_end]
    X_test, y_test = X[val_end:], y[val_end:]

    log.info(f"Split -> train={len(X_train)}, val={len(X_val)}, test={len(X_test)}")

    # 4. Train
    model = DemandForecaster()
    model.fit(X_train, y_train, X_val, y_val, feature_names=feature_cols)

    # 5. Evaluate on TEST set
    y_pred_test = model.predict(X_test)
    mae = float(mean_absolute_error(y_test, y_pred_test))
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred_test)))
    mape = _safe_mape(y_test, y_pred_test)

    # 6. Validation residuals (for uncertainty estimation)
    y_pred_val = model.predict(X_val)
    residuals = y_val - y_pred_val

    # 7. Save model
    model.save(model_path)

    # 8. Save residuals alongside model
    residuals_path = save_dir / "demand_residuals.npy"
    np.save(residuals_path, residuals)

    log.info(f"Demand test metrics - MAE: {mae:.2f} kW, RMSE: {rmse:.2f} kW, MAPE: {mape:.2f}%")

    return {
        "status": "success",
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "mape": round(mape, 4),
        "train_samples": len(X_train),
        "val_samples": len(X_val),
        "test_samples": len(X_test),
        "message": f"Demand model trained and saved to {model_path}",
        "residuals": residuals,
    }
