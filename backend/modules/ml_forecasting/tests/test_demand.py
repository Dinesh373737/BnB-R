"""
Tests for ML Forecasting — Demand Forecaster & Trainer
"""

import numpy as np
import pytest
from pathlib import Path

from backend.modules.ml_forecasting.data_generator import generate_historical_data
from backend.modules.ml_forecasting.demand.model import DemandForecaster
from backend.modules.ml_forecasting.demand.trainer import train_demand_model


@pytest.fixture(scope="module")
def shared_data(tmp_path_factory):
    tmp_dir = tmp_path_factory.mktemp("data")
    return generate_historical_data(days=14, seed=42, output_dir=tmp_dir)


def test_demand_model_fit_predict(tmp_path):
    X = np.random.randn(100, 10)
    y = 2000.0 + 100.0 * np.random.randn(100)

    model = DemandForecaster(params={"n_estimators": 10, "max_depth": 3})
    model.fit(X, y)

    preds = model.predict(X[:5])
    assert len(preds) == 5
    assert (preds >= 0).all()

    # Test save and load
    save_path = tmp_path / "test_demand.joblib"
    model.save(save_path)
    assert save_path.exists()

    loaded = DemandForecaster.load(save_path)
    loaded_preds = loaded.predict(X[:5])
    assert np.allclose(preds, loaded_preds)


def test_train_demand_pipeline(shared_data, tmp_path):
    result = train_demand_model(df=shared_data, model_dir=str(tmp_path), force=True)

    assert result["status"] == "success"
    assert result["mae"] is not None and result["mae"] > 0
    assert result["rmse"] is not None and result["rmse"] > 0
    assert result["mape"] is not None and 0 <= result["mape"] <= 100
    assert result["train_samples"] > 0
    assert result["val_samples"] > 0
    assert result["test_samples"] > 0
    assert result["residuals"] is not None

    # Model and residuals files exist
    assert (tmp_path / "demand_xgboost.joblib").exists()
    assert (tmp_path / "demand_residuals.npy").exists()
