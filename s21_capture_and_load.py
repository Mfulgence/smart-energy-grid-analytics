"""Section 2.1 - Capture the complete stream and load it into energy_readings.

Chosen ingestion route:  generator -> CSV file -> PostgreSQL COPY (bulk load)

Why this route
    MQTT was proven with the 2,000-message pilot. For 10.7 million historical
    rows a bulk load is the sensible tool: COPY sends rows to the server as one
    continuous stream instead of one INSERT round trip per row, and the CSV
    file gives an independent row count to compare with the generator and the
    database. The pilot rows stay untouched in energy_live.

Steps performed
    1. dataset_info()       -> print the expected counts.
    2. PHASE A (generate)   -> walk a fresh iter_readings() iterator and write
                               rows to data/energy_readings.csv in batches.
                               Nothing is ever collected into one giant list.
    3. Count the data rows of the CSV file (an independent check).
    4. PHASE B (load)       -> empty energy_readings, then COPY the file in
                               batches of 500,000 rows, committing each batch.
    5. Compare three numbers that must agree before cleaning:
           dictionaries consumed = CSV data rows = committed table rows
           = expected_counts.emitted_readings (10,696,848)
    6. Database checks: distinct meters, first/last event_time, table sizes.

Timings reported (all for this route only)
    file generation seconds   start of generation -> CSV file closed
    database loading seconds  first COPY -> final commit
    total elapsed seconds     start of generation -> final commit

Run:  python s21_capture_and_load.py
      python s21_capture_and_load.py --reuse-csv     (skip phase A if the file exists)
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import time
from operator import itemgetter

import smart_meter_simulator as sim            # the supplied, unchanged generator

from common import DATA_DIR, RESULTS_DIR, cat_text, connect, finish_log, format_table, show_query, start_log

STEP = "2_1_capture_and_load"
CSV_PATH = DATA_DIR / "energy_readings.csv"
WRITE_BATCH = 100_000        # rows buffered in memory before they are written to the file
LOAD_BATCH = 500_000         # rows sent to PostgreSQL per COPY + COMMIT
PROGRESS_EVERY = 500_000     # print a progress line this often


def generate_csv(fields: list[str]) -> tuple[int, float, str, str]:
    """PHASE A. Stream the generator into a CSV file. Returns
    (dictionaries consumed, seconds, start text, end text)."""
    pick = itemgetter(*fields)        # fast way to pull the 8 values in a fixed column order
    consumed = 0
    started_text, started = cat_text(), time.perf_counter()
    print(f"\nPHASE A  generating {CSV_PATH.name}   started {started_text}")
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(fields)                               # header line
        readings = sim.iter_readings()                        # a FRESH iterator
        while True:
            # islice takes the next WRITE_BATCH dictionaries without ever
            # holding the full dataset: memory use stays flat.
            batch = [pick(reading) for reading in itertools.islice(readings, WRITE_BATCH)]
            if not batch:
                break                                         # iterator exhausted
            writer.writerows(batch)
            consumed += len(batch)
            if consumed % PROGRESS_EVERY == 0:
                rate = consumed / (time.perf_counter() - started)
                print(f"  generated {consumed:>12,} dictionaries   {rate:>10,.0f} per second")
    seconds = time.perf_counter() - started
    ended_text = cat_text()
    print(f"PHASE A  finished {ended_text}: {consumed:,} dictionaries consumed in {seconds:,.1f} s "
          f"({CSV_PATH.stat().st_size / 1024**2:,.0f} MB)")
    return consumed, seconds, started_text, ended_text


def count_csv_rows() -> int:
    """Count data rows in the file (total lines minus the header line)."""
    lines = 0
    with open(CSV_PATH, "rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            lines += block.count(b"\n")
    return lines - 1


def load_csv(fields: list[str]) -> tuple[int, float, str, str]:
    """PHASE B. COPY the CSV into energy_readings in committed batches.
    Returns (rows sent, seconds, start text, end text)."""
    conn = connect(autocommit=False)
    # 2.1 requires an initially empty table. TRUNCATE also makes a re-run safe.
    conn.execute("TRUNCATE energy_readings")
    conn.commit()
    print("\nenergy_readings emptied (TRUNCATE) before loading.")

    copy_sql = f"COPY energy_readings ({', '.join(fields)}) FROM STDIN WITH (FORMAT csv)"
    sent = 0
    started_text, started = cat_text(), time.perf_counter()   # first database write starts here
    print(f"PHASE B  loading with COPY   started {started_text}")
    with open(CSV_PATH, "r", encoding="utf-8", newline="") as handle:
        handle.readline()                                     # skip the header line
        while True:
            lines = list(itertools.islice(handle, LOAD_BATCH))  # next batch of text lines
            if not lines:
                break
            with conn.cursor() as cur:
                with cur.copy(copy_sql) as copy:              # one COPY per batch
                    copy.write("".join(lines))
            conn.commit()                                     # batch is now durable
            sent += len(lines)
            rate = sent / (time.perf_counter() - started)
            print(f"  committed {sent:>12,} rows   {rate:>10,.0f} per second")
    seconds = time.perf_counter() - started                   # ... and ends at the final commit
    ended_text = cat_text()
    conn.close()
    print(f"PHASE B  finished {ended_text}: {sent:,} rows committed in {seconds:,.1f} s")
    return sent, seconds, started_text, ended_text


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the full dataset as CSV and bulk load it.")
    parser.add_argument("--reuse-csv", action="store_true",
                        help="skip generation when data/energy_readings.csv already exists")
    args = parser.parse_args()
    start_log(STEP)

    # ---- 1. Expected counts from the generator's own contract ----------------
    info = sim.dataset_info()
    fields = info["reading_fields"]
    expected = info["expected_counts"]
    print("dataset_info():")
    print(f"  period            {info['start_inclusive']}  to  {info['end_exclusive']} (exclusive)")
    print(f"  meters            {info['meters']:,}")
    print(f"  planned_readings  {info['planned_readings']:,}")
    for name, value in expected.items():
        print(f"  {name:<24}{value:>12,}")

    overall_start_text, overall_start = cat_text(), time.perf_counter()

    # ---- 2. Phase A: generate ------------------------------------------------
    if args.reuse_csv and CSV_PATH.exists():
        print(f"\nReusing existing {CSV_PATH} (generation skipped, so no generation time is reported).")
        consumed, generation_seconds = None, None
    else:
        consumed, generation_seconds, _, _ = generate_csv(fields)

    # ---- 3. Independent CSV row count -----------------------------------------
    csv_rows = count_csv_rows()
    print(f"\nCSV data rows counted in the file: {csv_rows:,}")
    if consumed is None:
        consumed = csv_rows

    # ---- 4. Phase B: load ------------------------------------------------------
    sent, load_seconds, _, load_end_text = load_csv(fields)
    total_seconds = time.perf_counter() - overall_start

    # ---- 5. The three-way agreement check -------------------------------------
    conn = connect()
    committed = conn.execute("SELECT count(*) FROM energy_readings").fetchone()[0]
    emitted = expected["emitted_readings"]
    check = [
        ("Dictionaries consumed from iter_readings()", consumed, emitted, consumed == emitted),
        ("CSV data rows", csv_rows, emitted, csv_rows == emitted),
        ("Rows committed in energy_readings", committed, emitted, committed == emitted),
    ]
    print("\n--- Count agreement (all must equal expected_counts.emitted_readings) ---")
    count_table = [(name, got, want, "OK" if ok else "MISMATCH") for name, got, want, ok in check]
    print(format_table(["Count", "Measured", "Expected", "Status"], count_table))

    timing_table = [
        ("Ingestion route", "generator -> CSV file -> COPY into energy_readings"),
        ("File generation seconds", f"{generation_seconds:,.1f}" if generation_seconds else "not measured (CSV reused)"),
        ("Database loading seconds (first COPY to final commit)", f"{load_seconds:,.1f}"),
        ("Total elapsed seconds (start of generation to final commit)",
         f"{total_seconds:,.1f}" if generation_seconds else "not measured (CSV reused)"),
        ("Started (CAT)", overall_start_text),
        ("Final commit (CAT)", load_end_text),
    ]
    print("\n--- Timings ---")
    print(format_table(["Measure", "Value"], timing_table))

    # ---- 6. Database checks (screenshot these) --------------------------------
    show_query(conn, """
SELECT count(*)                 AS row_count,
       count(DISTINCT meter_id) AS distinct_meters,
       min(event_time)          AS earliest_event_time,
       max(event_time)          AS latest_event_time
FROM energy_readings""", title="Row count, distinct meters, first and last event_time")

    # hypertable_detailed_size() adds up every chunk of the hypertable.
    # "table" = row data, "index" = all indexes, "toast" = out-of-line storage.
    show_query(conn, """
SELECT pg_size_pretty(table_bytes)                 AS table_data,
       pg_size_pretty(index_bytes)                 AS indexes,
       pg_size_pretty(coalesce(toast_bytes, 0))    AS toast,
       pg_size_pretty(total_bytes)                 AS combined_total,
       round(table_bytes / 1024.0 / 1024.0, 1)     AS table_mb,
       round(index_bytes / 1024.0 / 1024.0, 1)     AS index_mb,
       round(total_bytes / 1024.0 / 1024.0, 1)     AS total_mb
FROM hypertable_detailed_size('energy_readings')""", title="Size of energy_readings including all chunks")

    show_query(conn, """
SELECT count(*) AS chunk_count, min(range_start) AS first_chunk_start, max(range_end) AS last_chunk_end
FROM timescaledb_information.chunks
WHERE hypertable_name = 'energy_readings'""", title="Chunks created by the load")
    conn.close()

    # ---- Save a machine-readable record of this run ---------------------------
    record = {"route": "CSV + COPY", "consumed": consumed, "csv_rows": csv_rows, "committed": committed,
              "expected_emitted": emitted, "generation_seconds": generation_seconds,
              "load_seconds": load_seconds, "total_seconds": total_seconds if generation_seconds else None,
              "started": overall_start_text, "final_commit": load_end_text}
    (RESULTS_DIR / f"{STEP}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    (RESULTS_DIR / f"{STEP}.md").write_text(
        "# 2.1 Capture and load\n\n"
        + format_table(["Count", "Measured", "Expected", "Status"], count_table, markdown=True) + "\n\n"
        + format_table(["Measure", "Value"], timing_table, markdown=True) + "\n", encoding="utf-8")

    ok = all(row[3] for row in check)
    print(f"\nRESULT: {'all three counts agree with emitted_readings - safe to continue to 2.2' if ok else 'COUNTS DISAGREE - do not clean yet, investigate'}")
    finish_log(STEP)


if __name__ == "__main__":
    main()
