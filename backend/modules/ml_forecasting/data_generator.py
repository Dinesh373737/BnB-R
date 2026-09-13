"""
ML Forecasting — Synthetic Historical Data Generator
=======================================================
Generates realistic hourly time-series for demand, solar, wind, and weather
using the same mathematical patterns as Module 1's GridClient and WeatherClient.

Produces data at **microgrid scale** (kW) matching the simulation config defaults:
  - Solar capacity:  500 kW
  - Wind capacity:   200 kW
  - Demand base:    ~2100 kW  (households + industrial + critical)

The generator is deterministic (seeded) so results are reproducible.
"""

import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from backend.common.config import settings
from backend.common.logger import get_module_logger

log = get_module_logger("ml_forecasting.data_generator")

DATASETS_DIR = Path(settings.PROJECT_ROOT) / "data_storage" / "datasets"


def generate_historical_data(
    days: int = 90,
    seed: int = 42,
    output_dir: Optional[Path] = None,
) -> pd.DataFrame:
    """
    Generate synthetic hourly historical data for demand, solar, wind + weather.

    Parameters
    ----------
    days : int
        Number of days of history to generate (default 90 → 2160 rows).
    seed : int
        Random seed for reproducibility.
    output_dir : Path, optional
        Directory to save CSV. Defaults to ``data_storage/datasets/``.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns: timestamp, demand_kw, solar_kw, wind_kw,
        temperature_c, cloud_cover_pct, wind_speed_ms, solar_radiation_wm2
    """
    rng = np.random.default_rng(seed)
    out_dir = output_dir or DATASETS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Configuration (from settings, matching Module 1) ─────────────────
    solar_cap = settings.DEFAULT_SOLAR_CAPACITY_KW       # 500 kW
    wind_cap = settings.DEFAULT_WIND_CAPACITY_KW          # 200 kW
    n_households = settings.DEFAULT_NUM_HOUSEHOLDS         # 50
    industrial = settings.DEFAULT_INDUSTRIAL_LOAD_KW       # 1500 kW
    critical = settings.DEFAULT_CRITICAL_LOAD_KW           # 500 kW
    base_demand = n_households * 2.0 + industrial + critical  # ~2100 kW

    # Start 'days' ago from now
    end_time = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start_time = end_time - timedelta(days=days)

    hours_total = days * 24
    timestamps = [start_time + timedelta(hours=h) for h in range(hours_total)]

    records = []
    for i, ts in enumerate(timestamps):
        hour = ts.hour + ts.minute / 60.0
        day_of_year = ts.timetuple().tm_yday
        month = ts.month
        is_weekend = 1 if ts.weekday() >= 5 else 0

        # ── Weather ──────────────────────────────────────────────────────
        # Temperature: 20–35°C for Bangalore, daily cycle + seasonal
        seasonal_temp = 2.0 * math.sin(2 * math.pi * (day_of_year - 80) / 365)
        daily_temp = 5.0 * math.sin(math.pi * (hour - 6) / 12) if 6 <= hour <= 18 else -2.0
        temperature = 27.0 + seasonal_temp + daily_temp + rng.normal(0, 1.5)

        # Cloud cover: more during monsoon (June–Sep), daily variation
        monsoon_factor = 30.0 if 6 <= month <= 9 else 0.0
        cloud_cover = np.clip(
            20.0 + monsoon_factor + 15.0 * math.sin(math.pi * hour / 12) + rng.normal(0, 15),
            0, 100,
        )

        # Wind speed (m/s): higher at night/evening
        wind_speed = np.clip(
            5.0 + 3.0 * math.sin(math.pi * (hour + 6) / 12) + rng.normal(0, 2.0),
            0.5, 20.0,
        )

        # Solar radiation (W/m²): only during daylight, affected by clouds
        if 6 <= hour <= 18:
            clear_sky = 900.0 * math.sin(math.pi * (hour - 6) / 12)
            solar_rad = np.clip(
                clear_sky * (1.0 - cloud_cover / 150.0) + rng.normal(0, 30),
                0, 1200,
            )
        else:
            solar_rad = 0.0

        # ── Demand (kW) ─────────────────────────────────────────────────
        # Daily cycle: peak ~19:00, trough ~03:00  (matches GridClient)
        demand_cycle = math.sin(math.pi * (hour - 7) / 12) * 800.0
        weekend_factor = 0.85 if is_weekend else 1.0
        # Temperature effect: higher demand when hot (AC) or cold
        temp_effect = max(0, (temperature - 30)) * 15.0 + max(0, (20 - temperature)) * 10.0
        demand = max(
            100.0,
            (base_demand + demand_cycle) * weekend_factor + temp_effect + rng.normal(0, 80),
        )

        # ── Solar Generation (kW) ───────────────────────────────────────
        # Matches GridClient: generation only 6–18, peak ~12–13
        if 6 <= hour <= 18:
            solar_factor = math.sin(math.pi * (hour - 6) / 12)
            cloud_penalty = 1.0 - (cloud_cover / 120.0)  # heavy cloud → ~17% capacity
            solar_gen = max(
                0.0,
                solar_cap * solar_factor * cloud_penalty + rng.normal(0, 15),
            )
        else:
            solar_gen = 0.0

        # ── Wind Generation (kW) ────────────────────────────────────────
        # Matches GridClient: slightly higher at night
        wind_factor = np.clip(wind_speed / 12.0, 0, 1.0)  # cut-in ~1 m/s, rated ~12 m/s
        wind_gen = max(
            0.0,
            wind_cap * wind_factor * (0.7 + 0.3 * math.sin(math.pi * hour / 12))
            + rng.normal(0, 10),
        )

        records.append(
            {
                "timestamp": ts.isoformat(),
                "demand_kw": round(demand, 2),
                "solar_kw": round(solar_gen, 2),
                "wind_kw": round(wind_gen, 2),
                "temperature_c": round(temperature, 2),
                "cloud_cover_pct": round(cloud_cover, 2),
                "wind_speed_ms": round(wind_speed, 2),
                "solar_radiation_wm2": round(solar_rad, 2),
            }
        )

    df = pd.DataFrame(records)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Save to CSV
    csv_path = out_dir / "historical_microgrid_data.csv"
    df.to_csv(csv_path, index=False)
    log.info(f"Generated {len(df)} rows of synthetic data -> {csv_path}")

    return df


def load_historical_data(csv_path: Optional[Path] = None) -> pd.DataFrame:
    """
    Load historical data from CSV, or generate it if it doesn't exist.

    Parameters
    ----------
    csv_path : Path, optional
        Path to CSV file. Defaults to ``data_storage/datasets/historical_microgrid_data.csv``.

    Returns
    -------
    pd.DataFrame
    """
    path = csv_path or (DATASETS_DIR / "historical_microgrid_data.csv")
    if path.exists():
        log.info(f"Loading historical data from {path}")
        df = pd.read_csv(path, parse_dates=["timestamp"])
        return df

    log.info("No historical data found - generating synthetic data...")
    return generate_historical_data()
