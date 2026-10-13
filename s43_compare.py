"""Section 4.3 - One comparison of all five table configurations.

Run this AFTER the compressed tables were benchmarked:

    python s32_benchmark.py --label 4_3 --tables energy_time_compressed energy_meter_compressed --reference <baseline>
    python s43_compare.py

It merges two recorded benchmark sessions
    results/3_2_summary.json   three uncompressed chunk configurations
    results/4_3_summary.json   two compressed configurations
and calculates, for each compressed table and query,

    improvement % = 100 * (baseline median - compressed median) / baseline median

where the baseline is the uncompressed table with the same chunk interval
(named in results/4_choice.json). Positive = faster than the baseline.
Negative = slower.
"""

from __future__ import annotations

import json

from common import RESULTS_DIR, finish_log, format_table, start_log

STEP = "4_3_compare"
QUERY_NAMES = ["Q1", "Q2", "Q3", "Q4", "Q5"]


def main() -> None:
    start_log(STEP)
    uncompressed = json.loads((RESULTS_DIR / "3_2_summary.json").read_text(encoding="utf-8"))
    compressed = json.loads((RESULTS_DIR / "4_3_summary.json").read_text(encoding="utf-8"))
    baseline = json.loads((RESULTS_DIR / "4_choice.json").read_text(encoding="utf-8"))["baseline"]

    tables = uncompressed["tables"] + compressed["tables"]
    stats = {(s["query"], s["table"]): s for s in uncompressed["summary"] + compressed["summary"]}

    print(f"Baseline for improvement: {baseline}")
    print(f"Uncompressed session: {uncompressed['session_start']} to {uncompressed['session_end']} "
          f"({uncompressed['session_seconds']:,.1f} s)   client: {uncompressed['client']}")
    print(f"Compressed session  : {compressed['session_start']} to {compressed['session_end']} "
          f"({compressed['session_seconds']:,.1f} s)   client: {compressed['client']}")
    print(f"All results matched : uncompressed {uncompressed['all_results_match']}, "
          f"compressed {compressed['all_results_match']}")

    # ---- All five configurations: median (min - max) -----------------------------------
    rows = []
    for name in QUERY_NAMES:
        row = [name]
        for table in tables:
            s = stats[(name, table)]
            row.append(f"{s['median_ms']:,.1f} ({s['min_ms']:,.1f} - {s['max_ms']:,.1f})")
        rows.append(row)
    print("\n--- WARM-CACHE median ms (min - max), all five configurations ---")
    print(format_table(["query"] + tables, rows))

    # ---- Improvement of each compressed table over the baseline --------------------------
    improvement_rows = []
    for name in QUERY_NAMES:
        base = stats[(name, baseline)]["median_ms"]
        row = [name, f"{base:,.1f}"]
        for table in compressed["tables"]:
            median = stats[(name, table)]["median_ms"]
            change = 100 * (base - median) / base
            row += [f"{median:,.1f}", f"{change:+.1f} %", "faster" if change > 0 else "slower"]
        improvement_rows.append(row)
    headers = ["query", f"baseline median ms ({baseline})"]
    for table in compressed["tables"]:
        short = table.replace("energy_", "").replace("_compressed", "")
        headers += [f"{table} median ms", f"improvement ({short})", f"vs baseline ({short})"]
    print("\n--- Improvement = 100 * (baseline median - compressed median) / baseline median ---")
    print(format_table(headers, improvement_rows))
    print("Positive = faster than the uncompressed baseline. Negative = slower.")

    (RESULTS_DIR / f"{STEP}.md").write_text(
        "# 4.3 Five-configuration comparison (warm cache, ms)\n\n"
        + format_table(["query"] + tables, rows, markdown=True) + "\n\n"
        + format_table(headers, improvement_rows, markdown=True) + "\n", encoding="utf-8")
    finish_log(STEP)


if __name__ == "__main__":
    main()
