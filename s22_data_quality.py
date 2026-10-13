"""Section 2.2 - Investigate data quality before cleaning.

The diagnostic SQL lives in sql/02_2_data_quality.sql. This program runs those
queries one by one (printing each query and its result for the screenshots),
then calculates the four percentages and compares every measured count with
the reference values returned by dataset_info().

Formulas (exactly as given in the assignment)
    missing %      = 100 * missing pairs           / planned readings
    duplicate %    = 100 * extra copies            / observed unique pairs
    delayed %      = 100 * delayed unique readings / observed unique pairs
    completeness % = 100 * observed unique pairs   / planned readings

Consistency checks
    unique readings  + extra copies    = emitted readings
    planned readings - unique readings = missing readings

Run:  python s22_data_quality.py      (run it BEFORE s23_clean.py)
"""

from __future__ import annotations

import smart_meter_simulator as sim

from common import RESULTS_DIR, connect, finish_log, format_table, load_named_queries, show_query, start_log

STEP = "2_2_data_quality"


def main() -> None:
    start_log(STEP)
    queries = load_named_queries("02_2_data_quality.sql")
    info = sim.dataset_info()
    reference = {"planned_readings": info["planned_readings"], **info["expected_counts"]}

    conn = connect()
    # Group the raw rows once into a temporary table of observed pairs.
    show_query(conn, queries["build_observed_pairs"], title="Build the list of observed (meter_id, event_time) pairs")
    conn.execute(queries["analyze_observed_pairs"])

    headers, rows = show_query(conn, queries["counts"], title="Emitted, unique, duplicate and delayed counts")
    measured = dict(zip(headers, rows[0]))

    headers, rows = show_query(conn, queries["missing_from_grid"], title="Missing pairs from the planned grid")
    measured.update(dict(zip(headers, rows[0])))

    show_query(conn, queries["arrival_delay_profile"], title="Arrival delay profile (delayed = 30 to 180 minutes)")
    _, top5 = show_query(conn, queries["top5_missing_meters"], title="Five meters with the most missing readings")
    conn.close()

    # ---- Percentages -----------------------------------------------------------
    planned = measured["planned_readings"]
    unique = measured["unique_readings"]
    percentages = [
        ("Missing percentage", "100 * missing / planned", 100 * measured["missing_readings"] / planned),
        ("Duplicate percentage", "100 * extra copies / unique", 100 * measured["duplicate_readings"] / unique),
        ("Delayed percentage", "100 * delayed unique / unique", 100 * measured["delayed_unique_readings"] / unique),
        ("Completeness", "100 * unique / planned", 100 * unique / planned),
    ]
    print("\n--- Percentages ---")
    percent_table = [(name, formula, f"{value:.4f} %") for name, formula, value in percentages]
    print(format_table(["Measure", "Formula", "Value"], percent_table))

    # ---- Compare with the reference table ---------------------------------------
    print("\n--- Measured counts compared with dataset_info() ---")
    compare = [(name, measured[name], reference[name], measured[name] - reference[name],
                "OK" if measured[name] == reference[name] else "DIFFERENT")
               for name in ("planned_readings", "emitted_readings", "unique_readings",
                            "duplicate_readings", "delayed_unique_readings", "missing_readings")]
    print(format_table(["Entry", "Measured", "Expected", "Difference", "Status"], compare))

    # ---- The two identities the assignment asks us to check ---------------------
    identity_1 = unique + measured["duplicate_readings"] == measured["emitted_readings"]
    identity_2 = planned - unique == measured["missing_readings"]
    print("\n--- Consistency checks ---")
    print(f"unique + extra copies = emitted : {unique:,} + {measured['duplicate_readings']:,} = "
          f"{unique + measured['duplicate_readings']:,}  vs  {measured['emitted_readings']:,}  -> "
          f"{'OK' if identity_1 else 'FAILED'}")
    print(f"planned - unique = missing      : {planned:,} - {unique:,} = {planned - unique:,}  vs  "
          f"{measured['missing_readings']:,}  -> {'OK' if identity_2 else 'FAILED'}")

    (RESULTS_DIR / f"{STEP}.md").write_text(
        "# 2.2 Data quality (before cleaning)\n\n"
        + format_table(["Entry", "Measured", "Expected", "Difference", "Status"], compare, markdown=True) + "\n\n"
        + format_table(["Measure", "Formula", "Value"], percent_table, markdown=True) + "\n\n"
        + "Five meters with the most missing readings\n\n"
        + format_table(["meter_id", "region", "customer_type", "observed", "missing", "missing %"], top5, markdown=True)
        + "\n", encoding="utf-8")

    all_ok = identity_1 and identity_2 and all(row[4] == "OK" for row in compare)
    print(f"\nRESULT: {'every measured count matches the reference - continue to 2.3' if all_ok else 'differences found - investigate before cleaning'}")
    finish_log(STEP)


if __name__ == "__main__":
    main()
