"""Section 5.3 - Assess reporting quality.

Part 1  Completeness, for the whole network and for each region
            planned      = registered meters x 28 days x 96 readings per day
            completeness = 100 x observed unique (meter, event_time) pairs / planned

Part 2  What would a report produced at midnight have shown for 21 September?
            on-time total = energy of readings with event_time on 21 Sept whose
                            received_time is at or before 22 Sept 00:00 CAT
            final total   = energy of all readings for 21 Sept, any arrival time
            difference    = final - on-time, in kWh and as % of the final total

Run:  python s53_reporting_quality.py
"""

from __future__ import annotations

from common import RESULTS_DIR, connect, finish_log, format_table, load_named_queries, show_query, start_log

STEP = "5_3_reporting_quality"


def main() -> None:
    start_log(STEP)
    queries = load_named_queries("05_analysis.sql")
    conn = connect()
    headers_n, network = show_query(conn, queries["completeness_network"], title="Completeness: whole network")
    headers_r, regions = show_query(conn, queries["completeness_by_region"], title="Completeness: each region")
    headers_d, day = show_query(conn, queries["day21_on_time_vs_final"],
                                title="21 September: arrived by 22 Sept 00:00 vs all arrivals")
    conn.close()

    on_time, final, on_time_rows, final_rows, planned_rows = day[0]
    difference = final - on_time
    summary = [
        ("Energy from readings arrived by 22 Sept 00:00 CAT (kWh)", f"{on_time:,.3f}"),
        ("Energy from all arrivals = final total (kWh)", f"{final:,.3f}"),
        ("Difference (kWh)", f"{difference:,.3f}"),
        ("Difference as % of the final total", f"{100 * difference / final:.4f} %"),
        ("Readings arrived by midnight / all arrivals", f"{on_time_rows:,} / {final_rows:,}"),
        ("Late readings for this day", f"{final_rows - on_time_rows:,}"),
        ("Planned readings for the day (4,000 x 96)", f"{planned_rows:,}"),
        ("Readings that never arrived (missing)", f"{planned_rows - final_rows:,} "
                                                  f"({100 * (planned_rows - final_rows) / planned_rows:.3f} % of planned)"),
    ]
    print("\n--- 21 September summary ---")
    print(format_table(["Measure", "Value"], summary))
    print("""
How to read this
    Delayed readings: they exist, but arrive up to 3 hours after their interval.
        A total computed at midnight misses the late ones for the last hours of
        the day, so the early figure is too LOW and is corrected once they arrive.
    Missing readings: they never arrive. Even the final total is a slight
        UNDERCOUNT of true consumption, and no amount of waiting fixes it.""")

    (RESULTS_DIR / f"{STEP}.md").write_text(
        "# 5.3 Reporting quality\n\n" + format_table(headers_n, network, markdown=True) + "\n\n"
        + format_table(headers_r, regions, markdown=True) + "\n\n"
        + format_table(["Measure", "Value"], summary, markdown=True) + "\n", encoding="utf-8")
    finish_log(STEP)


if __name__ == "__main__":
    main()
