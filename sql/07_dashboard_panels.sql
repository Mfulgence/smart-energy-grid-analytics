-- ============================================================================
-- Section 7  Dashboard panel queries (the single source for both dashboards)
-- Used by:  s71_dashboard.py (the running dashboards)
--           s73_verify_dashboards.py (the numerical comparison)
--
-- raw_*  read energy_readings directly (joining meters where needed)
-- agg_*  read the continuous aggregate views; meters is used only for
--        labels and registered meter counts
--
-- Parameters supplied by the dashboard filters
--   %(start)s     first selected CAT day at 00:00            (inclusive)
--   %(end)s       day after the last selected day at 00:00   (exclusive)
--   %(meter_id)s  selected meter, used only by panel 4
-- Every panel is limited to the selected date range.
-- Each query also returns reading_count so 7.3 can check that both modes
-- used exactly the same number of readings.
-- ============================================================================

-- name: raw_p1
-- Panel 1  Hourly regional energy (kWh), straight from the raw readings.
SELECT time_bucket(INTERVAL '1 hour', r.event_time, 'Africa/Kigali') AS bucket,
       m.region,
       sum(r.energy_kwh)  AS energy_kwh,
       count(*)           AS reading_count
FROM energy_readings r
JOIN meters m ON m.meter_id = r.meter_id
WHERE r.event_time >= %(start)s AND r.event_time < %(end)s
GROUP BY bucket, m.region
ORDER BY bucket, length(m.region), m.region;

-- name: agg_p1
-- Panel 1  Hourly regional energy from the HOURLY regional view.
SELECT bucket,
       region,
       energy_kwh_sum          AS energy_kwh,
       reading_count::bigint   AS reading_count
FROM agg_region_hourly
WHERE bucket >= %(start)s AND bucket < %(end)s
ORDER BY bucket, length(region), region;

-- name: raw_p2
-- Panel 2  Daily network energy (kWh) per CAT day.
SELECT time_bucket(INTERVAL '1 day', event_time, 'Africa/Kigali') AS bucket,
       sum(energy_kwh)  AS energy_kwh,
       count(*)         AS reading_count
FROM energy_readings
WHERE event_time >= %(start)s AND event_time < %(end)s
GROUP BY bucket
ORDER BY bucket;

-- name: agg_p2
-- Panel 2  Daily network energy from the 15-MINUTE regional view.
-- Stored sums and counts are summed again when buckets are combined
-- (15-minute x region  ->  one CAT day for the whole network).
SELECT time_bucket(INTERVAL '1 day', bucket, 'Africa/Kigali') AS bucket,
       sum(energy_kwh_sum)             AS energy_kwh,
       sum(reading_count)::bigint      AS reading_count
FROM agg_region_15min
WHERE bucket >= %(start)s AND bucket < %(end)s
GROUP BY 1
ORDER BY 1;

-- name: raw_p3
-- Panel 3  Network energy in the seven-day periods that begin on 1, 8, 15 and
-- 22 September (origin = 1 September 00:00 CAT), limited to the selection.
SELECT time_bucket(INTERVAL '7 days', event_time, 'Africa/Kigali',
                   TIMESTAMPTZ '2026-09-01 00:00:00+02') AS bucket,
       sum(energy_kwh)  AS energy_kwh,
       count(*)         AS reading_count
FROM energy_readings
WHERE event_time >= %(start)s AND event_time < %(end)s
GROUP BY bucket
ORDER BY bucket;

-- name: agg_p3
-- Panel 3  The same seven-day periods from the 15-MINUTE regional view.
SELECT time_bucket(INTERVAL '7 days', bucket, 'Africa/Kigali',
                   TIMESTAMPTZ '2026-09-01 00:00:00+02') AS bucket,
       sum(energy_kwh_sum)             AS energy_kwh,
       sum(reading_count)::bigint      AS reading_count
FROM agg_region_15min
WHERE bucket >= %(start)s AND bucket < %(end)s
GROUP BY 1
ORDER BY 1;

-- name: raw_p4
-- Panel 4  Daily energy (kWh) of the selected meter.
SELECT time_bucket(INTERVAL '1 day', event_time, 'Africa/Kigali') AS bucket,
       meter_id,
       sum(energy_kwh)  AS energy_kwh,
       count(*)         AS reading_count
FROM energy_readings
WHERE meter_id = %(meter_id)s
  AND event_time >= %(start)s AND event_time < %(end)s
GROUP BY bucket, meter_id
ORDER BY bucket;

-- name: agg_p4
-- Panel 4  Meter history from the DAILY meter view.
SELECT bucket,
       meter_id,
       energy_kwh_sum          AS energy_kwh,
       reading_count::bigint   AS reading_count
FROM agg_meter_daily
WHERE meter_id = %(meter_id)s
  AND bucket >= %(start)s AND bucket < %(end)s
ORDER BY bucket;

-- name: raw_p5
-- Panel 5  Completeness by region (percent), as defined in 5.3.
--   planned  = registered meters x number of 15-minute intervals selected
--   observed = unique (meter_id, event_time) pairs = rows of the cleaned table
SELECT registered.region,
       registered.meter_count,
       coalesce(observed.reading_count, 0)                    AS reading_count,
       registered.meter_count * period.intervals              AS planned_readings,
       (100.0 * coalesce(observed.reading_count, 0)
              / (registered.meter_count * period.intervals))::double precision AS completeness_percent
FROM (SELECT region, count(*) AS meter_count FROM meters GROUP BY region) registered
CROSS JOIN (SELECT (extract(epoch FROM (%(end)s::timestamptz - %(start)s::timestamptz)) / 900)::bigint
                   AS intervals) period
LEFT JOIN (
    SELECT m.region, count(*) AS reading_count
    FROM energy_readings r
    JOIN meters m ON m.meter_id = r.meter_id
    WHERE r.event_time >= %(start)s AND r.event_time < %(end)s
    GROUP BY m.region
) observed ON observed.region = registered.region
ORDER BY length(registered.region), registered.region;

-- name: agg_p5
-- Panel 5  Completeness with the OBSERVED counts taken from the 15-MINUTE
-- regional view (stored reading counts are summed). Planned readings still
-- come from the registered meter counts and the selected period.
SELECT registered.region,
       registered.meter_count,
       coalesce(observed.reading_count, 0)                    AS reading_count,
       registered.meter_count * period.intervals              AS planned_readings,
       (100.0 * coalesce(observed.reading_count, 0)
              / (registered.meter_count * period.intervals))::double precision AS completeness_percent
FROM (SELECT region, count(*) AS meter_count FROM meters GROUP BY region) registered
CROSS JOIN (SELECT (extract(epoch FROM (%(end)s::timestamptz - %(start)s::timestamptz)) / 900)::bigint
                   AS intervals) period
LEFT JOIN (
    SELECT region, sum(reading_count)::bigint AS reading_count
    FROM agg_region_15min
    WHERE bucket >= %(start)s AND bucket < %(end)s
    GROUP BY region
) observed ON observed.region = registered.region
ORDER BY length(registered.region), registered.region;
