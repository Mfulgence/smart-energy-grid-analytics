"""Section 8.2 - Evaluate the previous-day baseline.

The baseline is the simplest sensible forecast:
    at 00:00 CAT on each test day, predict each of its 24 hours with the
    consumption of the SAME hour on the previous day, for every region.

In the dataset that value is the feature lag_24h, so the baseline needs no
training at all. 7 test days x 24 hours x 10 regions = 1,680 predictions.

Error definition (used everywhere in Section 8)
    error = predicted - actual   (kWh)
    MAE   = mean of |error|
    RMSE  = square root of the mean of error squared

Run:  python s82_baseline.py     (after s81_prepare_features.py)
"""

from __future__ import annotations

import forecast_common as fc
from common import RESULTS_DIR, cat_text, finish_log, format_table, start_log

STEP = "8_2_baseline"


def main() -> None:
    start_log(STEP)
    data = fc.load_dataset()
    test = data[fc.split_mask(data, "test")].copy()

    # The forecast: previous day's value of the same hour and region.
    test["baseline_kwh"] = test["lag_24h"]
    test["baseline_error"] = test["baseline_kwh"] - test[fc.TARGET]

    mae, rmse = fc.metrics(test["baseline_kwh"], test[fc.TARGET])
    summary = [
        ("Forecast rule", "value of the same hour on the previous day (lag 24 hours)"),
        ("Test days", f"{test['target_hour'].min():%Y-%m-%d} to {test['target_hour'].max():%Y-%m-%d}"),
        ("Regions", test["region"].nunique()),
        ("Predictions produced", f"{len(test):,}"),
        ("Predictions missing a value", int(test["baseline_kwh"].isna().sum())),
        ("MAE (kWh)", f"{mae:.3f}"),
        ("RMSE (kWh)", f"{rmse:.3f}"),
        ("Mean actual hourly consumption (kWh)", f"{test[fc.TARGET].mean():.3f}"),
        ("MAE as % of mean actual", f"{100 * mae / test[fc.TARGET].mean():.2f} %"),
        ("Completed", cat_text()),
    ]
    print(format_table(["Baseline run", "Value"], summary))

    columns = ["region", "target_hour", "forecast_origin", "lag_24h_source", fc.TARGET, "baseline_kwh", "baseline_error"]
    sample = test[test["region"] == "Region 1"].head(8)[columns].copy()
    for column in (fc.TARGET, "baseline_kwh", "baseline_error"):
        sample[column] = sample[column].round(3)
    print("\n--- Sample predictions (actual vs previous-day value) ---")
    print(format_table(columns, sample.astype(str).values.tolist()))

    # Where is the baseline weakest? Error by day of week of the TARGET day.
    by_day = (test.assign(abs_error=test["baseline_error"].abs(), weekday=test["target_hour"].dt.day_name())
              .groupby(["forecast_origin", "weekday"])["abs_error"].mean().reset_index())
    print("\n--- Baseline MAE by test day ---")
    print(format_table(["test day", "weekday", "MAE (kWh)"],
                       [(f"{row.forecast_origin:%Y-%m-%d}", row.weekday, f"{row.abs_error:.3f}") for row in by_day.itertuples()]))
    print("The largest errors fall on the days whose previous day is a different day type")
    print("(Saturday is predicted from Friday, Monday from Sunday).")

    test[["region", "target_hour", fc.TARGET, "baseline_kwh"]].to_csv(fc.BASELINE_FILE, index=False)
    (RESULTS_DIR / f"{STEP}.md").write_text(
        "# 8.2 Previous-day baseline\n\n" + format_table(["Baseline run", "Value"], summary, markdown=True) + "\n",
        encoding="utf-8")
    print(f"\nPredictions saved: results/{fc.BASELINE_FILE.name}")
    finish_log(STEP)


if __name__ == "__main__":
    main()
