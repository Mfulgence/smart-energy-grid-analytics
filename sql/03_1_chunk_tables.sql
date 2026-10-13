-- ============================================================================
-- Section 3.1  Create the two extra chunk-interval configurations
--     python run_sql.py sql/03_1_chunk_tables.sql
--
-- energy_readings        stays as the ONE-DAY hypertable (already cleaned)
-- energy_readings_3h     same data, THREE-HOUR chunks
-- energy_readings_week   same data, ONE-WEEK chunks
--
-- The file starts by dropping the two extra tables, so running it again
-- rebuilds them from the cleaned energy_readings table.
-- ============================================================================

DROP TABLE IF EXISTS energy_readings_3h;
DROP TABLE IF EXISTS energy_readings_week;

-- LIKE copies the eight column names, types and NOT NULL rules, so the three
-- tables cannot drift apart. It copies no indexes; we add those explicitly.
CREATE TABLE energy_readings_3h   (LIKE energy_readings);
CREATE TABLE energy_readings_week (LIKE energy_readings);

SELECT create_hypertable('energy_readings_3h', 'event_time',
                         chunk_time_interval    => INTERVAL '3 hours',
                         create_default_indexes => FALSE);

SELECT create_hypertable('energy_readings_week', 'event_time',
                         chunk_time_interval    => INTERVAL '1 week',
                         create_default_indexes => FALSE);

-- Copy the cleaned rows. ORDER BY gives both copies the same physical row
-- order as the original load (time first, then meter), so the comparison in
-- 3.2 measures the chunk interval and not a difference in row order.
INSERT INTO energy_readings_3h
SELECT * FROM energy_readings ORDER BY event_time, meter_id;

INSERT INTO energy_readings_week
SELECT * FROM energy_readings ORDER BY event_time, meter_id;

-- Matching NON-UNIQUE indexes: same columns, same method (btree), same sort
-- order (event_time DESC) as the two indexes on energy_readings.
-- Building them after the copy is faster than maintaining them row by row.
CREATE INDEX energy_readings_3h_time_idx
    ON energy_readings_3h USING btree (event_time DESC);
CREATE INDEX energy_readings_3h_meter_time_idx
    ON energy_readings_3h USING btree (meter_id, event_time DESC);

CREATE INDEX energy_readings_week_time_idx
    ON energy_readings_week USING btree (event_time DESC);
CREATE INDEX energy_readings_week_meter_time_idx
    ON energy_readings_week USING btree (meter_id, event_time DESC);

-- Refresh planner statistics on all three so row estimates are current (3.2).
ANALYZE energy_readings;
ANALYZE energy_readings_3h;
ANALYZE energy_readings_week;
