"""Section 6.2 - Test freshness and delayed arrivals on a continuous aggregate.

A tiny, separate experiment that shows WHEN inserted rows become visible in a
continuous aggregate. The times are taken from the real clock when you run it.

    H      = start of the most recent COMPLETED CAT hour
             (run at 10:30 -> H is 09:00 of the same day)
    older  = H minus 48 hours

Timeline
    stage 1  insert 1.0 kWh into the older hour, refresh ONLY that hour
    stage 2  insert 0.5 kWh into the older hour (a late arrival) and 2.0 kWh
             into hour H (new data). No refresh. Real-time aggregation is off.
    stage 3  switch real-time aggregation on. Still no refresh.
    stage 4  manually refresh both complete hours.

Expected aggregate at each stage (from the assignment)
                                        older hour          hour H
    1 initial refresh, real-time off    1 kWh, 1 row        no bucket
    2 after inserts, real-time off      1 kWh, 1 row        no bucket
    3 real-time on, before refresh      1 kWh, 1 row        2 kWh, 1 row
    4 after refreshing both hours       1.5 kWh, 2 rows     2 kWh, 1 row

The raw table must show 1.5 kWh / 2 rows and 2 kWh / 1 row after all inserts.
"No bucket" is NOT a zero reading: the aggregate simply has no row for it.

Run:  python s62_freshness_test.py
"""

from __future__ import annotations

from datetime import timedelta

from common import (CAT, RESULTS_DIR, cat_text, connect, finish_log, format_table, load_named_queries,
                    now_cat, show_query, start_log)

STEP = "6_2_freshness"


def describe(rows, hour) -> str:
    """Turn the aggregate/raw rows into '1.5 kWh, 2 rows' or 'no bucket returned'."""
    for bucket, energy, count in rows:
        if bucket == hour:
            return f"{energy:g} kWh, {count} row{'s' if count != 1 else ''}"
    return "no bucket returned"


def main() -> None:
    start_log(STEP)
    queries = load_named_queries("06_2_freshness_test.sql")
    conn = connect()          # autocommit: refresh cannot run inside a transaction

    # ---- Times, taken from the real clock ------------------------------------------
    test_time = now_cat()
    h = test_time.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    older = h - timedelta(hours=48)
    events = {"older_first": older + timedelta(minutes=10),    # 1.0 kWh
              "older_late": older + timedelta(minutes=25),     # 0.5 kWh
              "hour_h": h + timedelta(minutes=10)}             # 2.0 kWh
    window = {"older": older, "h": h, "h_end": h + timedelta(hours=1)}
    times = [
        ("Actual test time (CAT)", cat_text(test_time)),
        ("H = start of most recent completed CAT hour", cat_text(h)),
        ("Older hour = H - 48 hours", cat_text(older)),
        ("event_time of the 1.0 kWh reading (older hour)", cat_text(events["older_first"])),
        ("event_time of the 0.5 kWh reading (older hour, late)", cat_text(events["older_late"])),
        ("event_time of the 2.0 kWh reading (hour H)", cat_text(events["hour_h"])),
    ]
    print(format_table(["Recorded time", "Value"], times))

    # ---- Objects: test hypertable + empty hourly aggregate, no policy ----------------
    for name in ("drop_view", "drop_table", "create_table", "create_hypertable", "create_view"):
        show_query(conn, queries[name])
    show_query(conn, queries["show_columns"], title="Test table and view columns")
    show_query(conn, queries["show_definitions"], title="View definition")
    show_query(conn, queries["policies_on_view"], title="Automatic refresh is off (no policy on this view)")
    show_query(conn, queries["realtime_setting"], title="Real-time aggregation setting")

    stages = []

    def snapshot(stage: str) -> None:
        """Query raw table and aggregate for both hours and remember the result."""
        _, raw = show_query(conn, queries["raw_by_hour"], window, title=f"{stage} | RAW test table")
        _, agg = show_query(conn, queries["aggregate_by_hour"], window, title=f"{stage} | AGGREGATE")
        stages.append((stage, describe(raw, older), describe(raw, h), describe(agg, older), describe(agg, h)))

    # ---- Stage 1: one reading in the older hour, refresh only that hour --------------
    show_query(conn, queries["insert_reading"], {"event_time": events["older_first"], "energy_kwh": 1.0},
               title=f"Insert 1.0 kWh at {cat_text(events['older_first'])}")
    show_query(conn, queries["refresh_window"], {"window_start": older, "window_end": older + timedelta(hours=1)},
               title=f"Refresh ONLY the older hour [{cat_text(older)} , +1 hour)")
    snapshot("1 Initial older-hour refresh, real-time off")

    # ---- Stage 2: a late reading in the older hour and a new reading in hour H --------
    show_query(conn, queries["insert_reading"], {"event_time": events["older_late"], "energy_kwh": 0.5},
               title=f"Insert 0.5 kWh at {cat_text(events['older_late'])} (late arrival for the older hour)")
    show_query(conn, queries["insert_reading"], {"event_time": events["hour_h"], "energy_kwh": 2.0},
               title=f"Insert 2.0 kWh at {cat_text(events['hour_h'])} (hour H)")
    snapshot("2 After both new inserts, before refresh, real-time off")

    # ---- Stage 3: real-time aggregation on, still no refresh ---------------------------
    show_query(conn, queries["enable_realtime"], title="Enable real-time aggregation")
    show_query(conn, queries["realtime_setting"], title="Real-time aggregation setting")
    snapshot("3 Real-time on, still before refresh")

    # ---- Stage 4: refresh both complete hours --------------------------------------------
    show_query(conn, queries["refresh_window"], {"window_start": older, "window_end": older + timedelta(hours=1)},
               title="Refresh the older hour")
    show_query(conn, queries["refresh_window"], {"window_start": h, "window_end": h + timedelta(hours=1)},
               title="Refresh hour H")
    snapshot("4 After manual refresh of both hours")
    conn.close()

    # ---- Comparison with the expected table ------------------------------------------------
    expected = [("1 kWh, 1 row", "no bucket returned"), ("1 kWh, 1 row", "no bucket returned"),
                ("1 kWh, 1 row", "2 kWh, 1 row"), ("1.5 kWh, 2 rows", "2 kWh, 1 row")]
    headers = ["stage", "raw older hour", "raw hour H", "aggregate older hour", "aggregate hour H", "as expected"]
    table = [(*stage, "YES" if (stage[3], stage[4]) == want else "NO") for stage, want in zip(stages, expected)]
    print("\n--- Stage comparison ---")
    print(format_table(headers, table))

    # ---- Which hours could the 6.1 policy refresh at the recorded test time? ---------------
    # Policy window = [now - 3 days, now - 1 hour]. Only buckets that lie
    # completely inside the window are refreshed.
    window_start, window_end = test_time - timedelta(days=3), test_time - timedelta(hours=1)
    first_hour = (window_start.replace(minute=0, second=0, microsecond=0)
                  + (timedelta(hours=1) if window_start.minute or window_start.second else timedelta()))
    last_hour = window_end.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)

    def covered(hour) -> str:
        return "YES" if first_hour <= hour <= last_hour else "NO"

    policy = [
        ("Policy window at test time", f"{cat_text(window_start)}  to  {cat_text(window_end)}"),
        ("Hourly buckets fully inside the window", f"{first_hour.astimezone(CAT):%Y-%m-%d %H:%M}  to  "
                                                    f"{last_hour.astimezone(CAT):%Y-%m-%d %H:%M} (bucket starts)"),
        (f"Older hour {older:%Y-%m-%d %H:%M} refreshable by the policy?", covered(older)),
        (f"Hour H {h:%Y-%m-%d %H:%M} refreshable by the policy?",
         f"{covered(h)} (it ends at {h + timedelta(hours=1):%H:%M}, after the window end {window_end:%H:%M})"),
    ]
    print("\n--- What a 6.1-style policy (3-day lookback, 1-hour end offset) could refresh at the test time ---")
    print(format_table(["Question", "Answer"], policy))

    print("""
What became visible at each stage
    Stage 1  The refresh materialized the older hour: 1 kWh, 1 row. Hour H has
             no data and no stored bucket.
    Stage 2  The raw table already holds all three rows, but the aggregate is
             unchanged. With real-time off it returns ONLY stored buckets, so
             neither the late 0.5 kWh nor the new 2 kWh is visible.
    Stage 3  Real-time aggregation adds raw rows NEWER than the last refreshed
             point (the watermark, which is the end of the older hour). Hour H
             is newer, so its 2 kWh appears. The late 0.5 kWh lies in an hour
             that is already materialized, BEHIND the watermark, so real-time
             aggregation does not see it: the older hour still shows 1 kWh.
    Stage 4  A refresh recomputes the invalidated older hour (now 1.5 kWh,
             2 rows) and materializes hour H (2 kWh, 1 row). Aggregate = raw.
    Lesson   Late arrivals into already-materialized buckets only appear after
             a refresh that covers them. That is what the lookback is for.""")

    (RESULTS_DIR / f"{STEP}.md").write_text(
        "# 6.2 Freshness and delayed arrivals\n\n" + format_table(["Recorded time", "Value"], times, markdown=True)
        + "\n\n" + format_table(headers, table, markdown=True) + "\n\n"
        + format_table(["Question", "Answer"], policy, markdown=True) + "\n", encoding="utf-8")
    print(f"RESULT: {'all four stages match the expected table' if all(row[-1] == 'YES' for row in table) else 'a stage differs from the expected table'}")
    finish_log(STEP)


if __name__ == "__main__":
    main()
