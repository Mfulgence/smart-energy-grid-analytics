-- ============================================================================
-- Section 6.2  Freshness and delayed-arrival test objects
-- Executed by:  python s62_freshness_test.py
--
-- A small, separate hypertable and one hourly continuous aggregate, used only
-- to SEE when new and late rows become visible in an aggregate. Nothing here
-- touches energy_readings.
-- ============================================================================

-- name: drop_view
DROP MATERIALIZED VIEW IF EXISTS freshness_hourly CASCADE;

-- name: drop_table
DROP TABLE IF EXISTS freshness_test;

-- name: create_table
CREATE TABLE freshness_test (
    event_time TIMESTAMPTZ      NOT NULL,
    energy_kwh DOUBLE PRECISION NOT NULL
);

-- name: create_hypertable
SELECT create_hypertable('freshness_test', 'event_time');

-- name: create_view
-- Hourly sum and row count. Created empty (WITH NO DATA), real-time
-- aggregation off (materialized_only = TRUE) and NO refresh policy, so the
-- view only changes when this test refreshes it by hand.
CREATE MATERIALIZED VIEW freshness_hourly
WITH (timescaledb.continuous, timescaledb.materialized_only = TRUE) AS
SELECT time_bucket(INTERVAL '1 hour', event_time, 'Africa/Kigali') AS bucket,
       sum(energy_kwh) AS energy_kwh_sum,
       count(*)        AS row_count
FROM freshness_test
GROUP BY bucket
WITH NO DATA;

-- name: show_definitions
SELECT view_name, materialized_only, view_definition
FROM timescaledb_information.continuous_aggregates
WHERE view_name = 'freshness_hourly';

-- name: show_columns
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_name IN ('freshness_test', 'freshness_hourly')
ORDER BY table_name, ordinal_position;

-- name: policies_on_view
-- Must return 0: automatic refresh stays off for the whole test.
SELECT count(*) AS refresh_policies_on_freshness_hourly
FROM timescaledb_information.jobs j
JOIN timescaledb_information.continuous_aggregates ca
  ON j.hypertable_name IN (ca.view_name, ca.materialization_hypertable_name)
WHERE ca.view_name = 'freshness_hourly';

-- name: insert_reading
INSERT INTO freshness_test (event_time, energy_kwh) VALUES (%(event_time)s, %(energy_kwh)s);

-- name: refresh_window
CALL refresh_continuous_aggregate('freshness_hourly', %(window_start)s::timestamptz, %(window_end)s::timestamptz);

-- name: realtime_setting
SELECT view_name, materialized_only,
       CASE WHEN materialized_only THEN 'OFF' ELSE 'ON' END AS real_time_aggregation
FROM timescaledb_information.continuous_aggregates
WHERE view_name = 'freshness_hourly';

-- name: enable_realtime
-- materialized_only = FALSE switches real-time aggregation ON: a query now
-- returns the stored buckets PLUS raw rows newer than the last refreshed point.
ALTER MATERIALIZED VIEW freshness_hourly SET (timescaledb.materialized_only = FALSE);

-- name: raw_by_hour
-- The truth: aggregate the raw test table directly.
SELECT time_bucket(INTERVAL '1 hour', event_time, 'Africa/Kigali') AS hour,
       sum(energy_kwh) AS energy_kwh_sum,
       count(*)        AS row_count
FROM freshness_test
WHERE event_time >= %(older)s AND event_time < %(h_end)s
GROUP BY hour
ORDER BY hour;

-- name: aggregate_by_hour
-- What the continuous aggregate returns for the same two hours.
SELECT bucket AS hour, energy_kwh_sum, row_count
FROM freshness_hourly
WHERE bucket IN (%(older)s, %(h)s)
ORDER BY bucket;
