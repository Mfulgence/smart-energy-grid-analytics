-- ============================================================================
-- Section 5  Investigate the utility data
-- Executed by:  s51_demand_patterns.py, s52_groups.py, s53_reporting_quality.py,
--               s54_anomalies.py   (each prints the query and its result)
-- All queries read the CLEANED energy_readings table and group by event_time
-- unless a step explicitly says received_time.
--
-- kWh versus kW in these queries
--   energy_kwh is an amount of energy used in 15 minutes -> it is SUMMED over
--   time to get consumption totals.
--   power_kw is a rate at one moment -> it is SUMMED ACROSS METERS at the same
--   event_time to get network demand, and never summed over time.
-- ============================================================================

-- name: daily_energy
-- 5.1  Total network energy per CAT day (28 rows).
SELECT time_bucket('1 day', event_time, 'Africa/Kigali')      AS cat_day,
       to_char(time_bucket('1 day', event_time, 'Africa/Kigali'), 'Dy') AS weekday,
       sum(energy_kwh)                                         AS energy_kwh,
       count(*)                                                AS readings
FROM energy_readings
GROUP BY cat_day
ORDER BY cat_day;

-- name: weekly_energy
-- 5.1  Totals for the four seven-day periods beginning 1, 8, 15 and 22 September.
-- The fourth argument is the origin: buckets are counted from 1 September
-- 00:00 CAT instead of from a calendar Monday.
SELECT time_bucket('7 days', event_time, 'Africa/Kigali',
                   TIMESTAMPTZ '2026-09-01 00:00:00+02')        AS period_start,
       sum(energy_kwh)                                          AS energy_kwh,
       count(*)                                                 AS readings
FROM energy_readings
GROUP BY period_start
ORDER BY period_start;

-- name: peak_intervals
-- 5.1  The three highest 15-minute network DEMAND intervals of the 28 days.
-- Demand = power summed across all meters at the same event_time (kW).
SELECT event_time,
       to_char(event_time, 'Dy')  AS weekday,
       sum(power_kw)              AS network_demand_kw,
       count(*)                   AS meters_reporting
FROM energy_readings
GROUP BY event_time
ORDER BY network_demand_kw DESC, event_time
LIMIT 3;

-- name: load_profile
-- 5.1  Average network demand by hour of day, working days versus weekend.
-- Used to explain WHEN the peaks happen.
SELECT hour_of_day,
       avg(demand_kw) FILTER (WHERE NOT weekend) AS weekday_avg_kw,
       avg(demand_kw) FILTER (WHERE weekend)     AS weekend_avg_kw
FROM (
    SELECT extract(hour FROM event_time AT TIME ZONE 'Africa/Kigali')::int        AS hour_of_day,
           extract(isodow FROM event_time AT TIME ZONE 'Africa/Kigali') >= 6      AS weekend,
           sum(power_kw)                                                          AS demand_kw
    FROM energy_readings
    GROUP BY event_time
) per_interval
GROUP BY hour_of_day
ORDER BY hour_of_day;

-- name: by_region
-- 5.2  Energy by region over all 28 days, normalised by REGISTERED meters.
-- The meter count comes from the meters table (registered), not from the
-- readings, so a meter that reported less still counts as one meter.
SELECT m.region,
       registered.meter_count,
       sum(r.energy_kwh)                          AS energy_kwh,
       sum(r.energy_kwh) / registered.meter_count AS energy_per_meter_kwh
FROM energy_readings r
JOIN meters m ON m.meter_id = r.meter_id
JOIN (SELECT region, count(*) AS meter_count FROM meters GROUP BY region) registered
  ON registered.region = m.region
GROUP BY m.region, registered.meter_count
ORDER BY length(m.region), m.region;

-- name: by_customer_type
-- 5.2  Energy by customer type over all 28 days, normalised the same way.
SELECT m.customer_type,
       registered.meter_count,
       sum(r.energy_kwh)                          AS energy_kwh,
       sum(r.energy_kwh) / registered.meter_count AS energy_per_meter_kwh
FROM energy_readings r
JOIN meters m ON m.meter_id = r.meter_id
JOIN (SELECT customer_type, count(*) AS meter_count FROM meters GROUP BY customer_type) registered
  ON registered.customer_type = m.customer_type
GROUP BY m.customer_type, registered.meter_count
ORDER BY energy_kwh DESC;

-- name: region_customer_mix
-- 5.2  How many meters of each customer type every region has. This explains
-- regional differences that remain after dividing by the meter count.
SELECT region,
       count(*) FILTER (WHERE customer_type = 'residential') AS residential,
       count(*) FILTER (WHERE customer_type = 'commercial')  AS commercial,
       count(*) FILTER (WHERE customer_type = 'industrial')  AS industrial,
       round(avg(base_power_kw)::numeric, 3)                 AS avg_base_power_kw
FROM meters
GROUP BY region
ORDER BY length(region), region;

-- name: completeness_network
-- 5.3  Completeness of the whole network.
-- planned = registered meters x 28 days x 96 readings per day.
-- After cleaning each row is one unique (meter_id, event_time) pair.
SELECT (SELECT count(*) FROM meters)                                   AS registered_meters,
       (SELECT count(*) FROM meters) * 28 * 96                         AS planned_readings,
       count(*)                                                        AS observed_unique_pairs,
       round(100.0 * count(*) / ((SELECT count(*) FROM meters) * 28 * 96), 6) AS completeness_percent
FROM energy_readings;

-- name: completeness_by_region
-- 5.3  Completeness of each region.
SELECT m.region,
       registered.meter_count                               AS registered_meters,
       registered.meter_count * 28 * 96                     AS planned_readings,
       count(*)                                             AS observed_unique_pairs,
       registered.meter_count * 28 * 96 - count(*)          AS missing_readings,
       round(100.0 * count(*) / (registered.meter_count * 28 * 96), 6) AS completeness_percent
FROM energy_readings r
JOIN meters m ON m.meter_id = r.meter_id
JOIN (SELECT region, count(*) AS meter_count FROM meters GROUP BY region) registered
  ON registered.region = m.region
GROUP BY m.region, registered.meter_count
ORDER BY length(m.region), m.region;

-- name: day21_on_time_vs_final
-- 5.3  Energy of 21 September counted twice:
--   on time = only readings that had ARRIVED (received_time) by 00:00 on 22 Sept
--   final   = every reading for that day, whenever it arrived
-- This is the one query that uses received_time.
SELECT sum(energy_kwh) FILTER (WHERE received_time <= TIMESTAMPTZ '2026-09-22 00:00:00+02')
                                                              AS energy_arrived_by_midnight_kwh,
       sum(energy_kwh)                                        AS energy_all_arrivals_kwh,
       count(*) FILTER (WHERE received_time <= TIMESTAMPTZ '2026-09-22 00:00:00+02')
                                                              AS readings_arrived_by_midnight,
       count(*)                                               AS readings_all_arrivals,
       (SELECT count(*) FROM meters) * 96                     AS planned_readings_for_the_day
FROM energy_readings
WHERE event_time >= TIMESTAMPTZ '2026-09-21 00:00:00+02'
  AND event_time <  TIMESTAMPTZ '2026-09-22 00:00:00+02';

-- name: build_expected_profile
-- 5.4  Step 1 of the anomaly rule: learn what is NORMAL for each meter.
-- For every meter, every 15-minute time-of-day slot and each day type
-- (working day / weekend) take the MEDIAN power over the 28 days.
-- The median is used instead of the mean because a few abnormal readings
-- cannot move it, so the baseline itself is not polluted by anomalies.
CREATE TEMP TABLE expected_profile AS
SELECT meter_id,
       (event_time AT TIME ZONE 'Africa/Kigali')::time                      AS slot,
       extract(isodow FROM event_time AT TIME ZONE 'Africa/Kigali') >= 6    AS weekend,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY power_kw)                AS typical_kw,
       count(*)                                                             AS samples
FROM energy_readings
GROUP BY 1, 2, 3;

-- name: index_expected_profile
CREATE INDEX ON expected_profile (meter_id, slot, weekend);

-- name: ratio_distribution
-- 5.4  Step 2: how far do readings normally sit from their own typical value?
-- ratio = actual power / typical power for that meter, slot and day type.
-- The percentiles show the spread of normal behaviour and justify thresholds.
SELECT count(*)                                                    AS readings,
       percentile_cont(0.0001) WITHIN GROUP (ORDER BY ratio)       AS p0_01,
       percentile_cont(0.001)  WITHIN GROUP (ORDER BY ratio)       AS p0_1,
       percentile_cont(0.01)   WITHIN GROUP (ORDER BY ratio)       AS p1,
       percentile_cont(0.5)    WITHIN GROUP (ORDER BY ratio)       AS median,
       percentile_cont(0.99)   WITHIN GROUP (ORDER BY ratio)       AS p99,
       percentile_cont(0.999)  WITHIN GROUP (ORDER BY ratio)       AS p99_9,
       percentile_cont(0.9999) WITHIN GROUP (ORDER BY ratio)       AS p99_99
FROM (
    SELECT r.power_kw / p.typical_kw AS ratio
    FROM energy_readings r
    JOIN expected_profile p
      ON p.meter_id = r.meter_id
     AND p.slot     = (r.event_time AT TIME ZONE 'Africa/Kigali')::time
     AND p.weekend  = (extract(isodow FROM r.event_time AT TIME ZONE 'Africa/Kigali') >= 6)
    WHERE p.typical_kw > 0
) ratios;

-- name: drop_flags
DROP TABLE IF EXISTS anomaly_flags;

-- name: build_flags
-- 5.4  Step 3: apply the rule. A reading is flagged when its power is at
-- least HIGH times, or at most LOW times, the typical value for that meter,
-- time slot and day type. {high} and {low} are filled in by s54_anomalies.py.
-- Every flag identifies one meter_id and one event_time.
CREATE TABLE anomaly_flags AS
SELECT r.meter_id,
       r.event_time,
       r.power_kw,
       p.typical_kw,
       r.power_kw / p.typical_kw                                       AS ratio,
       CASE WHEN r.power_kw >= {high} * p.typical_kw THEN 'demand_spike'
            ELSE 'unusual_drop' END                                    AS flag_type
FROM energy_readings r
JOIN expected_profile p
  ON p.meter_id = r.meter_id
 AND p.slot     = (r.event_time AT TIME ZONE 'Africa/Kigali')::time
 AND p.weekend  = (extract(isodow FROM r.event_time AT TIME ZONE 'Africa/Kigali') >= 6)
WHERE p.typical_kw > 0
  AND (r.power_kw >= {high} * p.typical_kw OR r.power_kw <= {low} * p.typical_kw);

-- name: flag_summary
SELECT flag_type,
       count(*)                  AS flagged_readings,
       count(DISTINCT meter_id)  AS meters,
       min(ratio)                AS min_ratio,
       max(ratio)                AS max_ratio
FROM anomaly_flags
GROUP BY flag_type
ORDER BY flag_type;

-- name: flag_sample
SELECT meter_id, event_time, power_kw, typical_kw, ratio, flag_type
FROM anomaly_flags
ORDER BY event_time, meter_id
LIMIT 15;

-- name: flag_runs
-- Flags grouped into one line per meter: first flag, last flag, how many.
SELECT meter_id, flag_type, min(event_time) AS first_flag, max(event_time) AS last_flag,
       count(*) AS flagged_readings
FROM anomaly_flags
GROUP BY meter_id, flag_type
ORDER BY first_flag, meter_id;

-- name: readings_inside_events
-- Used only for EVALUATION: observed readings that fall inside an injected
-- interval of their own meter (start inclusive, end exclusive).
SELECT count(*) AS observed_readings_inside_injected_intervals
FROM energy_readings r
JOIN injected_events e
  ON e.meter_id = r.meter_id
 AND r.event_time >= e.start_time
 AND r.event_time <  e.end_time;
