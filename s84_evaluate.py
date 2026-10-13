"""Section 8.4 - Judge forecast usefulness.

Compares the previous-day baseline (8.2) with the frozen model (8.3) on the
same 1,680 test observations (24 hourly predictions per region per test day).

Outputs
    * MAE and RMSE over all test observations, and separately per region
    * a plot of actual, baseline and model consumption for one region over
      the seven test days
    * for each region, its highest actual test-hour consumption (ties broken
      by the earliest time) with each method's prediction and absolute error

error = predicted - actual (kWh).  MAE = mean |error|.  RMSE = sqrt(mean error^2).

Run:  python s84_evaluate.py     (after s82_baseline.py and s83_train_model.py)
      python s84_evaluate.py --region "Region 8"     (plot a different region)
"""

from __future__ import annotations

import argparse

import pandas as pd

import charts
import forecast_common as fc
from common import RESULTS_DIR, finish_log, format_table, start_log

STEP = "8_4_evaluate"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare baseline and model forecasts.")
    parser.add_argument("--region", default="Region 1", help="region shown in the forecast plot")
    args = parser.parse_args()
    start_log(STEP)

    baseline = pd.read_csv(fc.BASELINE_FILE, parse_dates=["target_hour"])
    model = pd.read_csv(fc.MODEL_PREDICTIONS_FILE, parse_dates=["target_hour"])
    # Join on region + hour so both methods are compared on exactly the same rows.
    both = baseline.merge(model[["region", "target_hour", "model_kwh"]], on=["region", "target_hour"], how="inner")
    actual = both[fc.TARGET]
    print(f"Test observations compared: {len(both):,} "
          f"({both['region'].nunique()} regions, {both['target_hour'].min()} to {both['target_hour'].max()})")

    # ---- Overall and per-region metrics -------------------------------------------------
    rows = []
    regions = sorted(both["region"].unique(), key=lambda name: (len(name), name))
    for label, part in [("ALL REGIONS", both)] + [(region, both[both["region"] == region]) for region in regions]:
        b_mae, b_rmse = fc.metrics(part["baseline_kwh"], part[fc.TARGET])
        m_mae, m_rmse = fc.metrics(part["model_kwh"], part[fc.TARGET])
        rows.append((label, len(part), f"{b_mae:.3f}", f"{m_mae:.3f}", f"{100 * (b_mae - m_mae) / b_mae:+.1f} %",
                     f"{b_rmse:.3f}", f"{m_rmse:.3f}", f"{100 * (b_rmse - m_rmse) / b_rmse:+.1f} %"))
    headers = ["scope", "observations", "baseline MAE", "model MAE", "MAE improvement",
               "baseline RMSE", "model RMSE", "RMSE improvement"]
    print("\n--- MAE and RMSE in kWh (improvement = reduction relative to the baseline) ---")
    print(format_table(headers, rows))
    mean_actual = actual.mean()
    overall_b = fc.metrics(both["baseline_kwh"], actual)
    overall_m = fc.metrics(both["model_kwh"], actual)
    print(f"Mean actual hourly regional consumption: {mean_actual:.3f} kWh "
          f"-> baseline MAE is {100 * overall_b[0] / mean_actual:.2f} %, model MAE is {100 * overall_m[0] / mean_actual:.2f} % of it.")

    # ---- Peak hour of each region ---------------------------------------------------------
    peak_rows = []
    for region in regions:
        part = both[both["region"] == region].sort_values("target_hour")
        # idxmax returns the FIRST maximum, and the rows are sorted by time,
        # so a tie is broken by the earliest hour as required.
        peak = part.loc[part[fc.TARGET].idxmax()]
        peak_rows.append((region, f"{peak['target_hour']:%Y-%m-%d %H:%M}", f"{peak[fc.TARGET]:.3f}",
                          f"{peak['baseline_kwh']:.3f}", f"{abs(peak['baseline_kwh'] - peak[fc.TARGET]):.3f}",
                          f"{peak['model_kwh']:.3f}", f"{abs(peak['model_kwh'] - peak[fc.TARGET]):.3f}",
                          f"{peak['model_kwh'] - peak[fc.TARGET]:+.3f}"))
    peak_headers = ["region", "peak hour (CAT)", "actual kWh", "baseline kWh", "baseline abs error",
                    "model kWh", "model abs error", "model error (pred - actual)"]
    print("\n--- Highest actual test-hour consumption per region ---")
    print(format_table(peak_headers, peak_rows))
    model_peak_errors = [float(row[7]) for row in peak_rows]
    print(f"Model error at the peak hours: mean {sum(model_peak_errors) / len(model_peak_errors):+.3f} kWh "
          f"({sum(1 for e in model_peak_errors if e < 0)} of {len(model_peak_errors)} peaks under-predicted).")

    # ---- Error by test day (shows where the baseline fails) ----------------------------------
    both["day"] = both["target_hour"].dt.normalize()
    by_day = both.assign(b=(both["baseline_kwh"] - actual).abs(), m=(both["model_kwh"] - actual).abs()) \
                 .groupby("day")[["b", "m"]].mean().reset_index()
    print("\n--- MAE by test day (kWh) ---")
    print(format_table(["test day", "weekday", "baseline MAE", "model MAE"],
                       [(f"{r.day:%Y-%m-%d}", r.day.day_name(), f"{r.b:.3f}", f"{r.m:.3f}") for r in by_day.itertuples()]))

    # ---- Plot: one region, seven test days -----------------------------------------------------
    part = both[both["region"] == args.region].sort_values("target_hour")
    fig, ax = charts.new_figure(12, 4.8)
    ax.plot(part["target_hour"], part[fc.TARGET], color=charts.TEXT, linewidth=2.2, label="Actual")
    ax.plot(part["target_hour"], part["baseline_kwh"], color=charts.SERIES[1], linewidth=1.6,
            linestyle="--", label="Baseline (previous day)")
    ax.plot(part["target_hour"], part["model_kwh"], color=charts.SERIES[0], linewidth=1.6, label="Model (Ridge)")
    ax.set_title(f"{args.region}: hourly consumption, 22-28 September 2026 (test week)")
    ax.set_ylabel("Energy per hour (kWh)")
    ax.set_xlabel("Target hour (CAT)")
    ax.set_ylim(0, None)
    import matplotlib.dates as mdates
    ax.xaxis.set_major_locator(mdates.DayLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%a %d %b"))
    ax.legend(loc="lower left", ncols=3)
    charts.save(fig, "8_4_forecast_plot")

    (RESULTS_DIR / f"{STEP}.md").write_text(
        "# 8.4 Forecast evaluation\n\n" + format_table(headers, rows, markdown=True) + "\n\n"
        + format_table(peak_headers, peak_rows, markdown=True) + "\n", encoding="utf-8")
    finish_log(STEP)


if __name__ == "__main__":
    main()
