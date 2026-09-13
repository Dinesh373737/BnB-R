"""
ML Forecasting — Feature Engineering
========================================
Pure functions for creating time-series features from historical data.

All functions accept and return ``pd.DataFrame``; none have database or API
dependencies.  Features are designed to **prevent future-data leakage**:
lag and rolling features only look backwards.

Feature categories
------------------
1. **Time** — hour, day_of_week, month, is_weekend, hour_sin, hour_cos
2. **Lag** — target value at t-1, t-2, t-3, t-6, t-12, t-24
3. **Rolling** — 3 h / 6 h / 12 h / 24 h backward mean; 24 h std
4. **Weather** — temperature_c, cloud_cover_pct, wind_speed_ms, solar_radiation_wm2
"""

import math
from typing import List, Optional

import numpy as np
import pandas as pd


# ═══════════════════════════════════════════════════════════════════════════
#  TIME FEATURES
# ═══════════════════════════════════════════════════════════════════════════


def add_time_features(df: pd.DataFrame, timestamp_col: str = "timestamp") -> pd.DataFrame:
    """
    Add cyclical and categorical time features from the timestamp column.

    New columns: hour, day_of_week, month, is_weekend, hour_sin, hour_cos
    """
    out = df.copy()
    ts = pd.to_datetime(out[timestamp_col])

    out["hour"] = ts.dt.hour
    out["day_of_week"] = ts.dt.dayofweek          # 0 = Monday
    out["month"] = ts.dt.month
    out["is_weekend"] = (ts.dt.dayofweek >= 5).astype(int)

    # Cyclical encoding — avoids the 23→0 discontinuity
    out["hour_sin"] = np.sin(2 * math.pi * out["hour"] / 24)
    out["hour_cos"] = np.cos(2 * math.pi * out["hour"] / 24)

    return out


# ═══════════════════════════════════════════════════════════════════════════
#  LAG FEATURES
# ═══════════════════════════════════════════════════════════════════════════


DEFAULT_LAGS = [1, 2, 3, 6, 12, 24]


def add_lag_features(
    df: pd.DataFrame,
    target_col: str,
    lags: Optional[List[int]] = None,
) -> pd.DataFrame:
    """
    Add lagged values of ``target_col``.

    Parameters
    ----------
    df : DataFrame
        Must be sorted by time.
    target_col : str
        Column to create lags for (e.g. ``"demand_kw"``).
    lags : list[int]
        Lag offsets in timesteps. Default: [1, 2, 3, 6, 12, 24].

    Returns
    -------
    DataFrame with new columns ``{target_col}_lag_{k}`` for each k in *lags*.
    """
    lags = lags or DEFAULT_LAGS
    out = df.copy()
    for k in lags:
        out[f"{target_col}_lag_{k}"] = out[target_col].shift(k)
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  ROLLING FEATURES
# ═══════════════════════════════════════════════════════════════════════════


DEFAULT_WINDOWS = [3, 6, 12, 24]


def add_rolling_features(
    df: pd.DataFrame,
    target_col: str,
    windows: Optional[List[int]] = None,
) -> pd.DataFrame:
    """
    Add backward-looking rolling mean (and 24 h std) of ``target_col``.

    The rolling window is **closed on the left** (``shift(1)``) so it never
    includes the current row → no future leakage.
    """
    windows = windows or DEFAULT_WINDOWS
    out = df.copy()
    shifted = out[target_col].shift(1)  # exclude current row

    for w in windows:
        out[f"{target_col}_rolling_{w}h"] = shifted.rolling(window=w, min_periods=1).mean()

    # 24-hour rolling standard deviation
    out[f"{target_col}_rolling_24h_std"] = shifted.rolling(window=24, min_periods=1).std()

    return out


# ═══════════════════════════════════════════════════════════════════════════
#  FULL FEATURE PIPELINE
# ═══════════════════════════════════════════════════════════════════════════

# Weather columns available in the historical dataset
WEATHER_FEATURES = [
    "temperature_c",
    "cloud_cover_pct",
    "wind_speed_ms",
    "solar_radiation_wm2",
]

# Feature sets tailored per forecast type
FEATURE_SETS = {
    "demand": {
        "weather": ["temperature_c"],
        "target_col": "demand_kw",
    },
    "solar": {
        "weather": ["temperature_c", "cloud_cover_pct", "solar_radiation_wm2"],
        "target_col": "solar_kw",
    },
    "wind": {
        "weather": ["temperature_c", "wind_speed_ms"],
        "target_col": "wind_kw",
    },
}


def prepare_features(
    df: pd.DataFrame,
    forecast_type: str,
    drop_na: bool = True,
) -> pd.DataFrame:
    """
    Full feature-engineering pipeline for a given forecast type.

    Steps:
        1. Add time features
        2. Add lag features for the target column
        3. Add rolling features for the target column
        4. Keep relevant weather columns
        5. Optionally drop rows with NaN (from lag/rolling)

    Parameters
    ----------
    df : DataFrame
        Raw historical data with timestamp and value columns.
    forecast_type : str
        One of ``"demand"``, ``"solar"``, ``"wind"``.
    drop_na : bool
        Drop rows containing NaN values (from lag creation). Default True.

    Returns
    -------
    DataFrame with all features and the target column.
    """
    if forecast_type not in FEATURE_SETS:
        raise ValueError(f"Unknown forecast_type '{forecast_type}'. Use: {list(FEATURE_SETS)}")

    config = FEATURE_SETS[forecast_type]
    target_col = config["target_col"]
    weather_cols = config["weather"]

    # Ensure sorted by time
    out = df.sort_values("timestamp").reset_index(drop=True)

    # 1. Time features
    out = add_time_features(out)

    # 2. Lag features
    out = add_lag_features(out, target_col)

    # 3. Rolling features
    out = add_rolling_features(out, target_col)

    # 4. Drop rows with NaN from lags/rolling (first ~24 rows)
    if drop_na:
        out = out.dropna().reset_index(drop=True)

    return out


def get_feature_columns(forecast_type: str) -> List[str]:
    """
    Return the list of feature column names used for a given forecast type.

    This is the definitive list of columns passed to the model at both
    training and inference time.
    """
    if forecast_type not in FEATURE_SETS:
        raise ValueError(f"Unknown forecast_type '{forecast_type}'. Use: {list(FEATURE_SETS)}")

    config = FEATURE_SETS[forecast_type]
    target_col = config["target_col"]
    weather_cols = config["weather"]

    cols = []

    # Time features
    cols += ["hour", "day_of_week", "month", "is_weekend", "hour_sin", "hour_cos"]

    # Lag features
    for k in DEFAULT_LAGS:
        cols.append(f"{target_col}_lag_{k}")

    # Rolling features
    for w in DEFAULT_WINDOWS:
        cols.append(f"{target_col}_rolling_{w}h")
    cols.append(f"{target_col}_rolling_24h_std")

    # Weather features
    cols += weather_cols

    return cols


def get_target_column(forecast_type: str) -> str:
    """Return the target column name for a given forecast type."""
    if forecast_type not in FEATURE_SETS:
        raise ValueError(f"Unknown forecast_type '{forecast_type}'. Use: {list(FEATURE_SETS)}")
    return FEATURE_SETS[forecast_type]["target_col"]
