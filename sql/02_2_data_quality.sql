-- ============================================================================
-- Section 2.2  Investigate data quality BEFORE cleaning
-- Executed by:  python s22_data_quality.py   (it prints each query and result)
--
-- Definitions used throughout
--   unique reading   one (meter_id, event_time) pair
--   planned grid     every meter x every 15-minute interval of the 28 days
--                    = 4,000 x 28 x 96 = 10,752,000 pairs
--   missing          a planned pair with no reading at all
--   extra copy       every row beyond the first for the same pair
--   delayed          a unique pair whose received_time is later than the
--                    interval end (event_time + 15 minutes)
-- Each block below starts with "-- name:" so the Python program can run them
-- one at a time.
-- ============================================================================

-- name: build_observed_pairs
-- One row per observed (meter_id, event_time) pair with the number of copies.
-- It is a TEMPORARY table: it lives only for this session and is reused by
-- the queries below so the 10.7 million rows are grouped only once.
CREATE TEMP TABLE observed_pairs AS
SELECT meter_id,
       event_time,
       count(*)           AS copies,          -- 1 = normal, 2+ = duplicated
       min(received_time) AS received_time    -- copies share one received_time
FROM energy_readings
GROUP BY meter_id, event_time;

-- name: analyze_observed_pairs
ANALYZE observed_pairs;

-- name: counts
-- emitted = every stored row;  unique = distinct pairs;  extra = emitted - unique.
SELECT sum(copies)::bigint                                  AS emitted_readings,
       count(*)                                             AS unique_readings,
       sum(copies - 1)::bigint                              AS duplicate_readings,
       count(*) FILTER (WHERE copies > 1)                   AS pairs_with_duplicates,
       max(copies)                                          AS max_copies_of_one_pair,
       count(*) FILTER (WHERE received_time > event_time + INTERVAL '15 minutes')
                                                            AS delayed_unique_readings
FROM observed_pairs;

-- name: missing_from_grid
-- Build the planned grid explicitly (meters x 15-minute steps) and count the
-- grid points that have no observed pair (an anti-join: LEFT JOIN ... IS NULL).
SELECT count(*)                                        AS planned_readings,
       count(o.meter_id)                               AS planned_pairs_observed,
       count(*) FILTER (WHERE o.meter_id IS NULL)      AS missing_readings
FROM meters m
CROSS JOIN generate_series(TIMESTAMPTZ '2026-09-01 00:00:00+02',
                           TIMESTAMPTZ '2026-09-28 23:45:00+02',
                           INTERVAL '15 minutes') AS grid(event_time)
LEFT JOIN observed_pairs o
       ON o.meter_id = m.meter_id AND o.event_time = grid.event_time;

-- name: arrival_delay_profile
-- How late do readings arrive? On-time readings arrive exactly 15 minutes
-- after event_time; delayed ones should fall between 30 and 180 minutes.
SELECT CASE WHEN received_time <= event_time + INTERVAL '15 minutes' THEN 'on time (15 min)'
            ELSE 'delayed' END                                         AS arrival,
       count(*)                                                        AS unique_readings,
       min(extract(epoch FROM received_time - event_time) / 60)::int   AS min_minutes_after_event,
       max(extract(epoch FROM received_time - event_time) / 60)::int   AS max_minutes_after_event
FROM observed_pairs
GROUP BY 1
ORDER BY 1 DESC;

-- name: top5_missing_meters
-- Each meter should have 28 x 96 = 2,688 readings. Missing = 2,688 - observed.
SELECT m.meter_id,
       m.region,
       m.customer_type,
       count(o.event_time)            AS observed_readings,
       28 * 96 - count(o.event_time)  AS missing_readings,
       round(100.0 * (28 * 96 - count(o.event_time)) / (28 * 96), 3) AS missing_percent
FROM meters m
LEFT JOIN observed_pairs o ON o.meter_id = m.meter_id
GROUP BY m.meter_id, m.region, m.customer_type
ORDER BY missing_readings DESC, m.meter_id
LIMIT 5;
