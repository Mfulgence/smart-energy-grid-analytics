"""Section 4.2 - Measure storage and compression cost.

Inputs
    results/4_choice.json            which uncompressed table is the baseline
    results/4_1_compression_log.csv  rows and compression seconds of every chunk
    the database                     current sizes of the three tables

Formulas (exactly as given in the assignment)
    compression ratio   = baseline total size / compressed table total size
    percentage saved    = 100 * (baseline size - compressed size) / baseline size
    compression cost    = sum of the measured chunk compression times
                          (data loading is excluded)
    rows in compressed chunks % = 100 * original rows of the compressed chunks
                                  / full cleaned row count

Sizes include every chunk (compressed or not) and their indexes.
For a compressed table most data is stored in PostgreSQL's TOAST storage, so
"data" below is table + TOAST and "total" is data + indexes.

Run:  python s42_storage_report.py
"""

from __future__ import annotations

import csv
import json

import smart_meter_simulator as sim

from common import RESULTS_DIR, connect, finish_log, format_table, show_query, start_log

STEP = "4_2_storage"
TARGETS = ["energy_time_compressed", "energy_meter_compressed"]
MB = 1024 * 1024

# hypertable_detailed_size() adds up all chunks of one hypertable, including
# the hidden tables that hold compressed data.
SIZE_SQL = """
SELECT %(table)s::text                                       AS hypertable,
       table_bytes + coalesce(toast_bytes, 0)                AS data_bytes,
       index_bytes,
       total_bytes
FROM hypertable_detailed_size(%(table)s::regclass)"""

# Before/after sizes recorded by TimescaleDB itself for the compressed chunks.
STATS_SQL = """
SELECT '{table}' AS hypertable,
       total_chunks,
       number_compressed_chunks                            AS compressed_chunks,
       pg_size_pretty(before_compression_total_bytes)      AS before_compression,
       pg_size_pretty(after_compression_total_bytes)       AS after_compression
FROM hypertable_compression_stats('{table}')"""


def main() -> None:
    start_log(STEP)
    choice = json.loads((RESULTS_DIR / "4_choice.json").read_text(encoding="utf-8"))
    baseline = choice["baseline"]
    with open(RESULTS_DIR / "4_1_compression_log.csv", encoding="utf-8") as handle:
        log_rows = list(csv.DictReader(handle))
    cleaned_rows = sim.dataset_info()["expected_counts"]["unique_readings"]

    print(f"Baseline (uncompressed, same chunk interval): {baseline}  ({choice['chunk_interval']})")
    print(f"Cutoff used in 4.1: {choice['cutoff']}")

    conn = connect()
    sizes = {}
    for table in [baseline] + TARGETS:
        headers, rows = show_query(conn, SIZE_SQL, {"table": table}, title=f"Size of {table}")
        sizes[table] = dict(zip(headers, rows[0]))
    for table in TARGETS:
        show_query(conn, STATS_SQL.format(table=table), title=f"TimescaleDB compression statistics: {table}")

    # Live chunk states, used for "compressed chunk count out of total chunks".
    chunk_state = {}
    for table in TARGETS:
        chunk_state[table] = conn.execute(
            "SELECT count(*) FILTER (WHERE is_compressed), count(*) "
            "FROM timescaledb_information.chunks WHERE hypertable_name = %s", (table,)).fetchone()
    conn.close()

    # ---- Storage table ---------------------------------------------------------------
    base = sizes[baseline]
    storage = [(table, f"{s['data_bytes'] / MB:,.1f}", f"{s['index_bytes'] / MB:,.1f}", f"{s['total_bytes'] / MB:,.1f}")
               for table, s in sizes.items()]
    print("\n--- Final sizes in MB (all chunks and their indexes) ---")
    storage_headers = ["table", "data MB", "index MB", "total MB"]
    print(format_table(storage_headers, storage))

    # ---- Ratio, saving, cost, coverage -------------------------------------------------
    report = []
    for table in TARGETS:
        mine = [row for row in log_rows if row["table"] == table]
        compressed = [row for row in mine if row["compressed"] == "True"]
        compression_seconds = sum(float(row["compress_seconds"]) for row in compressed)
        load_seconds = sum(float(row["load_seconds"]) for row in mine)
        rows_compressed = sum(int(row["rows"]) for row in compressed)   # ORIGINAL row counts
        total = sizes[table]["total_bytes"]
        compressed_now, chunks_now = chunk_state[table]
        report.append({
            "table": table,
            "ratio": base["total_bytes"] / total,
            "saved_percent": 100 * (base["total_bytes"] - total) / base["total_bytes"],
            "compression_seconds": compression_seconds,
            "load_seconds_excluded": load_seconds,
            "compressed_chunks": compressed_now, "total_chunks": chunks_now,
            "rows_in_compressed_chunks": rows_compressed,
            "rows_percent": 100 * rows_compressed / cleaned_rows,
        })
    headers = ["strategy", "compression ratio", "saved %", "compression s (sum of chunks)",
               "load s (excluded)", "compressed chunks", "rows in compressed chunks", "rows %"]
    table_rows = [(r["table"], f"{r['ratio']:.2f} : 1", f"{r['saved_percent']:.1f}",
                   f"{r['compression_seconds']:.1f}", f"{r['load_seconds_excluded']:.1f}",
                   f"{r['compressed_chunks']} of {r['total_chunks']}",
                   f"{r['rows_in_compressed_chunks']:,} of {cleaned_rows:,}", f"{r['rows_percent']:.2f}")
                  for r in report]
    print(f"\n--- Compression result (baseline {baseline}: {base['total_bytes'] / MB:,.1f} MB total) ---")
    print(format_table(headers, table_rows))

    (RESULTS_DIR / f"{STEP}.json").write_text(json.dumps(
        {"baseline": baseline, "sizes_bytes": sizes, "strategies": report}, indent=2), encoding="utf-8")
    (RESULTS_DIR / f"{STEP}.md").write_text(
        f"# 4.2 Storage and compression cost\n\nBaseline: {baseline}\n\n"
        + format_table(storage_headers, storage, markdown=True) + "\n\n"
        + format_table(headers, table_rows, markdown=True) + "\n", encoding="utf-8")
    finish_log(STEP)


if __name__ == "__main__":
    main()
