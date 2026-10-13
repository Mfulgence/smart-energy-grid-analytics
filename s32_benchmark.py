"""Sections 3.2 and 4.3 - Time the five workloads on several hypertables.

The five queries live in sql/03_2_workloads.sql. Only the table name changes.

Procedure (identical for every query and table)
    1. ANALYZE every table once so the planner has current statistics.
    2. For each query, for each table:
           1 warm-up execution   (not reported; it loads data into the cache)
           5 measured executions
       Everything runs sequentially on one connection.
    3. Each duration is measured in this client with time.perf_counter():
       the clock starts immediately before the statement is submitted and
       stops after the LAST result row has been received and fetched.
    4. Every execution is recorded with its CAT start time, CAT end time,
       duration and machine identifier in results/<label>_timings.csv.
    5. Results are checked for correctness: each table must return the same
       rows as the reference table (numbers may differ by at most 0.001).
    6. Median, minimum and maximum are reported per query and table, plus the
       session seconds from the first warm-up to the last measured result.
    7. One EXPLAIN (ANALYZE, BUFFERS) plan per configuration is printed and
       all plans are saved to results/<label>_plans.txt.

These are WARM-CACHE measurements: a warm-up always precedes timing, and
PostgreSQL is not restarted and caches are not cleared between runs.

Before running: close other programs, stop loaders, and pause background jobs
    python jobs.py pause

Section 3.2:
    python s32_benchmark.py
Section 4.3 (compressed tables, checked against the uncompressed baseline):
    python s32_benchmark.py --label 4_3 --tables energy_time_compressed energy_meter_compressed --reference energy_readings
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import re
import statistics
import time

import psycopg

from common import RESULTS_DIR, cat_text, connect, finish_log, format_table, load_named_queries, setting, start_log

DEFAULT_TABLES = ["energy_readings_3h", "energy_readings", "energy_readings_week"]
QUERY_NAMES = ["Q1", "Q2", "Q3", "Q4", "Q5"]
TOLERANCE = 0.001
CLIENT = f"Python {platform.python_version()} + psycopg {psycopg.__version__} (s32_benchmark.py)"
TIMER = "time.perf_counter() around execute()+fetchall()"


def timed_run(conn, sql: str):
    """Execute one statement and return (rows, milliseconds, start, end).

    The timer covers statement submission until the last row is in client
    memory: execute() sends the query and receives the complete result from
    the server, fetchall() hands the rows to Python.
    """
    start_wall = cat_text()
    started = time.perf_counter()
    rows = conn.execute(sql).fetchall()
    elapsed_ms = (time.perf_counter() - started) * 1000
    return rows, elapsed_ms, start_wall, cat_text()


def same_results(rows_a, rows_b) -> tuple[bool, float]:
    """Compare two result sets cell by cell. Floats may differ by TOLERANCE.
    Returns (match, largest numeric difference seen)."""
    if len(rows_a) != len(rows_b):
        return False, float("inf")
    largest = 0.0
    for row_a, row_b in zip(rows_a, rows_b):
        for a, b in zip(row_a, row_b):
            if isinstance(a, float) or isinstance(b, float):
                difference = abs(float(a) - float(b))
                largest = max(largest, difference)
                if difference > TOLERANCE:
                    return False, largest
            elif a != b:                       # keys, timestamps and integer counts must be identical
                return False, float("inf")
    return True, largest


def explain(conn, sql: str) -> str:
    """Return the actual execution plan with timing and buffer statistics."""
    rows = conn.execute("EXPLAIN (ANALYZE, BUFFERS) " + sql).fetchall()
    return "\n".join(row[0] for row in rows)


def chunks_in_plan(plan: str) -> int:
    """Count the distinct chunks a plan touched (chunk tables are named
    _hyper_<hypertable>_<n>_chunk). Used as evidence for chunk exclusion."""
    return len(set(re.findall(r"_hyper_\d+_\d+_chunk", plan)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Q1-Q5 on several hypertables.")
    parser.add_argument("--tables", nargs="+", default=DEFAULT_TABLES)
    parser.add_argument("--label", default="3_2", help="prefix of the result files (3_2 or 4_3)")
    parser.add_argument("--reference", help="table whose results define 'correct' (default: first table)")
    parser.add_argument("--runs", type=int, default=5, help="measured executions per query and table")
    parser.add_argument("--plan-query", default="Q1", choices=QUERY_NAMES,
                        help="which query's plan to print on screen (all are saved to file)")
    args = parser.parse_args()
    label = args.label
    start_log(f"{label}_benchmark")

    queries = load_named_queries("03_2_workloads.sql")
    machine = setting("MACHINE_ID")
    conn = connect()

    # ---- Record the measurement conditions ---------------------------------------
    print(f"Client          : {CLIENT}")
    print(f"Timing tool     : {TIMER}")
    print(f"Machine         : {machine}")
    print(f"Cache state     : WARM (1 warm-up before {args.runs} measured runs, no restart, caches not cleared)")
    for name in ("shared_buffers", "work_mem", "max_parallel_workers_per_gather", "jit"):
        print(f"{name:<16}: {conn.execute(f'SHOW {name}').fetchone()[0]}")

    # Background jobs that are still scheduled could run in the middle of a
    # measurement. Warn loudly so the run can be repeated cleanly.
    active_jobs = conn.execute(
        "SELECT job_id, proc_name, hypertable_name FROM timescaledb_information.jobs "
        "WHERE job_id >= 1000 AND scheduled").fetchall()
    if active_jobs:
        print(f"WARNING: {len(active_jobs)} background job(s) still scheduled: {active_jobs}")
        print("         Run 'python jobs.py pause' first, then repeat this benchmark.")
    others = conn.execute(
        "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
        "AND pid <> pg_backend_pid() AND state = 'active' AND backend_type = 'client backend'").fetchone()[0]
    if others:
        print(f"WARNING: {others} other active database session(s). Close competing workloads.")

    # ---- 1. Fresh statistics --------------------------------------------------------
    for table in dict.fromkeys(args.tables + ([args.reference] if args.reference else [])):
        conn.execute(f"ANALYZE {table}")
        print(f"ANALYZE {table}  done")

    # ---- Reference results for the correctness check ---------------------------------
    reference_table = args.reference or args.tables[0]
    reference_rows = {}
    if reference_table not in args.tables:      # e.g. 4.3: compare against the baseline
        for name in QUERY_NAMES:
            reference_rows[name] = conn.execute(queries[name].format(table=reference_table)).fetchall()
        print(f"Reference results taken from {reference_table} (not timed).")

    # ---- 2-4. Timed executions -------------------------------------------------------
    records, summary, correctness = [], [], []
    session_start_text, session_start = cat_text(), time.perf_counter()
    for name in QUERY_NAMES:
        for table in args.tables:
            sql = queries[name].format(table=table)        # the ONLY change is the table
            durations = []
            for run in range(0, args.runs + 1):            # run 0 is the warm-up
                rows, ms, start_text, end_text = timed_run(conn, sql)
                kind = "warm-up" if run == 0 else "measured"
                records.append({"label": label, "query": name, "table": table, "run_type": kind,
                                "run": run, "start_cat": start_text, "end_cat": end_text,
                                "duration_ms": round(ms, 3), "rows": len(rows),
                                "machine": machine, "client": CLIENT})
                if run:
                    durations.append(ms)
            # Correctness: compare the last result with the reference result.
            if name not in reference_rows:
                reference_rows[name] = rows                 # first table defines the reference
            match, largest = same_results(reference_rows[name], rows)
            correctness.append((name, table, len(rows), "MATCH" if match else "MISMATCH",
                                f"{largest:.9f}" if largest != float("inf") else "n/a"))
            summary.append({"query": name, "table": table, "median_ms": statistics.median(durations),
                            "min_ms": min(durations), "max_ms": max(durations), "rows": len(rows)})
            print(f"  {name} on {table:<26} median {statistics.median(durations):>10,.1f} ms   "
                  f"min {min(durations):>10,.1f}   max {max(durations):>10,.1f}   "
                  f"{'results match' if match else 'RESULTS DIFFER'}")
    session_seconds = time.perf_counter() - session_start
    session_end_text = cat_text()

    # ---- 5. Correctness table ---------------------------------------------------------
    print(f"\n--- Result check against {reference_table} (numeric tolerance {TOLERANCE}) ---")
    print(format_table(["query", "table", "rows", "status", "largest numeric difference"], correctness))

    # ---- 6. Timing comparison -----------------------------------------------------------
    print(f"\n--- WARM-CACHE timing comparison, milliseconds ({args.runs} measured runs after 1 warm-up) ---")
    timing_rows = [(s["query"], s["table"], f"{s['median_ms']:,.1f}", f"{s['min_ms']:,.1f}", f"{s['max_ms']:,.1f}")
                   for s in summary]
    print(format_table(["query", "table", "median ms", "min ms", "max ms"], timing_rows))

    # Median per table side by side, and the fastest table for each query.
    pivot_rows = []
    for name in QUERY_NAMES:
        medians = {s["table"]: s["median_ms"] for s in summary if s["query"] == name}
        fastest = min(medians, key=medians.get)
        slowest = max(medians, key=medians.get)
        # "x times" comparison of medians, ready to quote in the explanation (3.3).
        pivot_rows.append([name] + [f"{medians[t]:,.1f}" for t in args.tables]
                          + [fastest, f"{medians[slowest] / medians[fastest]:.2f} x faster than {slowest}"])
    print("\n--- Median ms per table (side by side) ---")
    print(format_table(["query"] + args.tables + ["fastest", "fastest vs slowest"], pivot_rows))

    print(f"\nSession: first warm-up submitted {session_start_text}")
    print(f"         last measured result    {session_end_text}")
    print(f"         session seconds         {session_seconds:,.1f}")

    # ---- 7. Execution plans (not part of the timed session) ------------------------------
    plan_text, chunk_rows = [], []
    for name in QUERY_NAMES:
        counts = []
        for table in args.tables:
            plan = explain(conn, queries[name].format(table=table))
            counts.append(chunks_in_plan(plan))
            plan_text.append(f"===== {name} on {table}   ({cat_text()}) =====\n{plan}\n")
            if name == args.plan_query:
                print(f"\n--- EXPLAIN (ANALYZE, BUFFERS) {name} on {table} ---")
                print(queries[name].format(table=table))
                print()
                print(plan)
        chunk_rows.append([name] + counts)
    (RESULTS_DIR / f"{label}_plans.txt").write_text("\n".join(plan_text), encoding="utf-8")
    print("\n--- Chunks touched by each plan (evidence of chunk exclusion) ---")
    print(format_table(["query"] + args.tables, chunk_rows))
    conn.close()

    # ---- Save the recorded timings ---------------------------------------------------------
    with open(RESULTS_DIR / f"{label}_timings.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)
    (RESULTS_DIR / f"{label}_summary.json").write_text(json.dumps({
        "label": label, "client": CLIENT, "timer": TIMER, "machine": machine, "cache": "warm",
        "tables": args.tables, "reference": reference_table, "runs": args.runs,
        "session_start": session_start_text, "session_end": session_end_text,
        "session_seconds": session_seconds, "summary": summary,
        "chunks_touched": {row[0]: dict(zip(args.tables, row[1:])) for row in chunk_rows},
        "all_results_match": all(row[3] == "MATCH" for row in correctness)}, indent=2), encoding="utf-8")
    (RESULTS_DIR / f"{label}_summary.md").write_text(
        f"# {label} warm-cache timing comparison (ms)\n\nClient: {CLIENT}  \nTimer: {TIMER}  \n"
        f"Machine: {machine}  \nSession: {session_start_text} to {session_end_text} = {session_seconds:,.1f} s\n\n"
        + format_table(["query", "table", "median ms", "min ms", "max ms"], timing_rows, markdown=True) + "\n\n"
        + format_table(["query"] + args.tables + ["fastest", "fastest vs slowest"], pivot_rows, markdown=True) + "\n\n"
        + "Chunks touched\n\n" + format_table(["query"] + args.tables, chunk_rows, markdown=True) + "\n",
        encoding="utf-8")
    print(f"\nSaved: results/{label}_timings.csv (every run), results/{label}_summary.md, results/{label}_plans.txt")
    finish_log(f"{label}_benchmark")


if __name__ == "__main__":
    main()
