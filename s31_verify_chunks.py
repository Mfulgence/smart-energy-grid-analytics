"""Section 3.1 - Verify that the three chunk configurations hold identical data.

The tables are built by sql/03_1_chunk_tables.sql. This program proves they
are comparable before any timing is done:

    * chunk interval of each hypertable (3 hours, 1 day, 7 days)
    * number of chunks and the date range they cover
    * index definitions (same columns, method and sort order on each table)
    * data check per table: row count, distinct meters, first and last
      event_time, sum of power_kw, sum of energy_kwh

Pass rules from the assignment
    rows = 10,643,735 and meters = 4,000 in every table
    earliest and latest event_time identical in every table
    numeric sums differ by at most 0.001 (floating-point rounding)

It is also reused in Section 4.1 for the two compressed tables:
    python s31_verify_chunks.py --tables energy_readings energy_time_compressed energy_meter_compressed --label 4_1_data_check

Run:  python s31_verify_chunks.py
"""

from __future__ import annotations

import argparse

import smart_meter_simulator as sim

from common import RESULTS_DIR, connect, finish_log, format_table, load_named_queries, show_query, start_log

DEFAULT_TABLES = ["energy_readings_3h", "energy_readings", "energy_readings_week"]
TOLERANCE = 0.001


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare hypertable configurations and their data.")
    parser.add_argument("--tables", nargs="+", default=DEFAULT_TABLES)
    parser.add_argument("--label", default="3_1_verify_chunks", help="name of the results file")
    args = parser.parse_args()
    start_log(args.label)

    queries = load_named_queries("03_1_verify.sql")
    expected_rows = sim.dataset_info()["expected_counts"]["unique_readings"]
    expected_meters = sim.dataset_info()["meters"]
    conn = connect()

    # ---- Configuration evidence --------------------------------------------------
    names = {"tables": args.tables}
    show_query(conn, queries["chunk_intervals"], names, title="Chunk interval of each hypertable")
    show_query(conn, queries["chunk_counts"], names, title="Chunk count and time range")
    show_query(conn, queries["indexes"], names, title="Indexes (must match on every table)")

    # ---- Same data everywhere? ---------------------------------------------------
    results = {}
    for table in args.tables:
        headers, rows = show_query(conn, queries["data_check"].format(table=table), title=f"Data check: {table}")
        results[table] = dict(zip(headers, rows[0]))
    conn.close()

    reference = results[args.tables[0]]
    summary, all_ok = [], True
    for table, values in results.items():
        ok = (values["row_count"] == expected_rows
              and values["distinct_meters"] == expected_meters
              and values["earliest_event_time"] == reference["earliest_event_time"]
              and values["latest_event_time"] == reference["latest_event_time"]
              and abs(values["sum_power_kw"] - reference["sum_power_kw"]) <= TOLERANCE
              and abs(values["sum_energy_kwh"] - reference["sum_energy_kwh"]) <= TOLERANCE)
        all_ok &= ok
        summary.append((table, values["row_count"], values["distinct_meters"],
                        values["earliest_event_time"], values["latest_event_time"],
                        f"{values['sum_power_kw']:.6f}", f"{values['sum_energy_kwh']:.6f}",
                        f"{abs(values['sum_power_kw'] - reference['sum_power_kw']):.9f}",
                        f"{abs(values['sum_energy_kwh'] - reference['sum_energy_kwh']):.9f}",
                        "MATCH" if ok else "MISMATCH"))

    headers = ["table", "rows", "meters", "earliest event_time", "latest event_time",
               "sum power_kw", "sum energy_kwh", "power diff", "energy diff", "status"]
    print(f"\n--- Matching data check (required: {expected_rows:,} rows, {expected_meters:,} meters, "
          f"identical dates, sums within {TOLERANCE}) ---")
    print(format_table(headers, summary))
    (RESULTS_DIR / f"{args.label}.md").write_text(
        f"# {args.label}\n\n" + format_table(headers, summary, markdown=True) + "\n", encoding="utf-8")

    print(f"\nRESULT: {'all tables hold the same cleaned data' if all_ok else 'MISMATCH - rebuild the tables before timing'}")
    finish_log(args.label)


if __name__ == "__main__":
    main()
