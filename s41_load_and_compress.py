"""Section 4.1 - Create, load and compress the two compressed configurations.

You choose ONE chunk interval from Section 3 by naming its uncompressed table:

    python s41_load_and_compress.py --baseline energy_readings        (1 day)
    python s41_load_and_compress.py --baseline energy_readings_3h     (3 hours)
    python s41_load_and_compress.py --baseline energy_readings_week   (1 week)

That table is the uncompressed BASELINE for all of Section 4. The choice is
saved in results/4_choice.json so the later scripts use the same baseline.

What happens, in order
    1. Record the experiment start time and ONE cutoff = start - 48 hours.
       The same cutoff is used for both tables for the whole experiment.
    2. Create two EMPTY hypertables with the chosen interval, the same eight
       columns and the same two indexes.
    3. Set compression: both order by event_time DESC; only
       energy_meter_compressed is segmented by meter_id.
    4. Add a "compress chunks older than 48 hours" policy to each table and
       PAUSE both (they are resumed after the 4.3 measurements).
    5. For each table, copy the cleaned data ONE CHUNK AT A TIME. As soon as a
       chunk is fully loaded, compress it manually if its end is before the
       cutoff. Loading and compression are timed SEPARATELY.
    6. Verify that both tables have the same time ranges compressed and that
       both hold the same data as the baseline (the 3.1 data checks).

Every chunk's row count, load seconds and compression seconds are written to
results/4_1_compression_log.csv. Section 4.2 reads that file.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import timedelta

import smart_meter_simulator as sim

from common import (RESULTS_DIR, cat_text, connect, finish_log, format_table, load_named_queries,
                    now_cat, show_query, start_log)

STEP = "4_1_load_and_compress"
TARGETS = ["energy_time_compressed", "energy_meter_compressed"]
BASELINES = ["energy_readings_3h", "energy_readings", "energy_readings_week"]
TOLERANCE = 0.001


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the two compressed hypertables.")
    parser.add_argument("--baseline", required=True, choices=BASELINES,
                        help="uncompressed table whose chunk interval you chose in Section 3")
    args = parser.parse_args()
    start_log(STEP)

    queries = load_named_queries("04_1_compressed_tables.sql")
    verify = load_named_queries("03_1_verify.sql")
    conn = connect()

    # The interval is read from the baseline table itself, so the compressed
    # tables are guaranteed to use exactly the same chunk interval.
    interval = conn.execute(
        "SELECT time_interval FROM timescaledb_information.dimensions WHERE hypertable_name = %s",
        (args.baseline,)).fetchone()[0]
    interval_text = f"{int(interval.total_seconds())} seconds"

    # ---- 1. Experiment start and the single cutoff --------------------------------
    experiment_start = now_cat()
    cutoff = experiment_start - timedelta(hours=48)
    print(f"Baseline table      : {args.baseline}  (chunk interval {interval})")
    print(f"Experiment start    : {cat_text(experiment_start)}")
    print(f"Compression cutoff  : {cat_text(cutoff)}   (= start - 48 hours, used for BOTH tables)")
    print("Rule                : a chunk is compressed when its range_end is earlier than the cutoff")

    # ---- 2-4. Tables, indexes, compression settings, paused policies ---------------
    for name in ("drop_tables", "create_time_table", "create_meter_table", "hypertable_time",
                 "hypertable_meter", "index_time_1", "index_time_2", "index_meter_1", "index_meter_2",
                 "compression_time", "compression_meter", "policy_time", "policy_meter", "pause_policies"):
        show_query(conn, queries[name].replace("{interval}", interval_text))
    show_query(conn, queries["show_configuration"], title="Both configurations")
    show_query(conn, queries["show_settings"], title="Compression settings (orderby / segmentby)")
    show_query(conn, queries["show_policies"], title="Compression policies (enabled = false means paused)")

    # ---- 5. Load chunk by chunk, compress chunk by chunk ---------------------------
    chunks = conn.execute(queries["baseline_chunks"], {"baseline": args.baseline}).fetchall()
    print(f"\n{args.baseline} has {len(chunks)} chunks. Copying them one at a time.")
    log_rows = []
    for target in TARGETS:
        print(f"\n--- Loading and compressing {target} ---")
        copy_sql = queries["copy_one_chunk"].format(target=target, baseline=args.baseline)
        print(copy_sql)
        print()
        for number, (range_start, range_end) in enumerate(chunks, start=1):
            # (a) load one chunk's time range - timed on its own
            started = time.perf_counter()
            rows = conn.execute(copy_sql, {"range_start": range_start, "range_end": range_end}).rowcount
            load_seconds = time.perf_counter() - started

            # (b) compress it if the whole chunk is older than the cutoff - timed on its own
            chunk = conn.execute(queries["find_chunk"], {"target": target, "range_start": range_start}).fetchone()
            compress_seconds, compressed, compress_start = 0.0, False, ""
            if chunk and range_end < cutoff:
                compress_start = cat_text()
                started = time.perf_counter()
                conn.execute(queries["compress_one_chunk"], {"chunk": chunk[0]})
                compress_seconds = time.perf_counter() - started
                compressed = True
            log_rows.append({"table": target, "chunk": chunk[0] if chunk else "", "range_start": range_start,
                             "range_end": range_end, "rows": rows, "load_seconds": round(load_seconds, 4),
                             "compressed": compressed, "compress_start_cat": compress_start,
                             "compress_seconds": round(compress_seconds, 4)})
            print(f"  chunk {number:>3}/{len(chunks)}  {range_start:%Y-%m-%d %H:%M} to {range_end:%Y-%m-%d %H:%M}  "
                  f"rows {rows:>9,}  load {load_seconds:6.2f} s  "
                  f"{'compress ' + format(compress_seconds, '6.2f') + ' s' if compressed else 'left uncompressed (newer than cutoff)'}")
        conn.execute(f"ANALYZE {target}")
        done = [r for r in log_rows if r["table"] == target]
        print(f"  {target}: {sum(r['rows'] for r in done):,} rows, "
              f"load {sum(r['load_seconds'] for r in done):,.1f} s, "
              f"compression {sum(r['compress_seconds'] for r in done):,.1f} s "
              f"({sum(r['compressed'] for r in done)} of {len(done)} chunks compressed)")

    with open(RESULTS_DIR / "4_1_compression_log.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(log_rows[0].keys()))
        writer.writeheader()
        writer.writerows(log_rows)
    (RESULTS_DIR / "4_choice.json").write_text(json.dumps({
        "baseline": args.baseline, "chunk_interval": str(interval),
        "experiment_start": cat_text(experiment_start), "cutoff": cat_text(cutoff)}, indent=2), encoding="utf-8")

    # ---- 6. Verification -------------------------------------------------------------
    show_query(conn, queries["compressed_chunk_list"], title="Compressed-chunk list", max_rows=500)
    _, mismatched = show_query(conn, queries["compressed_ranges_match"],
                               title="Ranges compressed in one table but not the other (must be 0 rows)")

    expected_rows = sim.dataset_info()["expected_counts"]["unique_readings"]
    results = {}
    for table in [args.baseline] + TARGETS:
        headers, rows = show_query(conn, verify["data_check"].format(table=table), title=f"Data check: {table}")
        results[table] = dict(zip(headers, rows[0]))
    conn.close()

    reference, summary, all_ok = results[args.baseline], [], not mismatched
    for table, values in results.items():
        ok = (values["row_count"] == expected_rows and values["distinct_meters"] == 4000
              and values["earliest_event_time"] == reference["earliest_event_time"]
              and values["latest_event_time"] == reference["latest_event_time"]
              and abs(values["sum_power_kw"] - reference["sum_power_kw"]) <= TOLERANCE
              and abs(values["sum_energy_kwh"] - reference["sum_energy_kwh"]) <= TOLERANCE)
        all_ok &= ok
        summary.append((table, values["row_count"], values["distinct_meters"], values["earliest_event_time"],
                        values["latest_event_time"], f"{values['sum_power_kw']:.6f}",
                        f"{values['sum_energy_kwh']:.6f}", "MATCH" if ok else "MISMATCH"))
    print("\n--- Matching data checks (baseline and both compressed tables) ---")
    headers = ["table", "rows", "meters", "earliest", "latest", "sum power_kw", "sum energy_kwh", "status"]
    print(format_table(headers, summary))
    (RESULTS_DIR / f"{STEP}.md").write_text(
        f"# 4.1 Compressed configurations\n\nBaseline: {args.baseline} ({interval})  \n"
        f"Experiment start: {cat_text(experiment_start)}  \nCutoff: {cat_text(cutoff)}\n\n"
        + format_table(headers, summary, markdown=True) + "\n", encoding="utf-8")

    print(f"\nRESULT: {'both compressed tables match the baseline and each other' if all_ok else 'MISMATCH - investigate'}")
    finish_log(STEP)


if __name__ == "__main__":
    main()
