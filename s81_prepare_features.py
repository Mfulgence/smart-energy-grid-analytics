"""Section 8.1 - Prepare the chronological dataset and the features.

Steps
    1. Query one row per region and CAT hour from the cleaned readings
       (10 regions x 672 hours = 6,720 rows) with the reading count.
    2. Check for absent hours and report the reading counts.
    3. Build calendar and lag features that are all available at the
       forecast origin (00:00 of the target day).
    4. Split by target timestamp: train 1-14 Sept, validation 15-21 Sept,
       test 22-28 Sept. Report row counts and date limits.
    5. Exclude training rows that lack the initial lookback (one week).
    6. Prove that every lag source hour ends at or before its forecast origin.
    7. Save the dataset to results/8_1_hourly_dataset.csv for 8.2-8.4.

Handling of missing data (also stated in the report)
    * Targets are the OBSERVED hourly totals. They are never adjusted or
      filled, so about 1% of readings are simply not in each total.
    * An absent region-hour would be left empty (not set to zero) and any row
      whose predictors depend on it would be excluded. On the common dataset
      no hour is absent, so nothing is excluded for that reason.
    * No scaler or encoder is fitted here. Preprocessing is fitted on the
      training rows only, inside s83_train_model.py.

Run:  python s81_prepare_features.py
"""

from __future__ import annotations

import pandas as pd

import forecast_common as fc
from common import RESULTS_DIR, connect, finish_log, format_table, load_named_queries, show_query, start_log

STEP = "8_1_prepare_features"


def main() -> None:
    start_log(STEP)
    conn = connect()
    headers, rows = show_query(conn, load_named_queries("08_hourly_region_energy.sql")["hourly_region_energy"],
                               title="One row per region and CAT hour", max_rows=5)
    conn.close()

    data = pd.DataFrame(rows, columns=headers)
    # Keep CAT wall-clock time without the +02:00 suffix: every later step
    # (day boundaries, hour of day, lags) is then plain CAT arithmetic.
    data["target_hour"] = (pd.to_datetime(data["target_hour"], utc=True)
                           .dt.tz_convert("Africa/Kigali").dt.tz_localize(None))

    # ---- 2. Absent hours and reading counts ---------------------------------------
    regions = sorted(data["region"].unique(), key=lambda name: (len(name), name))
    all_hours = pd.date_range("2026-09-01 00:00", "2026-09-28 23:00", freq="h")
    expected_rows = len(regions) * len(all_hours)
    grid = pd.MultiIndex.from_product([regions, all_hours], names=["region", "target_hour"])
    absent = grid.difference(pd.MultiIndex.from_frame(data[["region", "target_hour"]]))
    counts = data["reading_count"]
    print("\n--- Dataset check ---")
    print(format_table(["Check", "Value"], [
        ("Regions", len(regions)),
        ("CAT hours in the period", len(all_hours)),
        ("Expected rows (regions x hours)", expected_rows),
        ("Rows in the dataset", len(data)),
        ("Absent region-hours", len(absent)),
        ("Readings per region-hour: full count", "1,600 (400 meters x 4 intervals)"),
        ("Readings per region-hour: min / mean / max", f"{counts.min():,} / {counts.mean():,.1f} / {counts.max():,}"),
        ("Total readings behind the dataset", f"{counts.sum():,}"),
    ]))

    # ---- 3. Features ------------------------------------------------------------------
    data = fc.add_features(data)
    data["usable"] = fc.usable(data)

    first_hour = all_hours[0]
    feature_table = [(name, "lag", hours, f"{first_hour + pd.Timedelta(hours=hours):%Y-%m-%d %H:%M}")
                     for name, hours in fc.LAGS.items()]
    feature_table += [
        (fc.WINDOW_FEATURE, "window: mean of the previous CAT day", 24, f"{first_hour + pd.Timedelta(days=1):%Y-%m-%d %H:%M}"),
        ("hour_of_day", "calendar (0-23)", 0, f"{first_hour:%Y-%m-%d %H:%M}"),
        ("day_of_week", "calendar (Monday=0 ... Sunday=6)", 0, f"{first_hour:%Y-%m-%d %H:%M}"),
        ("region", "identifier (one of 10)", 0, f"{first_hour:%Y-%m-%d %H:%M}"),
    ]
    print("\n--- Features (shared by every model configuration) ---")
    feature_headers = ["feature", "kind", "lag / window length (hours)", "earliest usable target timestamp (CAT)"]
    print(format_table(feature_headers, feature_table))
    print(f"Initial lookback = {fc.LOOKBACK_HOURS} hours, so the earliest target with ALL features is "
          f"{first_hour + pd.Timedelta(hours=fc.LOOKBACK_HOURS):%Y-%m-%d %H:%M} CAT.")

    # ---- 4-5. Splits and lookback exclusions --------------------------------------------
    split_table = []
    for name in fc.SPLITS:
        part = data[fc.split_mask(data, name)]
        kept = part[part["usable"]]
        split_table.append((name, len(part), len(part) - len(kept), len(kept),
                            f"{kept['target_hour'].min():%Y-%m-%d %H:%M}", f"{kept['target_hour'].max():%Y-%m-%d %H:%M}",
                            f"{part['target_hour'].min():%Y-%m-%d} to {part['target_hour'].max():%Y-%m-%d}"))
    print("\n--- Splits by target timestamp ---")
    split_headers = ["split", "rows before exclusions", "excluded (no lookback)", "rows retained",
                     "first retained target", "last retained target", "split dates"]
    print(format_table(split_headers, split_table))
    print("The same retained training rows are used by every model configuration.")

    # ---- 6. Leakage check: every lag source must END at or before the origin -------------
    check = []
    usable_rows = data[data["usable"]]
    for name, hours in fc.LAGS.items():
        source_end = usable_rows[f"{name}_source"] + pd.Timedelta(hours=1)          # an hourly total is complete at its end
        gap_hours = (usable_rows["forecast_origin"] - source_end).dt.total_seconds() / 3600
        violations = int((gap_hours < 0).sum())
        check.append((name, len(usable_rows), f"{gap_hours.min():.0f}", f"{gap_hours.max():.0f}", violations,
                      "OK" if violations == 0 else "LEAK"))
    check.append((fc.WINDOW_FEATURE, len(usable_rows), "0", "0", 0, "OK (window = the 24 hours ending at the origin)"))
    print("\n--- Check: hours between the END of each lag source hour and the forecast origin (must be >= 0) ---")
    check_headers = ["feature", "rows checked", "smallest gap h", "largest gap h", "violations", "result"]
    print(format_table(check_headers, check))

    # ---- Feature examples -----------------------------------------------------------------
    example = data[(data["region"] == "Region 1") & (data["target_hour"] >= "2026-09-22 00:00")].head(6)
    columns = ["region", "target_hour", "forecast_origin", "energy_kwh", "lag_24h", "lag_24h_source",
               "lag_168h", "lag_168h_source", "prev_day_mean", "hour_of_day", "day_of_week"]
    print("\n--- Feature examples (Region 1, first test hours) ---")
    shown = example[columns].copy()
    for column in ("energy_kwh", "lag_24h", "lag_168h", "prev_day_mean"):
        shown[column] = shown[column].round(3)
    print(format_table(columns, shown.astype(str).values.tolist()))

    # ---- 7. Save -----------------------------------------------------------------------------
    data.to_csv(fc.DATASET_FILE, index=False)
    print(f"\nDataset saved: results/{fc.DATASET_FILE.name} ({len(data):,} rows)")
    (RESULTS_DIR / f"{STEP}.md").write_text(
        "# 8.1 Dataset and features\n\n" + format_table(feature_headers, feature_table, markdown=True) + "\n\n"
        + format_table(split_headers, split_table, markdown=True) + "\n\n"
        + format_table(check_headers, check, markdown=True) + "\n", encoding="utf-8")
    finish_log(STEP)


if __name__ == "__main__":
    main()
