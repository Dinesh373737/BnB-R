"""
Tests for ML Forecasting — Feature Engineering
"""

import math
import numpy as np
import pandas as pd
import pytest

from backend.modules.ml_forecasting.feature_engineering import (
    add_time_features,
    add_lag_features,
    add_rolling_features,
    prepare_features,
    get_feature_columns,
    get_target_column,
)


@pytest.fixture
def sample_data():
    """Create a minimal time-series dataframe for testing."""
    dates = pd.date_range("2026-01-01 00:00:00", periods=72, freq="h")
    df = pd.DataFrame({
        "timestamp": dates,
        "demand_kw": [2000.0 + 300.0 * math.sin(i * math.pi / 12) for i in range(72)],
        "solar_kw": [max(0.0, 400.0 * math.sin((i % 24 - 6) * math.pi / 12)) if 6 <= (i % 24) <= 18 else 0.0 for i in range(72)],
        "wind_kw": [100.0 + 30.0 * math.cos(i * math.pi / 12) for i in range(72)],
        "temperature_c": [25.0 + 5.0 * math.sin(i * math.pi / 12) for i in range(72)],
        "cloud_cover_pct": [20.0 for _ in range(72)],
        "wind_speed_ms": [5.0 for _ in range(72)],
        "solar_radiation_wm2": [500.0 if 6 <= (i % 24) <= 18 else 0.0 for i in range(72)],
    })
    return df


def test_add_time_features(sample_data):
    out = add_time_features(sample_data)
    assert "hour" in out.columns
    assert "day_of_week" in out.columns
    assert "month" in out.columns
    assert "is_weekend" in out.columns
    assert "hour_sin" in out.columns
    assert "hour_cos" in out.columns

    # Check cyclical boundary
    assert np.isclose(out.loc[0, "hour_sin"], 0.0, atol=1e-5)
    assert np.isclose(out.loc[0, "hour_cos"], 1.0, atol=1e-5)
    # Hour 6
    assert np.isclose(out.loc[6, "hour_sin"], 1.0, atol=1e-5)
    assert np.isclose(out.loc[6, "hour_cos"], 0.0, atol=1e-5)


def test_add_lag_features(sample_data):
    lags = [1, 2, 3]
    out = add_lag_features(sample_data, "demand_kw", lags=lags)
    for k in lags:
        col = f"demand_kw_lag_{k}"
        assert col in out.columns
        # Value at row k should equal sample_data row 0
        assert out.loc[k, col] == sample_data.loc[0, "demand_kw"]
        # Row 0 should be NaN
        assert pd.isna(out.loc[0, col])


def test_add_rolling_features_no_future_leakage(sample_data):
    windows = [3, 6]
    out = add_rolling_features(sample_data, "demand_kw", windows=windows)

    # First row must be NaN because rolling is shifted by 1
    assert pd.isna(out.loc[0, "demand_kw_rolling_3h"])

    # Row 1 rolling 3h should be mean of [row 0]
    assert np.isclose(out.loc[1, "demand_kw_rolling_3h"], sample_data.loc[0, "demand_kw"])

    # Row 3 rolling 3h should be mean of rows 0, 1, 2 (strictly past data)
    expected = sample_data.loc[0:2, "demand_kw"].mean()
    assert np.isclose(out.loc[3, "demand_kw_rolling_3h"], expected)


def test_prepare_features_for_all_types(sample_data):
    for ftype in ["demand", "solar", "wind"]:
        df_feat = prepare_features(sample_data, ftype, drop_na=True)
        assert len(df_feat) < len(sample_data)  # Dropped initial NaN rows
        assert len(df_feat) > 0

        target = get_target_column(ftype)
        assert target in df_feat.columns

        cols = get_feature_columns(ftype)
        for col in cols:
            assert col in df_feat.columns, f"Missing {col} for {ftype}"


def test_invalid_forecast_type(sample_data):
    with pytest.raises(ValueError):
        prepare_features(sample_data, "invalid_type")
