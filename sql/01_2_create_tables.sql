-- ============================================================================
-- Section 1.2  Create the three database structures
--     python run_sql.py sql/01_2_create_tables.sql
-- Safe to run more than once (IF NOT EXISTS everywhere).
-- ============================================================================

-- ---------------------------------------------------------------------------
-- energy_live : a REGULAR PostgreSQL table.
-- It receives the 2,000 pilot messages that travel through MQTT in 1.3.
-- No primary key and no unique constraint: the generator deliberately emits
-- duplicate readings and 1.2 says duplicates must be allowed at this stage.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS energy_live (
    meter_id      BIGINT           NOT NULL,  -- ten-digit meter identifier
    event_time    TIMESTAMPTZ      NOT NULL,  -- START of the 15-minute interval
    received_time TIMESTAMPTZ      NOT NULL,  -- simulated arrival time (not insert time)
    power_kw      DOUBLE PRECISION,           -- average power over the interval, kW
    voltage_v     DOUBLE PRECISION,           -- volts
    current_a     DOUBLE PRECISION,           -- amperes
    frequency_hz  DOUBLE PRECISION,           -- hertz
    energy_kwh    DOUBLE PRECISION            -- energy used in the interval, kWh
);

-- ---------------------------------------------------------------------------
-- energy_readings : same eight columns, turned into a TimescaleDB HYPERTABLE.
-- A hypertable looks like one table but is stored as many smaller tables
-- called chunks. Here each chunk holds one day of event_time.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS energy_readings (
    meter_id      BIGINT           NOT NULL,
    event_time    TIMESTAMPTZ      NOT NULL,
    received_time TIMESTAMPTZ      NOT NULL,
    power_kw      DOUBLE PRECISION,
    voltage_v     DOUBLE PRECISION,
    current_a     DOUBLE PRECISION,
    frequency_hz  DOUBLE PRECISION,
    energy_kwh    DOUBLE PRECISION
);

-- create_default_indexes => FALSE because we create the two indexes ourselves
-- below, with explicit names and sort orders, so that all hypertables compared
-- in Sections 3 and 4 have exactly the same index definitions.
SELECT create_hypertable(
    'energy_readings',
    'event_time',
    chunk_time_interval    => INTERVAL '1 day',
    create_default_indexes => FALSE,
    if_not_exists          => TRUE
);

-- Two NON-UNIQUE b-tree indexes (non-unique so duplicates are still accepted):
--   1. event_time                -> time-range filters across all meters
--   2. meter_id, then event_time -> one meter over a time range
CREATE INDEX IF NOT EXISTS energy_readings_time_idx
    ON energy_readings USING btree (event_time DESC);
CREATE INDEX IF NOT EXISTS energy_readings_meter_time_idx
    ON energy_readings USING btree (meter_id, event_time DESC);

-- ---------------------------------------------------------------------------
-- meters : one row of descriptive metadata per meter (4,000 rows).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS meters (
    meter_id      BIGINT PRIMARY KEY,         -- joins to the reading tables
    region        TEXT,                       -- 'Region 1' ... 'Region 10'
    customer_type TEXT,                       -- residential / commercial / industrial
    base_power_kw DOUBLE PRECISION,           -- typical load of this customer, kW
    power_factor  DOUBLE PRECISION            -- ratio, no unit (always 0.95)
);

-- ---- Evidence for the 1.2 screenshots --------------------------------------

-- Column names and types of all three tables.
SELECT table_name, ordinal_position AS pos, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('energy_live', 'energy_readings', 'meters')
ORDER BY table_name, ordinal_position;

-- energy_readings is a hypertable partitioned by event_time in one-day chunks.
SELECT hypertable_name, column_name AS partition_column, time_interval::text AS chunk_interval
FROM timescaledb_information.dimensions
WHERE hypertable_name = 'energy_readings';

-- energy_live is NOT a hypertable (it must not appear in this list).
SELECT hypertable_name FROM timescaledb_information.hypertables ORDER BY hypertable_name;

-- Indexes on the hypertable.
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public' AND tablename = 'energy_readings'
ORDER BY indexname;
