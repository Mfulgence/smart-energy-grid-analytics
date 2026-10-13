-- ============================================================================
-- Section 8.1  Forecast dataset: one row per region and CAT hour
-- Executed by:  python s81_prepare_features.py
-- Sums energy_kwh from the CLEANED readings. reading_count shows how many
-- readings each hourly total is built from (400 meters x 4 intervals = 1,600
-- when nothing is missing).
-- ============================================================================

-- name: hourly_region_energy
SELECT time_bucket(INTERVAL '1 hour', r.event_time, 'Africa/Kigali') AS target_hour,
       m.region,
       sum(r.energy_kwh) AS energy_kwh,
       count(*)          AS reading_count
FROM energy_readings r
JOIN meters m ON m.meter_id = r.meter_id
GROUP BY target_hour, m.region
ORDER BY length(m.region), m.region, target_hour;
