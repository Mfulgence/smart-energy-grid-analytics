-- ============================================================================
-- Section 3.1  Evidence that the three configurations hold the same data
-- Executed by:  python s31_verify_chunks.py
-- {table} is replaced by each hypertable name in turn.
-- ============================================================================

-- name: chunk_intervals
-- The configured chunk interval of every hypertable under comparison.
SELECT hypertable_name,
       column_name          AS partition_column,
       time_interval::text  AS chunk_interval
FROM timescaledb_information.dimensions
WHERE hypertable_name = ANY(%(tables)s)
ORDER BY time_interval;

-- name: chunk_counts
-- How many chunks each table actually has and the time range they span.
-- Chunk boundaries are aligned to UTC, i.e. 02:00 CAT. That is why the
-- one-day table has 29 chunks for 28 CAT days: the first and last CAT day
-- each fall partly into an extra chunk.
SELECT hypertable_name,
       count(*)          AS chunk_count,
       min(range_start)  AS first_chunk_start,
       max(range_end)    AS last_chunk_end
FROM timescaledb_information.chunks
WHERE hypertable_name = ANY(%(tables)s)
GROUP BY hypertable_name
ORDER BY chunk_count DESC;

-- name: indexes
-- Index definitions: must be the same two b-tree indexes on every table.
SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public' AND tablename = ANY(%(tables)s)
ORDER BY tablename, indexname;

-- name: data_check
-- The six values that must match across tables.
SELECT count(*)                 AS row_count,
       count(DISTINCT meter_id) AS distinct_meters,
       min(event_time)          AS earliest_event_time,
       max(event_time)          AS latest_event_time,
       sum(power_kw)            AS sum_power_kw,
       sum(energy_kwh)          AS sum_energy_kwh
FROM {table};
