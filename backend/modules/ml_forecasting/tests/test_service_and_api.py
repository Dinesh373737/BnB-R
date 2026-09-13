"""
Tests for ML Forecasting — Service & API Endpoints
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.common.database import get_db_session
from backend.modules.ml_forecasting.service import ForecastingService
from backend.modules.ml_forecasting.router import router, get_service
from backend.modules.ml_forecasting.schemas import ForecastRequest


@pytest.fixture(scope="module")
def test_app():
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture(scope="module")
def client(test_app):
    return TestClient(test_app)


@pytest.fixture(scope="module")
def service():
    srv = ForecastingService.get_instance()
    srv.ensure_models_trained()
    return srv


def test_service_predictions(service):
    demand = service.predict_demand()
    assert demand.forecast_type == "demand"
    assert demand.prediction > 0
    assert demand.lower <= demand.prediction <= demand.upper
    assert demand.confidence in {"high", "medium", "low"}

    solar = service.predict_solar()
    assert solar.forecast_type == "solar"
    assert solar.prediction >= 0
    assert solar.lower <= solar.upper

    wind = service.predict_wind()
    assert wind.forecast_type == "wind"
    assert wind.prediction >= 0
    assert wind.lower <= wind.upper

    summary = service.predict_all()
    assert summary.demand is not None
    assert summary.solar is not None
    assert summary.wind is not None
    assert summary.total_generation_forecast == round(solar.prediction + wind.prediction, 2)
    assert summary.net_position == round(summary.total_generation_forecast - demand.prediction, 2)

    state = service.get_forecast_state()
    assert state.demand_forecast_kw == demand.prediction
    assert state.solar_forecast_kw == solar.prediction
    assert state.wind_forecast_kw == wind.prediction
    assert state.uncertainty_level in {"low", "medium", "high"}


def test_api_demand_endpoint(client):
    response = client.get("/api/forecast/demand?horizon_minutes=60&current_value=2100.0&temperature_c=28.5")
    assert response.status_code == 200
    data = response.json()
    assert data["forecast_type"] == "demand"
    assert "prediction" in data
    assert "lower" in data
    assert "upper" in data
    assert "confidence" in data
    assert data["lower"] <= data["prediction"] <= data["upper"]

    # Also test without prefix
    resp2 = client.get("/forecast/demand")
    assert resp2.status_code == 200


def test_api_solar_endpoint(client):
    response = client.get("/api/forecast/solar?horizon_minutes=60&cloud_cover_pct=15.0&solar_radiation_wm2=750.0")
    assert response.status_code == 200
    data = response.json()
    assert data["forecast_type"] == "solar"
    assert data["prediction"] >= 0
    assert data["lower"] >= 0
    assert data["lower"] <= data["upper"]


def test_api_wind_endpoint(client):
    response = client.get("/api/forecast/wind?horizon_minutes=60&wind_speed_ms=8.5")
    assert response.status_code == 200
    data = response.json()
    assert data["forecast_type"] == "wind"
    assert data["prediction"] >= 0
    assert data["lower"] >= 0
    assert data["lower"] <= data["upper"]


def test_api_predictions_summary(client):
    response = client.get("/api/predictions")
    assert response.status_code == 200
    data = response.json()
    assert "demand" in data and data["demand"] is not None
    assert "solar" in data and data["solar"] is not None
    assert "wind" in data and data["wind"] is not None
    assert "total_generation_forecast" in data
    assert "net_position" in data


def test_api_training_invalid_type(client):
    response = client.post("/api/forecast/train", json={"forecast_types": ["nuclear"]})
    assert response.status_code == 400
    assert "Invalid forecast types" in response.json()["detail"]


def test_api_training_valid(client):
    # Train only demand to keep test fast
    response = client.post("/api/forecast/train", json={"forecast_types": ["demand"], "force_retrain": True})
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) == 1
    res = data["results"][0]
    assert res["forecast_type"] == "demand"
    assert res["status"] == "success"
    assert res["mae"] is not None
