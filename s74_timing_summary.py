"""Section 7.4 - Summarise the dashboard timings and weigh them against the cost.

Input: results/7_4_dashboard_timings.csv, written by the dashboards when the
"Run timing test" button is pressed (once on /raw and once on /aggregate).
For each mode the LATEST timing session is used: 1 warm-up (ignored) and
10 measured refreshes.

Output
    * median / minimum / maximum in ms for each panel query and for the whole
      dashboard (refresh request until all five panels rendered), per mode
    * the speed-up of Aggregate over Raw
    * the price paid for it: aggregate storage and initial refresh time (6.1)

Run:  python s74_timing_summary.py
"""

from __future__ import annotations

import csv
import json
import statistics

from common import RESULTS_DIR, finish_log, format_table, start_log

STEP = "7_4_dashboard_timing"
MEASURES = [("p1_query_ms", "Panel 1 query: hourly regional energy"),
            ("p2_query_ms", "Panel 2 query: daily network energy"),
            ("p3_query_ms", "Panel 3 query: seven-day periods"),
            ("p4_query_ms", "Panel 4 query: selected meter daily"),
            ("p5_query_ms", "Panel 5 query: completeness by region"),
            ("dashboard_ms", "Whole dashboard: refresh until all 5 panels rendered")]
MB = 1024 * 1024


def latest_session(rows: list[dict], mode: str) -> list[dict]:
    """Measured refreshes of the most recent timing session of one mode."""
    sessions = [row["session"] for row in rows if row["mode"] == mode and row["run_type"] == "measured"]
    if not sessions:
        raise SystemExit(f"No timing session found for the {mode} dashboard. "
                         f"Open http://localhost:8050/{mode} and press 'Run timing test'.")
    last = sessions[-1]
    return [row for row in rows if row["session"] == last and row["run_type"] == "measured"]


def main() -> None:
    start_log(STEP)
    with open(RESULTS_DIR / "7_4_dashboard_timings.csv", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    runs = {mode: latest_session(rows, mode) for mode in ("raw", "aggregate")}
    for mode, measured in runs.items():
        first = measured[0]
        print(f"{mode:<9}: {len(measured)} measured refreshes, {first['start_cat']} to {measured[-1]['end_cat']}, "
              f"days {first['first_day']} to {first['last_day']}, meter {first['meter_id']}, machine {first['machine']}")
        print(f"           browser: {first['browser']}")
    print("Tools     : browser performance.now() for the dashboard time, server time.perf_counter() for query times")
    print("Caching   : none (every refresh re-runs all five queries); 1 warm-up refresh precedes the 10 measured")

    stats = {mode: {column: [float(row[column]) for row in measured] for column, _ in MEASURES}
             for mode, measured in runs.items()}
    table = []
    for column, label in MEASURES:
        raw, agg = stats["raw"][column], stats["aggregate"][column]
        raw_median, agg_median = statistics.median(raw), statistics.median(agg)
        table.append((label, f"{raw_median:,.1f}", f"{min(raw):,.1f}", f"{max(raw):,.1f}",
                      f"{agg_median:,.1f}", f"{min(agg):,.1f}", f"{max(agg):,.1f}",
                      f"{raw_median / agg_median:,.1f} x" if agg_median else "n/a"))
    headers = ["measurement (ms)", "Raw median", "Raw min", "Raw max",
               "Aggregate median", "Aggregate min", "Aggregate max", "Raw / Aggregate"]
    print("\n--- Dashboard timing comparison ---")
    print(format_table(headers, table))

    # ---- The cost side: what the aggregates needed (from 6.1) ----------------------
    aggregates = json.loads((RESULTS_DIR / "6_1_aggregates.json").read_text(encoding="utf-8"))
    cost = [(a["view"], a["rows"], f"{a['total_bytes'] / MB:.2f}", f"{a['refresh_seconds']:.2f}") for a in aggregates]
    cost.append(("TOTAL", sum(a["rows"] for a in aggregates),
                 f"{sum(a['total_bytes'] for a in aggregates) / MB:.2f}",
                 f"{sum(a['refresh_seconds'] for a in aggregates):.2f}"))
    cost_headers = ["continuous aggregate", "stored rows", "storage MB (data + index)", "initial refresh s"]
    print("\n--- Cost of the aggregates (measured in 6.1) ---")
    print(format_table(cost_headers, cost))

    raw_dash = statistics.median(stats["raw"]["dashboard_ms"])
    agg_dash = statistics.median(stats["aggregate"]["dashboard_ms"])
    saved_ms = raw_dash - agg_dash
    refresh_ms = sum(a["refresh_seconds"] for a in aggregates) * 1000
    print(f"\nEach refresh is {saved_ms:,.0f} ms faster on Aggregate (median {raw_dash:,.0f} ms -> {agg_dash:,.0f} ms).")
    if saved_ms > 0:
        print(f"The one-off initial refresh ({refresh_ms / 1000:,.1f} s) is repaid after about "
              f"{refresh_ms / saved_ms:,.0f} dashboard refreshes.")
    else:
        print("Aggregate was not faster in this run, so the refresh and storage cost is not repaid by speed.")

    (RESULTS_DIR / f"{STEP}.md").write_text(
        "# 7.4 Dashboard timing (10 measured refreshes after 1 warm-up, ms)\n\n"
        + format_table(headers, table, markdown=True) + "\n\n"
        + format_table(cost_headers, cost, markdown=True) + "\n", encoding="utf-8")
    finish_log(STEP)


if __name__ == "__main__":
    main()
