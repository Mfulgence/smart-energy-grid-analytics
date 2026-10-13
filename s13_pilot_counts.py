"""Section 1.3 (steps 3-4) - Put the four pilot counts in one table.

Run this AFTER both s13_subscriber.py and s13_publisher.py have finished.

The four stages and where each count comes from
    1. dictionaries taken from the generator   <- results/1_3_publisher_counts.json
    2. messages acknowledged by the broker     <- results/1_3_publisher_counts.json
    3. messages received by the subscriber     <- results/1_3_subscriber_counts.json
    4. rows committed in energy_live           <- SELECT count(*) (queried now)

The target is 2,000 at every stage. Deliberate generator duplicates are
separate messages and separate rows, so they are counted, not removed.

Run:  python s13_pilot_counts.py
"""

from __future__ import annotations

import json

from common import RESULTS_DIR, connect, finish_log, format_table, show_query, start_log

STEP = "1_3_pilot_counts"
TARGET = 2000


def main() -> None:
    start_log(STEP)
    publisher = json.loads((RESULTS_DIR / "1_3_publisher_counts.json").read_text(encoding="utf-8"))
    subscriber = json.loads((RESULTS_DIR / "1_3_subscriber_counts.json").read_text(encoding="utf-8"))

    conn = connect()
    _, rows = show_query(conn, "SELECT count(*) AS rows_in_energy_live FROM energy_live",
                         title="Stored row count (after all inserts were committed)")
    stored = rows[0][0]

    stages = [
        ("1. Dictionaries taken from generator", publisher["taken_from_generator"]),
        ("2. Messages acknowledged by broker (PUBACK)", publisher["acknowledged_by_broker"]),
        ("3. Messages received by subscriber", subscriber["received"]),
        ("4. Rows committed in energy_live", stored),
    ]
    table = [(name, value, TARGET, value - TARGET, "OK" if value == TARGET else "DIFFERENT")
             for name, value in stages]
    headers = ["Stage", "Count", "Target", "Difference", "Status"]
    print("\n--- The four pilot counts ---")
    print(format_table(headers, table))

    # Extra detail that explains any difference.
    print("\nDiagnostics recorded by the programs")
    print(f"  publisher  unacknowledged messages : {publisher['unacknowledged']}")
    print(f"  subscriber redelivered (DUP)       : {subscriber['redelivered']}")
    print(f"  subscriber parse errors            : {subscriber['parse_errors']}")
    print(f"  subscriber failed inserts          : {subscriber['insert_errors']}")
    print("  (details, if any, are in logs/publisher.log and logs/subscriber.log)")

    # The first 2,000 dictionaries already contain a few deliberate duplicates.
    # They must be present as separate rows, which this query makes visible.
    show_query(conn, """
SELECT count(*)                                         AS rows,
       count(DISTINCT (meter_id, event_time))           AS distinct_meter_time_pairs,
       count(*) - count(DISTINCT (meter_id, event_time)) AS generator_duplicate_rows,
       count(DISTINCT meter_id)                         AS meters,
       min(event_time)                                  AS first_event,
       max(event_time)                                  AS last_event
FROM energy_live""", title="Duplicates are kept as separate rows")
    show_query(conn, "SELECT * FROM energy_live ORDER BY event_time, meter_id LIMIT 5",
               title="Sample stored rows")
    conn.close()

    all_ok = all(value == TARGET for _, value in stages)
    (RESULTS_DIR / f"{STEP}.md").write_text(
        "# 1.3 Pilot counts\n\n" + format_table(headers, table, markdown=True) + "\n", encoding="utf-8")
    print(f"\nRESULT: {'all four counts equal 2,000 - pilot passed' if all_ok else 'counts differ - read the logs, fix, repeat the pilot'}")
    finish_log(STEP)


if __name__ == "__main__":
    main()
