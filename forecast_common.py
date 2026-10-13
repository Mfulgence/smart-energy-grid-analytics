"""Shared definitions for the next-day forecast (Section 8).

Everything that must be IDENTICAL in 8.1, 8.2, 8.3 and 8.4 lives here: the
split dates, the feature list and the way features are built. That is what
guarantees the baseline and the model are compared on the same 1,680 rows.

The forecasting situation
    At 00:00 CAT on day D (the "forecast origin") we predict the 24 hourly
    consumption values of day D for every region. Only information that
    exists BEFORE that origin may be used. So:
        allowed      the same hour one day earlier (D-1), two days earlier,
                     one week earlier, the average of day D-1
        not allowed  any hour of day D itself (for example the previous hour)
"""

from __future__ import annotations

import pandas as pd

from common import RESULTS_DIR

DATASET_FILE = RESULTS_DIR / "8_1_hourly_dataset.csv"
MODEL_FILE = RESULTS_DIR / "8_3_frozen_model.joblib"
BASELINE_FILE = RESULTS_DIR / "8_2_baseline_predictions.csv"
MODEL_PREDICTIONS_FILE = RESULTS_DIR / "8_3_model_predictions.csv"

# Split by TARGET timestamp (CAT days, both days included).
SPLITS = {
    "train": ("2026-09-01", "2026-09-14"),
    "validation": ("2026-09-15", "2026-09-21"),
    "test": ("2026-09-22", "2026-09-28"),
}

# Lag features: column name -> how many hours before the target hour.
LAGS = {"lag_24h": 24, "lag_48h": 48, "lag_168h": 168}
WINDOW_FEATURE = "prev_day_mean"          # mean of the 24 hours of the day before the target day
NUMERIC_FEATURES = list(LAGS) + [WINDOW_FEATURE]
CATEGORICAL_FEATURES = ["hour_of_day", "day_of_week", "region"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
LOOKBACK_HOURS = max(LAGS.values())       # 168: a row needs one full week of history
TARGET = "energy_kwh"


def add_features(data: pd.DataFrame) -> pd.DataFrame:
    """Add calendar, lag and window features to the hourly table.

    Lags are attached by JOINING on (region, target_hour - lag). A join (and
    not a simple "shift down N rows") stays correct even if an hour were
    absent: the lag would then be empty instead of silently taken from the
    wrong hour.
    """
    data = data.sort_values(["region", "target_hour"]).reset_index(drop=True)

    # Forecast origin = 00:00 at the start of the target hour's own day.
    data["forecast_origin"] = data["target_hour"].dt.normalize()

    # Calendar features: known for any future hour, so always available.
    data["hour_of_day"] = data["target_hour"].dt.hour
    data["day_of_week"] = data["target_hour"].dt.dayofweek          # Monday = 0 ... Sunday = 6

    history = data[["region", "target_hour", TARGET]]
    for name, hours in LAGS.items():
        source = history.rename(columns={"target_hour": f"{name}_source", TARGET: name})
        data[f"{name}_source"] = data["target_hour"] - pd.Timedelta(hours=hours)
        data = data.merge(source, on=["region", f"{name}_source"], how="left")

    # Window feature: average hourly energy of the previous CAT day (24 hours
    # that end exactly at the forecast origin).
    daily = (data.groupby(["region", "forecast_origin"])[TARGET].agg(["mean", "count"]).reset_index()
             .rename(columns={"mean": WINDOW_FEATURE, "count": "prev_day_hours"}))
    daily["forecast_origin"] = daily["forecast_origin"] + pd.Timedelta(days=1)   # day D-1 serves day D
    data = data.merge(daily, on=["region", "forecast_origin"], how="left")
    data.loc[data["prev_day_hours"] != 24, WINDOW_FEATURE] = float("nan")       # need the full day
    return data.sort_values(["region", "target_hour"]).reset_index(drop=True)


def split_mask(data: pd.DataFrame, name: str) -> pd.Series:
    """True for the rows whose TARGET day falls inside the named split."""
    first, last = SPLITS[name]
    day = data["target_hour"].dt.normalize()
    return (day >= pd.Timestamp(first)) & (day <= pd.Timestamp(last))


def load_dataset() -> pd.DataFrame:
    """Read the dataset written by s81_prepare_features.py."""
    time_columns = ["target_hour", "forecast_origin"] + [f"{name}_source" for name in LAGS]
    return pd.read_csv(DATASET_FILE, parse_dates=time_columns)


def usable(data: pd.DataFrame) -> pd.Series:
    """Rows that have every predictor (i.e. a complete initial lookback)."""
    return data[NUMERIC_FEATURES].notna().all(axis=1)


def metrics(predicted: pd.Series, actual: pd.Series) -> tuple[float, float]:
    """MAE and RMSE in kWh. Error is defined as predicted minus actual."""
    error = predicted - actual
    return float(error.abs().mean()), float((error ** 2).mean() ** 0.5)
