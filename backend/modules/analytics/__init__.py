"""GridMind — Module 8: Analytics & Baseline Comparison.

Deterministic analytics module that calculates metrics from simulation results
and compares GridMind's multi-agent performance against a simple rule-based
baseline controller under the same scenario.
"""

from backend.modules.analytics.service import AnalyticsService
from backend.modules.analytics.metrics import calculate_all_metrics
from backend.modules.analytics.baseline import BaselineController

__all__ = [
    "AnalyticsService",
    "BaselineController",
    "calculate_all_metrics",
]
