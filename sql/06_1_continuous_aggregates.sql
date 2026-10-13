-- ============================================================================
-- Section 6.1  Three continuous aggregate views over energy_readings
--     python run_sql.py sql/06_1_continuous_aggregates.sql
-- Then:  python s61_refresh_aggregates.py   (timed refresh, sizes, policies)
--
-- A continuous aggregate is a view whose result is STORED (materialized) in a
-- hidden hypertable and kept up to date by refreshing only the time ranges
-- that changed. Dashboards then read a few thousand stored rows instead of
-- re-aggregating 10.6 million raw rows on every refresh.
--
--   agg_region_15min   15-minute bucket x region
--   agg_region_hourly  CAT hour         x region
--   agg_meter_daily    CAT day          x meter_id
--
-- Each view stores: the bucket, its grouping key, sum of energy_kwh,
-- sum of power_kw and the number of readings.
--
-- WITH NO DATA              -> created empty ("initially unpopulated")
-- materialized_only = TRUE  -> real-time aggregation OFF: a query returns only
--                              what is stored, never raw rows added on the fly.
--                              Section 7 must measure stored aggregates.
-- The regional views use an INNER JOIN on meter_id to pick up the region.
-- The meters table itself is not modified.
-- ============================================================================

-- Drop first so the file can be re-run (CASCADE also removes their policies).
DROP MATERIALIZED VIEW IF EXISTS agg_region_15min CASCADE;
DROP MATERIALIZED VIEW IF EXISTS agg_region_hourly CASCADE;
DROP MATERIALIZED VIEW IF EXISTS agg_meter_daily CASCADE;

-- 1. 15-minute bucket and region.
--    A 15-minute bucket is the same instant in every time zone (CAT is a
--    whole number of hours from UTC), so no zone argument is needed here.
CREATE MATERIALIZED VIEW agg_region_15min
WITH (timescaledb.continuous, timescaledb.materialized_only = TRUE) AS
SELECT time_bucket(INTERVAL '15 minutes', r.event_time) AS bucket,
       m.region,
       sum(r.energy_kwh) AS energy_kwh_sum,
       sum(r.power_kw)   AS power_kw_sum,
       count(*)          AS reading_count
FROM energy_readings r
INNER JOIN meters m ON m.meter_id = r.meter_id
GROUP BY bucket, m.region
WITH NO DATA;

-- 2. CAT hour and region.
CREATE MATERIALIZED VIEW agg_region_hourly
WITH (timescaledb.continuous, timescaledb.materialized_only = TRUE) AS
SELECT time_bucket(INTERVAL '1 hour', r.event_time, 'Africa/Kigali') AS bucket,
       m.region,
       sum(r.energy_kwh) AS energy_kwh_sum,
       sum(r.power_kw)   AS power_kw_sum,
       count(*)          AS reading_count
FROM energy_readings r
INNER JOIN meters m ON m.meter_id = r.meter_id
GROUP BY bucket, m.region
WITH NO DATA;

-- 3. CAT day and meter. The zone argument is essential here: it makes each
--    bucket start at 00:00 CAT instead of 00:00 UTC (which is 02:00 CAT).
CREATE MATERIALIZED VIEW agg_meter_daily
WITH (timescaledb.continuous, timescaledb.materialized_only = TRUE) AS
SELECT time_bucket(INTERVAL '1 day', event_time, 'Africa/Kigali') AS bucket,
       meter_id,
       sum(energy_kwh) AS energy_kwh_sum,
       sum(power_kw)   AS power_kw_sum,
       count(*)        AS reading_count
FROM energy_readings
GROUP BY bucket, meter_id
WITH NO DATA;

-- ---- Evidence: definitions and the "initially empty" state -----------------
SELECT view_name,
       materialized_only,                       -- TRUE = real-time aggregation disabled
       materialization_hypertable_name AS stored_in
FROM timescaledb_information.continuous_aggregates
WHERE view_name IN ('agg_region_15min', 'agg_region_hourly', 'agg_meter_daily')
ORDER BY view_name;

SELECT view_name, view_definition
FROM timescaledb_information.continuous_aggregates
WHERE view_name IN ('agg_region_15min', 'agg_region_hourly', 'agg_meter_daily')
ORDER BY view_name;

SELECT (SELECT count(*) FROM agg_region_15min)  AS rows_15min_before_refresh,
       (SELECT count(*) FROM agg_region_hourly) AS rows_hourly_before_refresh,
       (SELECT count(*) FROM agg_meter_daily)   AS rows_daily_before_refresh;
