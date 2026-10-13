-- ============================================================================
-- Section 4.1  Two compressed configurations
-- Executed by:  python s41_load_and_compress.py --baseline <chosen table>
-- {interval} is replaced by the chunk interval chosen from Section 3
-- (for example '1 day'). Both tables use that same interval.
--
--   energy_time_compressed    ORDER BY event_time DESC, NO segmentation
--   energy_meter_compressed   ORDER BY event_time DESC, SEGMENT BY meter_id
--
-- What the two settings mean
--   orderby    the order of rows inside each compressed batch. Sorting by time
--              puts similar neighbouring values together, which compresses
--              well and lets time filters skip batches using min/max metadata.
--   segmentby  rows are first split into one group per meter_id and each
--              group is compressed on its own. A query for ONE meter can then
--              decompress only that meter's batches. Without segmentation a
--              batch mixes all meters, so a single-meter query has to
--              decompress every batch in the time range.
-- ============================================================================

-- name: drop_tables
DROP TABLE IF EXISTS energy_time_compressed, energy_meter_compressed;

-- name: create_time_table
CREATE TABLE energy_time_compressed (LIKE energy_readings);

-- name: create_meter_table
CREATE TABLE energy_meter_compressed (LIKE energy_readings);

-- name: hypertable_time
SELECT create_hypertable('energy_time_compressed', 'event_time',
                         chunk_time_interval    => INTERVAL '{interval}',
                         create_default_indexes => FALSE);

-- name: hypertable_meter
SELECT create_hypertable('energy_meter_compressed', 'event_time',
                         chunk_time_interval    => INTERVAL '{interval}',
                         create_default_indexes => FALSE);

-- name: index_time_1
CREATE INDEX energy_time_compressed_time_idx
    ON energy_time_compressed USING btree (event_time DESC);

-- name: index_time_2
CREATE INDEX energy_time_compressed_meter_time_idx
    ON energy_time_compressed USING btree (meter_id, event_time DESC);

-- name: index_meter_1
CREATE INDEX energy_meter_compressed_time_idx
    ON energy_meter_compressed USING btree (event_time DESC);

-- name: index_meter_2
CREATE INDEX energy_meter_compressed_meter_time_idx
    ON energy_meter_compressed USING btree (meter_id, event_time DESC);

-- name: compression_time
-- Strategy 1: time ordering only. The empty string switches segmentation OFF
-- explicitly (newer TimescaleDB versions would otherwise pick a default).
ALTER TABLE energy_time_compressed SET (
    timescaledb.compress,
    timescaledb.compress_orderby   = 'event_time DESC',
    timescaledb.compress_segmentby = ''
);

-- name: compression_meter
-- Strategy 2: the same ordering, segmented by meter.
ALTER TABLE energy_meter_compressed SET (
    timescaledb.compress,
    timescaledb.compress_orderby   = 'event_time DESC',
    timescaledb.compress_segmentby = 'meter_id'
);

-- name: policy_time
-- Policy: automatically compress chunks whose END is more than 48 hours old.
SELECT add_compression_policy('energy_time_compressed', compress_after => INTERVAL '48 hours') AS job_id;

-- name: policy_meter
SELECT add_compression_policy('energy_meter_compressed', compress_after => INTERVAL '48 hours') AS job_id;

-- name: pause_policies
-- Pause both policies until the 4.3 measurements are complete, so that every
-- compression in this experiment is the manual, individually timed one.
SELECT job_id, alter_job(job_id, scheduled => false) IS NOT NULL AS paused
FROM timescaledb_information.jobs
WHERE proc_name IN ('policy_compression', 'policy_columnstore')
  AND hypertable_name IN ('energy_time_compressed', 'energy_meter_compressed');

-- name: show_policies
SELECT job_id, hypertable_name, proc_name AS policy, schedule_interval::text AS runs_every,
       config::text AS settings, scheduled AS enabled
FROM timescaledb_information.jobs
WHERE hypertable_name IN ('energy_time_compressed', 'energy_meter_compressed')
ORDER BY hypertable_name;

-- name: show_configuration
SELECT d.hypertable_name, d.time_interval::text AS chunk_interval,
       h.compression_enabled
FROM timescaledb_information.dimensions d
JOIN timescaledb_information.hypertables h USING (hypertable_name)
WHERE d.hypertable_name IN ('energy_time_compressed', 'energy_meter_compressed')
ORDER BY d.hypertable_name;

-- name: show_settings
-- orderby / segmentby actually stored for each table.
SELECT hypertable_name, attname AS column_name,
       segmentby_column_index AS segmentby_position,
       orderby_column_index   AS orderby_position,
       CASE WHEN orderby_column_index IS NULL THEN NULL
            WHEN orderby_asc THEN 'ASC' ELSE 'DESC' END AS order_direction
FROM timescaledb_information.compression_settings
WHERE hypertable_name IN ('energy_time_compressed', 'energy_meter_compressed')
ORDER BY hypertable_name, segmentby_column_index NULLS LAST, orderby_column_index;

-- name: baseline_chunks
-- Chunk time ranges of the uncompressed baseline, oldest first. The data is
-- copied one of these ranges at a time.
SELECT range_start, range_end
FROM timescaledb_information.chunks
WHERE hypertable_name = %(baseline)s
ORDER BY range_start;

-- name: copy_one_chunk
-- Copy exactly one chunk's time range from the cleaned baseline table.
INSERT INTO {target}
SELECT * FROM {baseline}
WHERE event_time >= %(range_start)s AND event_time < %(range_end)s
ORDER BY event_time, meter_id;

-- name: find_chunk
-- The chunk that was just filled in the target table.
SELECT format('%%I.%%I', chunk_schema, chunk_name) AS chunk
FROM timescaledb_information.chunks
WHERE hypertable_name = %(target)s AND range_start = %(range_start)s;

-- name: compress_one_chunk
SELECT compress_chunk(%(chunk)s::regclass);

-- name: compressed_chunk_list
-- Final state of every chunk in both tables.
SELECT hypertable_name, chunk_name, range_start, range_end, is_compressed
FROM timescaledb_information.chunks
WHERE hypertable_name IN ('energy_time_compressed', 'energy_meter_compressed')
ORDER BY hypertable_name, range_start;

-- name: compressed_ranges_match
-- Both tables must have the SAME time ranges compressed. Any row returned here
-- is a range that is compressed in one table but not in the other.
SELECT coalesce(t.range_start, m.range_start) AS range_start,
       t.is_compressed AS time_table_compressed,
       m.is_compressed AS meter_table_compressed
FROM (SELECT range_start, is_compressed FROM timescaledb_information.chunks
      WHERE hypertable_name = 'energy_time_compressed') t
FULL JOIN (SELECT range_start, is_compressed FROM timescaledb_information.chunks
           WHERE hypertable_name = 'energy_meter_compressed') m USING (range_start)
WHERE t.is_compressed IS DISTINCT FROM m.is_compressed;
