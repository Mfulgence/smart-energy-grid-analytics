"""Section 7.3 - Verify that the Raw and Aggregate dashboards show the same numbers.

Filters are fixed to the values the assignment requires
    22 September 00:00 CAT  up to, not including,  29 September 00:00 CAT
    all regions, meter 1000000000 for the meter-history panel

For each of the five panels this program
    1. runs the Raw query and the Aggregate query (the exact SQL the dashboards use),
    2. saves the data behind both panels as CSV in results/,
    3. matches rows by their key (bucket, region or meter),
    4. reports the compared row count and the largest absolute difference.

Pass rules
    identical keys and identical reading counts
    energy difference        <= 0.001 kWh
    completeness difference  <= 0.000001 percentage points (before rounding)

Run:  python s73_verify_dashboards.py
      python s73_verify_dashboards.py --show-queries     (print the panel SQL of both dashboards)
"""

from __future__ import annotations

import argparse
import csv

import dashboard_queries as dq
from common import RESULTS_DIR, connect, finish_log, format_table, start_log

STEP = "7_3_verify_dashboards"
ENERGY_TOLERANCE = 0.001            # kWh
COMPLETENESS_TOLERANCE = 0.000001   # percentage points


def save_csv(name: str, headers: list[str], rows: list) -> None:
    with open(RESULTS_DIR / f"{name}.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare the data behind both dashboards.")
    parser.add_argument("--show-queries", action="store_true", help="print every panel query and exit")
    args = parser.parse_args()

    if args.show_queries:
        start_log("7_2_panel_queries")
        for mode, name in dq.MODES.items():
            for panel, spec in dq.PANELS.items():
                print(f"\n===== {name} dashboard | panel {panel[1]}: {spec['title']} ({spec['unit']}) =====")
                print(dq.panel_sql(mode, panel))
        finish_log("7_2_panel_queries")
        return

    start_log(STEP)
    start, end = dq.period_bounds(dq.DEFAULT_START, dq.DEFAULT_END)
    print(f"Filters: {start:%Y-%m-%d %H:%M %Z} (inclusive) to {end:%Y-%m-%d %H:%M %Z} (exclusive), "
          f"all regions, meter {dq.DEFAULT_METER}")

    conn = connect()
    report, all_ok = [], True
    for panel, spec in dq.PANELS.items():
        data = {}
        for mode in dq.MODES:
            headers, rows, _ = dq.run_panel(conn, mode, panel, dq.DEFAULT_START, dq.DEFAULT_END, dq.DEFAULT_METER)
            save_csv(f"7_3_panel{panel[1]}_{mode}", headers, rows)
            data[mode] = (headers, rows)
            print(f"\n--- Panel {panel[1]} {spec['title']} | {dq.MODES[mode]} | first rows of {len(rows)} ---")
            print(format_table(headers, rows[:4]))

        # Index every row by its key columns so rows can be matched one to one.
        def index(mode: str) -> dict:
            headers, rows = data[mode]
            key_positions = [headers.index(name) for name in spec["keys"]]
            return {tuple(row[i] for i in key_positions): dict(zip(headers, row)) for row in rows}

        raw, agg = index("raw"), index("aggregate")
        same_keys = raw.keys() == agg.keys()
        shared = raw.keys() & agg.keys()
        count_mismatches = sum(1 for key in shared if raw[key]["reading_count"] != agg[key]["reading_count"])
        max_difference = max((abs(raw[key][spec["value"]] - agg[key][spec["value"]]) for key in shared), default=0.0)
        tolerance = COMPLETENESS_TOLERANCE if panel == "p5" else ENERGY_TOLERANCE
        ok = same_keys and count_mismatches == 0 and max_difference <= tolerance and len(shared) > 0
        all_ok &= ok
        report.append((f"{panel[1]} {spec['title']}", " + ".join(spec["keys"]), len(raw), len(agg), len(shared),
                       "identical" if same_keys else "DIFFERENT", count_mismatches,
                       f"{max_difference:.9f} {'pp' if panel == 'p5' else 'kWh'}", f"{tolerance:g}",
                       "PASS" if ok else "FAIL"))
    conn.close()

    headers = ["panel", "matched by", "raw rows", "aggregate rows", "compared rows", "keys",
               "reading-count mismatches", "max abs difference", "allowed", "result"]
    print("\n--- Numerical check of all five panels ---")
    print(format_table(headers, report))
    (RESULTS_DIR / f"{STEP}.md").write_text(
        "# 7.3 Raw vs Aggregate dashboard data\n\n" + format_table(headers, report, markdown=True) + "\n",
        encoding="utf-8")
    print("\nPanel data exported to results/7_3_panel<N>_raw.csv and results/7_3_panel<N>_aggregate.csv")
    print(f"RESULT: {'both dashboards return matching data - safe to time them' if all_ok else 'DIFFERENCES FOUND - fix before timing'}")
    finish_log(STEP)


if __name__ == "__main__":
    main()
