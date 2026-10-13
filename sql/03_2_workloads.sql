-- ============================================================================
-- Sections 3.2 and 4.3  The five benchmark workloads
-- Executed by:  python s32_benchmark.py
-- {table} is the ONLY thing that changes between configurations.
-- "22 to 28 September" includes both named days, so the upper bound is the
-- exclusive instant 29 September 00:00 CAT.
-- ============================================================================

-- name: Q1
-- Average power per CAT hour on 21 September, over every available reading
-- in that hour (24 rows). Narrow one-day time filter across all meters.
SELECT time_bucket('1 hour', event_time, 'Africa/Kigali') AS cat_hour,
       avg(power_kw)                                      AS avg_power_kw
FROM {table}
WHERE event_time >= TIMESTAMPTZ '2026-09-21 00:00:00+02'
  AND event_time <  TIMESTAMPTZ '2026-09-22 00:00:00+02'
GROUP BY cat_hour
ORDER BY cat_hour;

-- name: Q2
-- The ten highest 15-minute network demand intervals from 22 to 28 September.
-- Total power is summed across meters per interval. The second sort key
-- (event_time ascending) decides ties, so exactly ten rows come back even
-- when a tie crosses tenth place.
SELECT event_time,
       sum(power_kw) AS total_power_kw
FROM {table}
WHERE event_time >= TIMESTAMPTZ '2026-09-22 00:00:00+02'
  AND event_time <  TIMESTAMPTZ '2026-09-29 00:00:00+02'
GROUP BY event_time
ORDER BY total_power_kw DESC, event_time ASC
LIMIT 10;

-- name: Q3
-- Total energy per meter across the full historical period (4,000 rows).
-- No time filter: every chunk must be read.
SELECT meter_id,
       sum(energy_kwh) AS total_energy_kwh
FROM {table}
GROUP BY meter_id
ORDER BY meter_id;

-- name: Q4
-- One meter over one week: energy total, average power and peak power.
-- Selective on both meter and time, so the (meter_id, event_time) index helps.
SELECT sum(energy_kwh) AS energy_total_kwh,
       avg(power_kw)   AS average_power_kw,
       max(power_kw)   AS peak_power_kw
FROM {table}
WHERE meter_id = 1000000000
  AND event_time >= TIMESTAMPTZ '2026-09-22 00:00:00+02'
  AND event_time <  TIMESTAMPTZ '2026-09-29 00:00:00+02';

-- name: Q5
-- Full scan: one row of statistics over every reading.
SELECT count(*)        AS row_count,
       sum(energy_kwh) AS total_energy_kwh,
       avg(power_kw)   AS average_power_kw,
       min(power_kw)   AS minimum_power_kw,
       max(power_kw)   AS maximum_power_kw
FROM {table};
