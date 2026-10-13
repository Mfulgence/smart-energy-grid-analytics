-- ============================================================================
-- Section 1.1 (part b)  Enable TimescaleDB and fix the time zone
-- Run while connected to energy_grid:
--     python run_sql.py sql/01_1b_enable_timescaledb.sql
-- ============================================================================

-- 1. Turn the extension on in THIS database. Extensions are per database, so
--    this must be run inside energy_grid, not inside "postgres".
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 2. Make Africa/Kigali (CAT, UTC+02:00, no daylight saving) the default zone
--    for every future session that connects to this database.
ALTER DATABASE energy_grid SET timezone TO 'Africa/Kigali';

-- 3. The ALTER above only affects NEW sessions, so set it for this one too.
SET TIME ZONE 'Africa/Kigali';

-- ---- Evidence for the 1.1 screenshots --------------------------------------

-- Which database and server are we connected to?
SELECT current_database() AS database,
       current_user       AS connected_as,
       version()          AS postgresql_version;

-- Is the extension enabled, and which version?
SELECT extname AS extension, extversion AS version
FROM pg_extension
WHERE extname = 'timescaledb';

-- Session time zone and the current database clock shown in CAT.
SELECT current_setting('TimeZone') AS session_time_zone,
       now()                       AS database_clock_cat;

-- The four configuration values the assignment asks us to record.
SELECT name, setting, unit, current_setting(name) AS readable_value
FROM pg_settings
WHERE name IN ('shared_buffers', 'work_mem', 'max_parallel_workers_per_gather', 'jit')
ORDER BY name;

-- "Align daily buckets to CAT midnight".
-- time_bucket() cuts days at UTC midnight unless it is told a time zone.
-- 13:45 CAT on 1 September belongs to the CAT day starting 00:00 CAT.
-- With the zone argument the bucket starts at 00:00+02 (correct).
-- Without it the bucket starts at 02:00+02, which is UTC midnight (wrong for us).
-- Every daily query, view and dashboard panel in this project therefore uses
-- the three-argument form time_bucket('1 day', event_time, 'Africa/Kigali').
SELECT time_bucket('1 day', TIMESTAMPTZ '2026-09-01 13:45:00+02', 'Africa/Kigali') AS day_bucket_aligned_to_cat,
       time_bucket('1 day', TIMESTAMPTZ '2026-09-01 13:45:00+02')                  AS day_bucket_default_utc;
