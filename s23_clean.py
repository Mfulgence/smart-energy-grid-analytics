"""Section 2.3 - Clean duplicates and preserve a consistent benchmark dataset.

The SQL lives in sql/02_3_clean_duplicates.sql. This program runs it in a safe
order and refuses to delete anything if copies of a reading disagree.

Order of work
    1. BEFORE totals: row count and summed energy_kwh.
    2. Find pairs (meter_id, event_time) that occur more than once and compare
       their six other values (received_time, power_kw, voltage_v, current_a,
       frequency_hz, energy_kwh).
    3. If any pair has conflicting values -> print examples and STOP.
    4. Otherwise delete the extra copies inside ONE transaction, keeping one row
       per pair. Missing intervals are left as gaps.
    5. AFTER totals, then verify:
         - row count = expected_counts.unique_readings (10,643,735)
         - no duplicate pairs remain
         - energy fell by exactly the energy of the deleted copies
    6. VACUUM ANALYZE so later benchmarks see accurate statistics.

Repeatable: running it again on the cleaned table deletes 0 rows.

Run:  python s23_clean.py
"""

from __future__ import annotations

import json

import smart_meter_simulator as sim

from common import RESULTS_DIR, cat_text, connect, finish_log, format_table, load_named_queries, show_query, start_log

STEP = "2_3_clean"


def main() -> None:
    start_log(STEP)
    queries = load_named_queries("02_3_clean_duplicates.sql")
    expected_unique = sim.dataset_info()["expected_counts"]["unique_readings"]

    conn = connect()

    # ---- 1. Before -------------------------------------------------------------
    headers, rows = show_query(conn, queries["totals"], title="BEFORE cleaning")
    before = dict(zip(headers, rows[0]))

    # ---- 2. Find and compare duplicates -----------------------------------------
    show_query(conn, queries["find_duplicate_pairs"], title="Find duplicated (meter_id, event_time) pairs")
    headers, rows = show_query(conn, queries["duplicate_summary"], title="Do the copies agree in all six values?")
    summary = dict(zip(headers, rows[0]))
    if summary["duplicated_pairs"]:
        show_query(conn, queries["duplicate_examples"], title="Example duplicated readings (copies are identical)")

    # ---- 3. Stop on conflicts ----------------------------------------------------
    if summary["conflicting_pairs"]:
        show_query(conn, queries["conflict_examples"], title="CONFLICTING copies - investigate these first")
        print("\nSTOPPED: copies with different values exist. Nothing was deleted.")
        conn.close()
        return

    _, rows = show_query(conn, queries["extra_copy_energy"], title="Energy held by the extra copies")
    extra_energy = rows[0][0]

    # ---- 4. Delete inside one transaction ---------------------------------------
    # autocommit is switched off so that the DELETE is all-or-nothing: if the
    # count is not what the diagnosis promised, we roll back and nothing changes.
    conn.autocommit = False
    print(f"\n--- Delete the extra copies ({cat_text()}) ---")
    print(queries["delete_extra_copies"])
    deleted = conn.execute(queries["delete_extra_copies"]).rowcount
    if deleted != summary["extra_copies_to_delete"]:
        conn.rollback()
        print(f"\nROLLED BACK: deleted {deleted:,} but expected {summary['extra_copies_to_delete']:,}.")
        conn.close()
        return
    conn.commit()
    conn.autocommit = True
    print(f"\nDELETE {deleted:,}  -> committed at {cat_text()}")

    # ---- 5. After and verification ----------------------------------------------
    headers, rows = show_query(conn, queries["totals"], title="AFTER cleaning")
    after = dict(zip(headers, rows[0]))
    _, rows = show_query(conn, queries["remaining_duplicates"], title="Duplicate pairs remaining (must be 0)")
    remaining = rows[0][0]

    # ---- 6. Housekeeping ---------------------------------------------------------
    show_query(conn, queries["vacuum_analyze"], title="Reclaim space and refresh statistics")
    conn.close()

    comparison = [
        ("Row count", before["row_count"], after["row_count"], after["row_count"] - before["row_count"]),
        ("Distinct (meter_id, event_time) pairs", before["distinct_pairs"], after["distinct_pairs"],
         after["distinct_pairs"] - before["distinct_pairs"]),
        ("Sum of energy_kwh", round(before["total_energy_kwh"], 6), round(after["total_energy_kwh"], 6),
         round(after["total_energy_kwh"] - before["total_energy_kwh"], 6)),
    ]
    print("\n--- Before and after ---")
    print(format_table(["Measure", "Before", "After", "Change"], comparison))

    energy_drop = before["total_energy_kwh"] - after["total_energy_kwh"]
    checks = [
        ("Rows deleted = extra copies found", deleted == summary["extra_copies_to_delete"]),
        (f"Final row count = expected unique_readings ({expected_unique:,})", after["row_count"] == expected_unique),
        ("Row count = distinct pairs (one row per pair)", after["row_count"] == after["distinct_pairs"]),
        ("No duplicate pairs remain", remaining == 0),
        ("Distinct pairs unchanged (no reading lost, gaps kept as gaps)", before["distinct_pairs"] == after["distinct_pairs"]),
        (f"Energy fell by the extra copies' energy ({extra_energy:,.6f} kWh)", abs(energy_drop - extra_energy) < 0.001),
    ]
    print("\n--- Verification ---")
    print(format_table(["Check", "Result"], [(name, "OK" if ok else "FAILED") for name, ok in checks]))

    print("""
Why missing readings are NOT turned into zero consumption
    A missing reading means the utility did not receive a measurement. It does
    not mean the customer used 0 kWh. Writing zeros would (1) understate energy
    and bias every total, average and forecast downward, (2) create false
    "unusual drop" anomalies, and (3) hide the data-quality problem, because
    completeness would wrongly look like 100%. Keeping the gap keeps the truth:
    "unknown" stays unknown and completeness can still be measured (5.3).""")

    (RESULTS_DIR / f"{STEP}.json").write_text(json.dumps(
        {"before": before, "after": after, "deleted": deleted, "extra_copy_energy_kwh": extra_energy,
         "duplicate_pairs_remaining": remaining}, indent=2, default=str), encoding="utf-8")
    (RESULTS_DIR / f"{STEP}.md").write_text(
        "# 2.3 Cleaning\n\n" + format_table(["Measure", "Before", "After", "Change"], comparison, markdown=True)
        + "\n\n" + format_table(["Check", "Result"], [(n, "OK" if ok else "FAILED") for n, ok in checks], markdown=True)
        + "\n", encoding="utf-8")

    print(f"RESULT: {'cleaned dataset verified - use it for every later section' if all(ok for _, ok in checks) else 'verification FAILED'}")
    finish_log(STEP)


if __name__ == "__main__":
    main()
