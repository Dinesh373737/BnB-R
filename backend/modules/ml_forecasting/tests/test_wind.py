"""
Tests for ML Forecasting — Wind Forecaster & Trainer
"""

import numpy as np
import pytest
from pathlib import Path

from backend.modules.ml_forecasting.data_generator import generate_historical_data
from backend.modules.ml_forecasting.wind.model import WindForecaster
from backend.modules.ml_forecasting.wind.trainer import train_wind_model


@pytest.fixture(scope="module")
def shared_data(tmp_path_factory):
    tmp_dir = tmp_path_factory.mktemp("data")
    return generate_historical_data(days=14, seed=42, output_dir=tmp_dir)


def test_wind_model_fit_predict(tmp_path):
    X = np.random.randn(100, 8)
    y = np.maximum(0, 100.0 + 20.0 * np.random.randn(100))

    model = WindForecaster(params={"n_estimators": 10, "max_depth": 3})
    model.fit(X, y)

    preds = model.predict(X[:5])
    assert len(preds) == 5
    assert (preds >= 0).all()

    # Save and load
    save_path = tmp_path / "test_wind.joblib"
    model.save(save_path)
    assert save_path.exists()

    loaded = WindForecaster.load(save_path)
    loaded_preds = loaded.predict(X[:5])
    assert np.allclose(preds, loaded_preds)


def test_train_wind_pipeline(shared_data, tmp_path):
    result = train_wind_model(df=shared_data, model_dir=str(tmp_path), force=True)

    assert result["status"] == "success"
    assert result["mae"] is not None and result["mae"] >= 0
    assert result["rmse"] is not None and result["rmse"] >= 0
    assert result["train_samples"] > 0
    assert result["val_samples"] > 0
    assert result["test_samples"] > 0
    assert result["residuals"] is not None

    assert (tmp_path / "wind_xgboost.joblib").exists()
    assert (tmp_path / "wind_residuals.npy").exists()
