"""Section 1.2 (step 4) - Load the 4,000 meter metadata rows into "meters".

The tables themselves are created by sql/01_2_create_tables.sql.
This program does exactly what the assignment describes:
  1. import the unchanged generator module,
  2. call meter_metadata() to get a list of 4,000 dictionaries,
  3. insert each dictionary as one row of the meters table,
  4. verify that the table now holds 4,000 rows.

Run:  python s12_load_meters.py
"""

from __future__ import annotations

import smart_meter_simulator as sim            # the supplied, unchanged generator

from common import connect, finish_log, show_query, start_log

STEP = "1_2_load_meters"

# %(name)s placeholders are filled from each dictionary by the driver. Values
# are sent separately from the SQL text, so there is no string concatenation.
# ON CONFLICT makes the script repeatable: running it twice does not fail on
# the primary key and does not create duplicates.
INSERT_SQL = """
INSERT INTO meters (meter_id, region, customer_type, base_power_kw, power_factor)
VALUES (%(meter_id)s, %(region)s, %(customer_type)s, %(base_power_kw)s, %(power_factor)s)
ON CONFLICT (meter_id) DO UPDATE
   SET region        = EXCLUDED.region,
       customer_type = EXCLUDED.customer_type,
       base_power_kw = EXCLUDED.base_power_kw,
       power_factor  = EXCLUDED.power_factor
"""


def main() -> None:
    start_log(STEP)

    meters = sim.meter_metadata()              # list of 4,000 dictionaries
    print(f"meter_metadata() returned {len(meters):,} dictionaries")
    print(f"First dictionary: {meters[0]}")

    # One transaction for all rows: either all 4,000 are stored or none are.
    with connect(autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.executemany(INSERT_SQL, meters)   # one INSERT per dictionary
        conn.commit()
        print(f"Inserted/updated {len(meters):,} rows and committed.")

    # ---- Verification (screenshot these results) ----------------------------
    conn = connect()
    _, rows = show_query(conn, "SELECT count(*) AS meter_rows FROM meters",
                         title="Row count must be 4,000")
    show_query(conn, """
SELECT region, count(*) AS meters
FROM meters
GROUP BY region
ORDER BY length(region), region""", title="Meters per region (expect 400 each)")
    show_query(conn, """
SELECT customer_type, count(*) AS meters,
       round(min(base_power_kw)::numeric, 3) AS min_base_kw,
       round(max(base_power_kw)::numeric, 3) AS max_base_kw
FROM meters
GROUP BY customer_type
ORDER BY customer_type""", title="Meters per customer type")
    show_query(conn, "SELECT * FROM meters ORDER BY meter_id LIMIT 5", title="Sample rows")
    conn.close()

    count = rows[0][0]
    print(f"\nRESULT: meters contains {count:,} rows -> {'OK' if count == 4000 else 'NOT 4,000 - investigate'}")
    finish_log(STEP)


if __name__ == "__main__":
    main()
