"""
Tests for ML Forecasting — Uncertainty Estimation
"""

import numpy as np
import pytest

from backend.modules.ml_forecasting.uncertainty.estimator import UncertaintyEstimator


def test_uncertainty_estimator_with_residuals():
    # Synthetic residuals with known distribution
    residuals = np.random.normal(loc=0.0, scale=10.0, size=200)
    estimator = UncertaintyEstimator(residuals=residuals)

    pred = 500.0
    lower, upper, confidence = estimator.estimate(pred, coverage=0.90)

    # Sanity checks
    assert lower >= 0.0
    assert lower <= pred <= upper
    assert confidence in {"high", "medium", "low"}

    # Relative uncertainty is low (margin ~ 16, pred = 500 => margin/pred ~ 3% => high confidence)
    assert confidence == "high"


def test_uncertainty_estimator_coverage_scaling():
    residuals = np.random.normal(loc=0.0, scale=15.0, size=500)
    estimator = UncertaintyEstimator(residuals=residuals)

    pred = 200.0
    low_50, up_50, _ = estimator.estimate(pred, coverage=0.50)
    low_95, up_95, _ = estimator.estimate(pred, coverage=0.95)

    # 95% interval must be strictly wider than 50% interval
    width_50 = up_50 - low_50
    width_95 = up_95 - low_95
    assert width_95 > width_50


def test_uncertainty_zero_prediction():
    residuals = np.random.normal(loc=0.0, scale=2.0, size=100)
    estimator = UncertaintyEstimator(residuals=residuals)

    # E.g., solar at night
    lower, upper, confidence = estimator.estimate(0.0)
    assert lower == 0.0
    assert upper >= 0.0
    assert confidence in {"high", "medium"}


def test_uncertainty_fallback_without_residuals():
    estimator = UncertaintyEstimator(residuals=None)
    pred = 100.0
    lower, upper, confidence = estimator.estimate(pred)

    assert lower >= 0.0
    assert lower <= pred <= upper
    assert confidence in {"high", "medium", "low"}
