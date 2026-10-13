"""Section 6.1 (step 3) - Populate the three continuous aggregates and measure them.

Run sql/06_1_continuous_aggregates.sql first (it creates the three EMPTY views).

For each view this program
    1. confirms the view is empty,
    2. manually refreshes the ENTIRE generated period
       (1 September 00:00 CAT up to, but not including, 29 September 00:00 CAT)
       and reports the refresh duration in seconds,
    3. reports the materialized data size and index size.
Only after all three measurements are complete does it
    4. add the refresh policies (3-day lookback, 1-hour end offset, every
       15 minutes) from sql/06_1_policies.sql,
    5. print the view settings, sample rows, policy settings and job status.

The measurements are saved in results/6_1_aggregates.json because Section 7.4
reports them next to the dashboard timings.

Run:  python s61_refresh_aggregates.py
"""

from __future__ import annotations

import json
import time

from common import (PERIOD_END, PERIOD_START, RESULTS_DIR, cat_text, connect, finish_log, format_table,
                    load_named_queries, show_query, start_log)

STEP = "6_1_aggregates"
VIEWS = ["agg_region_15min", "agg_region_hourly", "agg_meter_daily"]
MB = 1024 * 1024


def main() -> None:
    start_log(STEP)
    queries = load_named_queries("06_1_policies.sql")
    conn = connect()          # autocommit: refresh_continuous_aggregate cannot run inside a transaction

    measurements = []
    for view in VIEWS:
        before = conn.execute(f"SELECT count(*) FROM {view}").fetchone()[0]
        refresh_sql = (f"CALL refresh_continuous_aggregate('{view}', "
                       f"TIMESTAMPTZ '{PERIOD_START}', TIMESTAMPTZ '{PERIOD_END}')")
        print(f"\n--- Manual refresh of {view} (rows before: {before:,}) ---")
        print(refresh_sql)
        started_text, started = cat_text(), time.perf_counter()
        conn.execute(refresh_sql)                       # the timed operation
        seconds = time.perf_counter() - started
        after = conn.execute(f"SELECT count(*) FROM {view}").fetchone()[0]
        print(f"Refresh finished: {seconds:,.2f} s   (started {started_text}, ended {cat_text()})   rows now: {after:,}")

        _, size = show_query(conn, queries["view_size"], {"view": view}, title=f"Stored size of {view}")
        _, data_bytes, index_bytes, total_bytes = size[0]
        measurements.append({"view": view, "rows_before": before, "rows": after, "refresh_seconds": seconds,
                             "data_bytes": data_bytes, "index_bytes": index_bytes, "total_bytes": total_bytes,
                             "refreshed_at": started_text})

    headers = ["view", "rows", "initial refresh s", "data MB", "index MB", "total MB"]
    table = [(m["view"], m["rows"], f"{m['refresh_seconds']:.2f}", f"{m['data_bytes'] / MB:.2f}",
              f"{m['index_bytes'] / MB:.2f}", f"{m['total_bytes'] / MB:.2f}") for m in measurements]
    print("\n--- Storage and initial refresh cost (measured BEFORE any policy exists) ---")
    print(format_table(headers, table))
    print(f"Total: {sum(m['refresh_seconds'] for m in measurements):.2f} s refresh, "
          f"{sum(m['total_bytes'] for m in measurements) / MB:.2f} MB stored")

    # ---- Policies are added only now, after the measurements --------------------
    # (if_not_exists => TRUE in the SQL makes this safe to run more than once.)
    for name in ("policy_15min", "policy_hourly", "policy_daily"):
        show_query(conn, queries[name])

    # ---- Evidence -----------------------------------------------------------------
    show_query(conn, queries["view_settings"], title="View settings (materialized_only = TRUE means real-time is off)")
    show_query(conn, "SELECT * FROM agg_region_15min ORDER BY bucket, length(region), region LIMIT 5",
               title="Sample rows: agg_region_15min")
    show_query(conn, "SELECT * FROM agg_region_hourly ORDER BY bucket, length(region), region LIMIT 5",
               title="Sample rows: agg_region_hourly")
    show_query(conn, "SELECT * FROM agg_meter_daily ORDER BY bucket, meter_id LIMIT 5",
               title="Sample rows: agg_meter_daily")
    # Does the stored aggregate add up to the raw table? (same total energy and count)
    show_query(conn, """
SELECT 'energy_readings (raw)' AS source, sum(energy_kwh) AS energy_kwh, count(*) AS readings FROM energy_readings
UNION ALL SELECT 'agg_region_15min',  sum(energy_kwh_sum), sum(reading_count) FROM agg_region_15min
UNION ALL SELECT 'agg_region_hourly', sum(energy_kwh_sum), sum(reading_count) FROM agg_region_hourly
UNION ALL SELECT 'agg_meter_daily',   sum(energy_kwh_sum), sum(reading_count) FROM agg_meter_daily""",
               title="Stored aggregates agree with the raw table")
    show_query(conn, queries["show_policies"], title="Policy settings and background job status")
    conn.close()

    (RESULTS_DIR / f"{STEP}.json").write_text(json.dumps(measurements, indent=2), encoding="utf-8")
    (RESULTS_DIR / f"{STEP}.md").write_text(
        "# 6.1 Continuous aggregates: storage and initial refresh\n\n"
        + format_table(headers, table, markdown=True) + "\n", encoding="utf-8")
    finish_log(STEP)


if __name__ == "__main__":
    main()
