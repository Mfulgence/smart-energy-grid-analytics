-- ============================================================================
-- Section 2.3  Remove duplicate copies and keep one consistent benchmark set
-- Executed by:  python s23_clean.py   (it prints each query and result)
--
-- Rule: rows sharing (meter_id, event_time) are duplicates. If their other six
-- values are identical we keep ONE row and delete the extra copies. If they
-- differ ("conflict") we stop and investigate instead of deleting.
-- Missing intervals are left as gaps: nothing is inserted or filled.
-- The script is repeatable: on a clean table it finds nothing and deletes 0.
-- ============================================================================

-- name: totals
-- Row count, distinct pairs and total energy. Run before and after the clean.
-- The inner query makes one row per (meter_id, event_time) pair; the outer
-- query adds the pairs up. row_count > distinct_pairs means duplicates exist.
SELECT sum(copies)::bigint AS row_count,
       count(*)            AS distinct_pairs,
       sum(pair_energy)    AS total_energy_kwh
FROM (
    SELECT count(*) AS copies, sum(energy_kwh) AS pair_energy
    FROM energy_readings
    GROUP BY meter_id, event_time
) pairs;

-- name: find_duplicate_pairs
-- Every (meter_id, event_time) that occurs more than once.
-- The six count(DISTINCT ...) columns compare the six remaining values across
-- the copies: 1 distinct value means "all copies agree" for that column.
CREATE TEMP TABLE duplicate_pairs AS
SELECT meter_id,
       event_time,
       count(*)                        AS copies,
       count(DISTINCT received_time)   AS distinct_received_time,
       count(DISTINCT power_kw)        AS distinct_power_kw,
       count(DISTINCT voltage_v)       AS distinct_voltage_v,
       count(DISTINCT current_a)       AS distinct_current_a,
       count(DISTINCT frequency_hz)    AS distinct_frequency_hz,
       count(DISTINCT energy_kwh)      AS distinct_energy_kwh
FROM energy_readings
GROUP BY meter_id, event_time
HAVING count(*) > 1;

-- name: duplicate_summary
-- conflicting_pairs must be 0 before anything is deleted.
SELECT count(*)                           AS duplicated_pairs,
       coalesce(sum(copies - 1), 0)::bigint AS extra_copies_to_delete,
       count(*) FILTER (WHERE distinct_received_time > 1 OR distinct_power_kw > 1
                           OR distinct_voltage_v > 1 OR distinct_current_a > 1
                           OR distinct_frequency_hz > 1 OR distinct_energy_kwh > 1)
                                          AS conflicting_pairs
FROM duplicate_pairs;

-- name: conflict_examples
-- Lists any pair whose copies disagree (expected: no rows).
SELECT r.*
FROM energy_readings r
JOIN duplicate_pairs d ON d.meter_id = r.meter_id AND d.event_time = r.event_time
WHERE d.distinct_received_time > 1 OR d.distinct_power_kw > 1 OR d.distinct_voltage_v > 1
   OR d.distinct_current_a > 1 OR d.distinct_frequency_hz > 1 OR d.distinct_energy_kwh > 1
ORDER BY r.meter_id, r.event_time
LIMIT 20;

-- name: duplicate_examples
-- A few duplicated readings shown side by side, as evidence that copies match.
SELECT r.*
FROM energy_readings r
JOIN (SELECT meter_id, event_time FROM duplicate_pairs ORDER BY event_time, meter_id LIMIT 3) d
  ON d.meter_id = r.meter_id AND d.event_time = r.event_time
ORDER BY r.meter_id, r.event_time;

-- name: extra_copy_energy
-- Energy carried by the copies that are about to be deleted. After cleaning,
-- total energy must drop by exactly this amount (one copy of each pair stays).
SELECT coalesce(sum(extra.energy_kwh), 0) AS energy_in_extra_copies_kwh
FROM (
    SELECT r.energy_kwh,
           row_number() OVER (PARTITION BY r.meter_id, r.event_time ORDER BY r.ctid) AS copy_number
    FROM energy_readings r
    JOIN duplicate_pairs d ON d.meter_id = r.meter_id AND d.event_time = r.event_time
) extra
WHERE extra.copy_number > 1;

-- name: delete_extra_copies
-- How one copy is kept:
--   * The rows are identical in all eight columns, so no column can tell the
--     copies apart. PostgreSQL's hidden column ctid (the physical address of a
--     row) can. In a hypertable each chunk is its own table, so the pair
--     (tableoid, ctid) identifies exactly one physical row.
--   * row_number() numbers the copies inside each group of identical rows:
--     copy 1, copy 2, ...  Copy 1 is retained; copies 2+ are deleted.
--   * Partitioning by ALL eight columns means only fully identical rows are
--     ever treated as copies of each other.
WITH ranked AS (
    SELECT r.tableoid AS chunk_oid,
           r.ctid     AS row_address,
           row_number() OVER (
               PARTITION BY r.meter_id, r.event_time, r.received_time, r.power_kw,
                            r.voltage_v, r.current_a, r.frequency_hz, r.energy_kwh
               ORDER BY r.ctid
           ) AS copy_number
    FROM energy_readings r
    JOIN duplicate_pairs d ON d.meter_id = r.meter_id AND d.event_time = r.event_time
)
DELETE FROM energy_readings t
USING ranked x
WHERE t.tableoid = x.chunk_oid
  AND t.ctid     = x.row_address
  AND x.copy_number > 1;

-- name: remaining_duplicates
-- Must return 0 after cleaning.
SELECT count(*) AS duplicate_pairs_remaining
FROM (SELECT 1 FROM energy_readings GROUP BY meter_id, event_time HAVING count(*) > 1) leftover;

-- name: vacuum_analyze
-- Reclaim the space of the deleted rows and refresh planner statistics.
VACUUM (ANALYZE) energy_readings;
