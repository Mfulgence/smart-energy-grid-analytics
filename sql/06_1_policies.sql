-- ============================================================================
-- Section 6.1 (step 3, second half)  Refresh policies
-- Executed by s61_refresh_aggregates.py AFTER the manual refresh was measured.
--
-- start_offset => 3 days      look back three days from "now"
-- end_offset   => 1 hour      stop one hour before "now"
-- schedule_interval => 15 min run every 15 minutes
--
-- Both offsets are relative to the DATABASE CLOCK. Today the window is
-- [now - 3 days, now - 1 hour], which lies in October. The September data is
-- far older than three days, so the policy alone would never populate it.
-- That is why the whole generated period was refreshed manually first.
-- ============================================================================

-- name: policy_15min
SELECT add_continuous_aggregate_policy('agg_region_15min',
           start_offset      => INTERVAL '3 days',
           end_offset        => INTERVAL '1 hour',
           schedule_interval => INTERVAL '15 minutes',
           if_not_exists     => TRUE) AS job_id;

-- name: policy_hourly
SELECT add_continuous_aggregate_policy('agg_region_hourly',
           start_offset      => INTERVAL '3 days',
           end_offset        => INTERVAL '1 hour',
           schedule_interval => INTERVAL '15 minutes',
           if_not_exists     => TRUE) AS job_id;

-- name: policy_daily
SELECT add_continuous_aggregate_policy('agg_meter_daily',
           start_offset      => INTERVAL '3 days',
           end_offset        => INTERVAL '1 hour',
           schedule_interval => INTERVAL '15 minutes',
           if_not_exists     => TRUE) AS job_id;

-- name: show_policies
-- Policy settings and background job status.
SELECT j.job_id,
       ca.view_name,
       j.schedule_interval::text        AS runs_every,
       j.config ->> 'start_offset'      AS start_offset,
       j.config ->> 'end_offset'        AS end_offset,
       j.scheduled                      AS enabled,
       s.job_status,
       s.last_run_status,
       s.next_start
FROM timescaledb_information.jobs j
JOIN timescaledb_information.continuous_aggregates ca
  -- depending on the TimescaleDB version the job is listed under the view
  -- name or under the hidden materialization hypertable: accept either
  ON j.hypertable_name IN (ca.view_name, ca.materialization_hypertable_name)
LEFT JOIN timescaledb_information.job_stats s ON s.job_id = j.job_id
WHERE j.proc_name = 'policy_refresh_continuous_aggregate'
ORDER BY ca.view_name;

-- name: view_settings
SELECT view_name, materialized_only, materialization_hypertable_name AS stored_in
FROM timescaledb_information.continuous_aggregates
WHERE view_name IN ('agg_region_15min', 'agg_region_hourly', 'agg_meter_daily')
ORDER BY view_name;

-- name: view_size
-- Size of the hidden hypertable that stores one view's rows.
SELECT ca.view_name,
       s.table_bytes + coalesce(s.toast_bytes, 0) AS data_bytes,
       s.index_bytes,
       s.total_bytes
FROM timescaledb_information.continuous_aggregates ca,
     LATERAL hypertable_detailed_size(
         format('%%I.%%I', ca.materialization_hypertable_schema,
                           ca.materialization_hypertable_name)::regclass) s
WHERE ca.view_name = %(view)s;
