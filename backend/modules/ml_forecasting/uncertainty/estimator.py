"""
ML Forecasting — Uncertainty Estimation
=========================================
Uses validation residuals to produce calibrated prediction intervals
and confidence levels (high / medium / low) for demand, solar, and wind.

Approach:
  - Validation residuals e = y_val - y_hat_val are computed and stored during model training.
  - Non-parametric empirical quantile of |e| provides the margin for a given coverage level.
  - Lower bound is clipped to >= 0 (power in kW cannot be negative).
  - Confidence rating is derived from relative uncertainty and residual dispersion.
"""

from pathlib import Path
from typing import Optional, Tuple
import numpy as np

from backend.common.config import settings
from backend.common.logger import get_module_logger

log = get_module_logger("ml_forecasting.uncertainty.estimator")


class UncertaintyEstimator:
    """Estimates prediction intervals and confidence using empirical validation residuals."""

    def __init__(
        self,
        residuals: Optional[np.ndarray] = None,
        forecast_type: Optional[str] = None,
        model_dir: Optional[str] = None,
    ):
        self.forecast_type = forecast_type
        self.model_dir = Path(model_dir or settings.ML_MODEL_DIR)
        self.residuals = residuals
        if self.residuals is None and forecast_type is not None:
            self.residuals = self._load_residuals(forecast_type)

    def _load_residuals(self, forecast_type: str) -> Optional[np.ndarray]:
        res_file = self.model_dir / f"{forecast_type}_residuals.npy"
        if res_file.exists():
            try:
                res = np.load(res_file)
                log.debug(f"Loaded {len(res)} validation residuals for {forecast_type} from {res_file}")
                return res
            except Exception as e:
                log.warning(f"Failed to load residuals from {res_file}: {e}")
        return None

    def estimate(
        self,
        prediction: float,
        coverage: float = 0.85,
    ) -> Tuple[float, float, str]:
        """
        Compute lower bound, upper bound, and confidence level for a given prediction.

        Parameters
        ----------
        prediction : float
            Point forecast value (kW).
        coverage : float
            Desired coverage probability between 0 and 1 (default 0.85 = 85%).

        Returns
        -------
        tuple of (lower, upper, confidence)
            lower : float (>= 0)
            upper : float
            confidence : str ("high", "medium", or "low")
        """
        if self.residuals is not None and len(self.residuals) > 0:
            abs_res = np.abs(self.residuals)
            # Clip coverage between 0.5 and 0.99
            pct = np.clip(coverage * 100, 50.0, 99.0)
            margin = float(np.percentile(abs_res, pct))
            std_res = float(np.std(self.residuals))
        else:
            # Fallback heuristic if no validation residuals available yet
            margin = max(prediction * 0.15, 5.0)
            std_res = margin / 1.5

        lower = max(0.0, round(prediction - margin, 2))
        upper = round(prediction + margin, 2)

        # Determine confidence level
        # If prediction is virtually 0 (e.g. solar at night), confidence is high if margin is small
        if prediction < 1.0:
            confidence = "high" if margin < 10.0 else "medium"
        else:
            relative_margin = margin / max(prediction, 1.0)
            if relative_margin <= 0.15:
                confidence = "high"
            elif relative_margin <= 0.35:
                confidence = "medium"
            else:
                confidence = "low"

        return lower, upper, confidence
