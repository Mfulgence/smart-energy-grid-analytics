# Smart Energy Grid Analytics

Advanced Big Data Analytics, Assignment I (October 2026).

Readings from 4,000 smart meters are published through EMQX, stored in
TimescaleDB, cleaned, benchmarked under different chunk and compression
settings, analysed, aggregated, shown on two dashboards and used to forecast
next-day consumption.

This README is the execution guide. Follow the steps **in the order they are
numbered**. Each step says what it is for, the exact command, what you should
see, and which screenshot to take for the report.

---

## Contents

1. [How the project is organised](#1-how-the-project-is-organised)
2. [One-time setup](#2-one-time-setup)
3. [The steps, in order](#3-the-steps-in-order)
   - [Section 1: ingestion pipeline](#section-1-build-the-ingestion-pipeline)
   - [Section 2: historical dataset](#section-2-capture-and-prepare-the-historical-dataset)
   - [Section 3: chunk intervals](#section-3-compare-chunk-intervals)
   - [Section 4: compression](#section-4-compare-compression-strategies)
   - [Section 5: utility analysis](#section-5-investigate-the-utility-data)
   - [Section 6: continuous aggregates](#section-6-continuous-aggregates)
   - [Section 7: dashboards](#section-7-dashboards)
   - [Section 8: forecast](#section-8-forecast-the-next-day)
   - [Section 9: report and submission](#section-9-report-and-submission)
4. [Command list on one page](#4-command-list-on-one-page)
5. [Regenerating the dataset](#5-regenerating-the-dataset)
6. [Troubleshooting](#6-troubleshooting)

---

## 1. How the project is organised

| Item | What it is |
| --- | --- |
| `smart_meter_simulator.py` | The supplied generator. **Unchanged, byte for byte.** Never edit it. |
| `sNN_*.py` | One program per assignment step. `s12_...` belongs to subsection 1.2, `s54_...` to 5.4, and so on. |
| `sql/` | Every SQL statement used: table definitions, cleaning, the five benchmark queries, the continuous aggregates and the dashboard panel queries. File names start with the subsection number. |
| `run_sql.py` | Runs a `.sql` file and prints each statement followed by its result (so a screenshot shows command and output). |
| `common.py` | Small shared helpers: database connection, CAT clock, table printing, logging. |
| `jobs.py` | Pause, resume or list TimescaleDB background jobs (needed before and after timing). |
| `charts.py`, `forecast_common.py`, `dashboard_queries.py` | Shared code for charts, the forecast and the dashboards. |
| `assets/` | Dashboard style sheet and the browser timing script. |
| `results/` | **Created by your runs.** Every program saves what it printed (`.log`), report-ready tables (`.md`), recorded timings (`.csv`, `.json`) and charts (`.png`). |
| `logs/` | Fault logs of the MQTT publisher and subscriber. |
| `data/` | The generated CSV (about 1.1 GB). Not committed to Git. |
| `docs/Assignment_I_Report_Template.docx` | The report template in Word: subsection order, a paste-in box for every required screenshot, and yellow markers for values from your own runs. |
| `docs/REPORT_TEMPLATE.md` | The same template as plain text (readable on GitHub). |
| `.env.example` | Template for connection settings. Passwords are placeholders. |

Two things are true of every program:

- It prints the SQL it runs next to the result, with a start and finish line
  showing the time in CAT and the machine name.
- It writes the same output to `results/<step>.log`, so numbers can be copied
  into the report after the screenshot is taken.

### Where each deliverable is covered

| Subsection | Code | Output to use in the report |
| --- | --- | --- |
| 1.1 Environment | `sql/01_1a_*.sql`, `sql/01_1b_*.sql`, `s11_environment.py` | `results/1_1_environment.md` |
| 1.2 Structures | `sql/01_2_create_tables.sql`, `s12_load_meters.py` | terminal output, data dictionary in the report template |
| 1.3 Pilot stream | `s13_subscriber.py`, `s13_publisher.py`, `s13_pilot_counts.py` | `results/1_3_pilot_counts.md`, `logs/` |
| 2.1 Capture and load | `s21_capture_and_load.py` | `results/2_1_capture_and_load.md` |
| 2.2 Data quality | `sql/02_2_data_quality.sql`, `s22_data_quality.py` | `results/2_2_data_quality.md` |
| 2.3 Cleaning | `sql/02_3_clean_duplicates.sql`, `s23_clean.py` | `results/2_3_clean.md` |
| 3.1 Chunk configurations | `sql/03_1_chunk_tables.sql`, `sql/03_1_verify.sql`, `s31_verify_chunks.py` | `results/3_1_verify_chunks.md` |
| 3.2 Workload timing | `sql/03_2_workloads.sql`, `s32_benchmark.py` | `results/3_2_summary.md`, `3_2_timings.csv`, `3_2_plans.txt` |
| 3.3 Explanation | written answer | uses 3.1 and 3.2 outputs |
| 4.1 Compressed tables | `sql/04_1_compressed_tables.sql`, `s41_load_and_compress.py` | `results/4_1_load_and_compress.md`, `4_1_compression_log.csv` |
| 4.2 Storage and cost | `s42_storage_report.py` | `results/4_2_storage.md` |
| 4.3 Query comparison | `s32_benchmark.py --label 4_3`, `s43_compare.py`, `jobs.py` | `results/4_3_compare.md`, `4_3_timings.csv`, `4_3_plans.txt` |
| 4.4 Recommendation | written answer | uses 4.2 and 4.3 outputs |
| 5.1 Demand patterns | `sql/05_analysis.sql`, `s51_demand_patterns.py` | `results/5_1_demand_patterns.md`, three charts |
| 5.2 Regions and types | `sql/05_analysis.sql`, `s52_groups.py` | `results/5_2_groups.md`, two charts |
| 5.3 Reporting quality | `sql/05_analysis.sql`, `s53_reporting_quality.py` | `results/5_3_reporting_quality.md` |
| 5.4 Anomalies | `sql/05_analysis.sql`, `s54_anomalies.py` | `results/5_4_anomalies.md`, two charts |
| 5.5 Management recommendation | written answer (last) | uses 4, 5, 7 and 8 outputs |
| 6.1 Continuous aggregates | `sql/06_1_continuous_aggregates.sql`, `sql/06_1_policies.sql`, `s61_refresh_aggregates.py` | `results/6_1_aggregates.md` |
| 6.2 Freshness test | `sql/06_2_freshness_test.sql`, `s62_freshness_test.py` | `results/6_2_freshness.md` |
| 7.1 and 7.2 Dashboards | `s71_dashboard.py`, `dashboard_queries.py`, `sql/07_dashboard_panels.sql`, `assets/` | the running dashboards |
| 7.3 Matching results | `s73_verify_dashboards.py` | `results/7_3_verify_dashboards.md`, `7_3_panel*.csv` |
| 7.4 Dashboard timing | `assets/dashboard_timing.js`, `s74_timing_summary.py`, `jobs.py` | `results/7_4_dashboard_timing.md`, `7_4_dashboard_timings.csv` |
| 8.1 Data and features | `sql/08_hourly_region_energy.sql`, `forecast_common.py`, `s81_prepare_features.py` | `results/8_1_prepare_features.md` |
| 8.2 Baseline | `s82_baseline.py` | `results/8_2_baseline.md` |
| 8.3 Model | `s83_train_model.py` | `results/8_3_validation_comparison.md` |
| 8.4 Usefulness | `s84_evaluate.py` | `results/8_4_evaluate.md`, forecast plot |
| 9.1 to 9.3 Submission | this README, `docs/REPORT_TEMPLATE.md`, `.env.example` | report PDF, repository, ZIP |

### Screenshot rule

Each screenshot must show **the command, its result, the taskbar and the
clock**. Take a full-screen capture (not a cropped window), and keep the
terminal scrolled so the command line is visible. Where the output is longer
than one screen, take two captures.

---

## 2. One-time setup

### 2.1 What must already be installed

| Software | Version | Check |
| --- | --- | --- |
| Python | 3.10 to 3.13 | `python --version` |
| PostgreSQL with TimescaleDB | TimescaleDB 2.10 or later | `SELECT extversion FROM pg_extension` (after step 1.1) |
| EMQX | 5.x | `emqx ctl status` or the dashboard at http://localhost:18083 |
| A web browser | any current one | used for the dashboards |
| Free disk space | about 10 GB | |

The code was tested end to end with Python 3.13, PostgreSQL 16, TimescaleDB
2.30 and EMQX 5.8.

If EMQX or TimescaleDB is not installed, `docker-compose.yml` can start both
(`docker compose up -d`). It is optional and was not exercised during testing,
so prefer your course installation if you have one.

### 2.2 Install the Python packages

Open a terminal **in this folder** and run:

```
python -m pip install -r requirements.txt
```

### 2.3 Create your settings file

```
copy .env.example .env          (Windows)
cp .env.example .env            (macOS / Linux)
```

Open `.env` in a text editor and fill in:

- `PGPASSWORD`: the password of your PostgreSQL user.
- `PGUSER`, `PGHOST`, `PGPORT` if they differ from the defaults.
- `MQTT_USERNAME` / `MQTT_PASSWORD` only if your broker requires a login.
- `PG_RUNTIME`, `STORAGE_TYPE`, `EMQX_VERSION`: facts about your machine that
  the environment record needs (see step 1.1).

Leave `PGDATABASE=energy_grid`. `.env` is ignored by Git, so the real password
never reaches GitHub. Only `.env.example` with placeholders is committed.

### 2.4 Start the services

Start PostgreSQL and EMQX the way your installation does it (Windows Services,
`emqx start`, or `docker compose up -d`). Make sure the Windows clock is set to
synchronise automatically (Settings > Time & language > Date & time > Sync now).

---

## 3. The steps, in order

Timings and sizes depend on your machine. Counts do not: the generator
produces identical data for everyone, so the counts shown below must match
exactly.

## Section 1: Build the ingestion pipeline

### Step 1.1 Confirm the environment

**Goal:** one database for the whole assignment, TimescaleDB enabled, session
time zone Africa/Kigali, and a record of the machine.

```
python run_sql.py sql/01_1a_create_database.sql --db postgres
python run_sql.py sql/01_1b_enable_timescaledb.sql
python s11_environment.py
```

What each command does:

1. Creates the database `energy_grid`. It connects to the default `postgres`
   database, because a database cannot be created from inside itself.
2. Inside `energy_grid`: enables the TimescaleDB extension, sets the database
   time zone to `Africa/Kigali`, then prints the evidence: connected database,
   extension version, session time zone, the four settings
   (`shared_buffers`, `work_mem`, `max_parallel_workers_per_gather`, `jit`),
   and a demonstration that daily buckets start at CAT midnight when
   `time_bucket` is given the zone.
3. Collects CPU model, cores, RAM, OS, storage, Python, EMQX, PostgreSQL and
   TimescaleDB versions, the settings, how PostgreSQL runs, and a clock check.
   It also connects to EMQX, which proves the broker is running. The table is
   saved to `results/1_1_environment.md`.

**You should see:** `extension timescaledb`, `session_time_zone Africa/Kigali`,
`day_bucket_aligned_to_cat 2026-09-01 00:00:00+0200`, and `EMQX broker RUNNING`.

**Screenshots:** the running broker (EMQX dashboard or `emqx ctl status`), the
output of command 2 (connection, extension, time zone), the table from command 3.

> How daily buckets are aligned to CAT midnight: every daily query, view and
> panel uses `time_bucket('1 day', event_time, 'Africa/Kigali')`. Without the
> zone argument TimescaleDB would cut days at UTC midnight, which is 02:00 CAT.

### Step 1.2 Create the database structures

```
python run_sql.py sql/01_2_create_tables.sql
python s12_load_meters.py
```

1. Creates `energy_live` (regular table), `energy_readings` (hypertable on
   `event_time`, one-day chunks) and `meters` (primary key `meter_id`). Both
   reading tables have the same eight columns and no unique constraint, so
   duplicates are accepted. It adds two non-unique indexes on
   `energy_readings` (`event_time` and `meter_id, event_time`) and prints
   column names and types, the chunk interval and the indexes.
2. Imports the generator, calls `meter_metadata()` and inserts each of the
   4,000 dictionaries as one row of `meters`, then counts the rows.

**You should see:** `chunk_interval 1 day`, `meter_rows 4,000`, 400 meters in
each of the 10 regions.

**Screenshots:** column list of the three tables, the chunk interval, the
4,000-row count. The data dictionary is in `docs/REPORT_TEMPLATE.md`.

### Step 1.3 Capture and publish a pilot stream

This step needs **two terminals**.

Terminal A (start this first and leave it running):

```
python s13_subscriber.py
```

Wait until it prints `Waiting for messages`.

Terminal B:

```
python s13_publisher.py
```

When both have finished, in either terminal:

```
python s13_pilot_counts.py
```

How the pilot works:

- The **subscriber** empties `energy_live`, subscribes to `energy/meters/#` at
  QoS 1, parses each JSON message and inserts its eight fields in batches. It
  stops by itself after 2,000 messages.
- The **publisher** takes only the first 2,000 dictionaries from
  `iter_readings()`, converts each to JSON and publishes it to
  `energy/meters/<meter_id>` with QoS 1 and `retain=False`. It counts the
  broker acknowledgements (PUBACK).
- **`s13_pilot_counts.py`** shows the four counts in one table: taken from the
  generator, acknowledged by the broker, received by the subscriber, rows in
  `energy_live`.

**You should see:** `2,000` at all four stages. Six of those rows are the
generator's deliberate duplicates and are kept as separate rows.

**If a count differs:** the table shows the size of the difference. Open
`logs/publisher.log` and `logs/subscriber.log`: they record unacknowledged
messages, redelivered messages (DUP flag), parse errors and failed inserts.
Fix the cause, then repeat the three commands (the subscriber empties the
table again).

**Screenshots:** publisher completion with the acknowledged count, subscriber
received count, the four-count table and the sample rows.

---

## Section 2: Capture and prepare the historical dataset

### Step 2.1 Capture and load the complete stream

```
python s21_capture_and_load.py
```

Chosen route: **generator -> CSV file -> PostgreSQL COPY**.

1. Prints `dataset_info()` with the expected counts.
2. Phase A: walks a fresh `iter_readings()` iterator and writes
   `data/energy_readings.csv` in batches of 100,000 rows, printing progress.
   The full dataset is never held in memory.
3. Counts the data rows of the CSV file.
4. Phase B: empties `energy_readings` and loads the file with `COPY` in
   batches of 500,000 rows, committing each batch.
5. Compares dictionaries consumed, CSV rows and committed table rows with
   `expected_counts.emitted_readings`.
6. Reports file generation seconds, database loading seconds and total elapsed
   seconds, then the distinct meter count, first and last `event_time`, and
   the data, index and combined sizes.

**You should see:** all three counts equal `10,696,848`; `distinct_meters 4,000`;
earliest `2026-09-01 00:00`, latest `2026-09-28 23:45`. Expect several minutes.

**Screenshots:** end of generation, end of load, the count table, the timing
table, the database checks.

The pilot rows stay in `energy_live`. After this step is verified you may
delete `data/energy_readings.csv`.

### Step 2.2 Investigate data quality (before cleaning)

```
python s22_data_quality.py
```

Runs `sql/02_2_data_quality.sql`: groups the rows into unique
`(meter_id, event_time)` pairs, counts extra copies and delayed pairs, builds
the planned grid (4,000 meters x 2,688 intervals) to count missing pairs, lists
the five meters with the most missing readings, calculates the four percentages
and checks the two identities.

**You should see:**

| Entry | Count |
| --- | --- |
| planned_readings | 10,752,000 |
| emitted_readings | 10,696,848 |
| unique_readings | 10,643,735 |
| duplicate_readings | 53,113 |
| delayed_unique_readings | 213,090 |
| missing_readings | 108,265 |

Missing 1.0069 %, duplicates 0.4990 %, delayed 2.0020 %, completeness 98.9931 %.

**Screenshots:** each diagnostic query with its result, the comparison table.

### Step 2.3 Clean and preserve a consistent benchmark

```
python s23_clean.py
```

Runs `sql/02_3_clean_duplicates.sql`:

1. Row count and summed energy before cleaning.
2. Finds pairs that occur more than once and compares their six other values.
3. Stops without deleting if any copies disagree.
4. Deletes the extra copies in one transaction, keeping one row per pair.
   Identical rows are told apart by their physical address
   (`tableoid`, `ctid`); `row_number()` keeps copy 1 and deletes the rest.
5. Row count and energy after cleaning, and six verification checks.
6. `VACUUM ANALYZE`.

Missing intervals are left as gaps. The program can be run again safely: on a
clean table it deletes 0 rows.

**You should see:** `DELETE 53,113`, final row count `10,643,735`, zero
duplicate pairs remaining, all checks `OK`.

**Screenshots:** the delete completion, the before-and-after table, the checks.

---

## Section 3: Compare chunk intervals

### Step 3.1 Create and verify three configurations

```
python run_sql.py sql/03_1_chunk_tables.sql
python s31_verify_chunks.py
```

1. Creates `energy_readings_3h` (3-hour chunks) and `energy_readings_week`
   (1-week chunks), copies the cleaned rows into both, creates the same two
   indexes as on `energy_readings`, and runs `ANALYZE` on all three.
2. Prints each table's chunk interval, chunk count, date range and indexes,
   then the data check: row count, distinct meters, first and last
   `event_time`, sum of `power_kw`, sum of `energy_kwh`.

**You should see:** `10,643,735` rows and `4,000` meters in each table,
identical dates, sums within 0.001, status `MATCH`.

Chunk boundaries follow UTC, so a one-day chunk runs from 02:00 CAT to 02:00
CAT. The 28 CAT days therefore occupy 29 one-day chunks, 225 three-hour chunks
and 5 weekly chunks.

**Screenshots:** chunk intervals, chunk counts and ranges, indexes, the
matching data check.

### Step 3.2 Implement and time the five workloads

Close other programs first. Then:

```
python jobs.py pause
python s32_benchmark.py
```

`s32_benchmark.py` runs Q1 to Q5 from `sql/03_2_workloads.sql` on the three
hypertables. Only the table name changes. For each query and table it runs
one warm-up and five measured executions, sequentially, on one connection.

- **Client:** Python with psycopg 3 (the exact versions are printed).
- **Timer:** `time.perf_counter()`, from submitting the statement until the
  last result row has been fetched.
- **Cache state:** warm. PostgreSQL is not restarted and caches are not
  cleared.

It prints the result check (each table must return the same rows within
0.001), the median, minimum and maximum per query and table, the fastest table
per query, the session seconds, one `EXPLAIN (ANALYZE, BUFFERS)` plan per
configuration, and how many chunks each plan touched.

Saved files: `results/3_2_timings.csv` (every run with CAT start, CAT end,
duration and machine), `results/3_2_summary.md`, `results/3_2_plans.txt`
(all 15 plans).

To print the plan of a different query on screen:
`python s32_benchmark.py --plan-query Q4`. This repeats the whole benchmark.

**Screenshots:** the timing comparison, and one plan per configuration.

### Step 3.3 Explain the chunk results

No command. Use the "Median ms per table" and "Chunks touched" tables from
step 3.2. `docs/REPORT_TEMPLATE.md` gives the structure: for each query name
the fastest interval, compare the medians with numbers, then explain using
chunk counts, the time filter or the plan, keeping observation and
explanation in separate sentences.

---

## Section 4: Compare compression strategies

### Step 4.1 Create the two compressed configurations

Choose one chunk interval from Section 3 and name its table:

```
python s41_load_and_compress.py --baseline energy_readings
```

Use `energy_readings_3h` or `energy_readings_week` instead if you chose that
interval. The named table is the uncompressed baseline for all of Section 4.

What the program does:

1. Records the experiment start time and one cutoff = start minus 48 hours.
2. Creates `energy_time_compressed` and `energy_meter_compressed`, empty, with
   the chosen interval, the same columns and the same indexes.
3. Sets compression: both order by `event_time DESC`; only
   `energy_meter_compressed` is segmented by `meter_id`.
4. Adds a "compress chunks older than 48 hours" policy to each table and
   pauses both.
5. Copies the cleaned data **one chunk at a time**. After each chunk is loaded
   it is compressed manually if its end is before the cutoff. Load time and
   compression time are measured separately for every chunk.
6. Lists the compressed chunks, checks that the same ranges are compressed in
   both tables, and repeats the 3.1 data checks.

Because the data is from September and the experiment runs in October, every
chunk is older than the cutoff and is compressed.

**Screenshots:** both configurations and their settings, the paused policies,
the compressed-chunk list, the matching data checks.

### Step 4.2 Measure storage and compression cost

```
python s42_storage_report.py
```

Reports data, index and total size of the baseline and both compressed tables,
the compression ratio, percentage saved, summed compression seconds (loading
excluded), compressed chunks out of total chunks, and the percentage of rows
held in compressed chunks.

**Screenshots:** the size table and the compression result table.

### Step 4.3 Repeat the query comparison

The compression policies are still paused from step 4.1. Then:

```
python s32_benchmark.py --label 4_3 --tables energy_time_compressed energy_meter_compressed --reference energy_readings --plan-query Q4
python s43_compare.py
python jobs.py resume --kind compression
```

Replace `energy_readings` after `--reference` with your baseline table if you
chose another interval.

1. The same benchmark procedure as 3.2 on the two compressed tables. Their
   results are checked against the baseline table.
2. Merges the 3.2 and 4.3 results into one comparison of all five
   configurations and calculates
   `improvement % = 100 x (baseline median - compressed median) / baseline median`.
   Positive means faster.
3. Resumes the two compression policies and prints their status.

**Screenshots:** the five-configuration comparison, the plans of both
compressed tables, the enabled policies.

### Step 4.4 Select a storage configuration

No command. Use the tables from 4.2 and 4.3. Q4 is the single-meter workload;
Q1, Q2, Q3 and Q5 run across all meters. See `docs/REPORT_TEMPLATE.md`.

---

## Section 5: Investigate the utility data

All of Section 5 reads the cleaned `energy_readings` and `meters`. The SQL is
in `sql/05_analysis.sql`.

### Step 5.1 Identify demand patterns

```
python s51_demand_patterns.py
```

Energy per CAT day, totals for the four seven-day periods, the three highest
15-minute demand intervals, and the average load profile by hour. Charts:
`results/5_1_daily_energy.png`, `5_1_weekly_energy.png`, `5_1_load_profile.png`.

**You should see:** the highest interval on 28 September at 13:00 CAT with
about 7,993.7 kW.

### Step 5.2 Compare regions and customer types

```
python s52_groups.py
```

Energy total, registered meter count and energy per meter, by region and by
customer type, plus the customer mix of each region. Charts:
`5_2_region_per_meter.png`, `5_2_type_per_meter.png`.

### Step 5.3 Assess reporting quality

```
python s53_reporting_quality.py
```

Completeness for the network and each region, and the 21 September total
counted twice: readings received by 22 September 00:00, and all arrivals.

### Step 5.4 Investigate abnormal consumption

```
python s54_anomalies.py
```

The rule, stated at the top of the file: for each meter, 15-minute slot and
day type (working day or weekend) the typical power is the median over the 28
days. A reading is flagged when it is at least 2.0 times or at most 0.5 times
that typical value. The flags are created first and stored in the table
`anomaly_flags`. Only then is `anomaly_events()` called to evaluate them.

It reports detected and missed events out of 40, false flags as a count and
as a percentage of readings outside injected intervals, and the percentage of
meters affected by false flags. Charts: `5_4_example_demand_spike.png`,
`5_4_example_unusual_drop.png`.

**Screenshots for 5.1 to 5.4:** the executed analysis, the charts and result
tables.

### Step 5.5 Write the management recommendation

Written last, after Sections 6 to 8. See `docs/REPORT_TEMPLATE.md`.

---

## Section 6: Continuous aggregates

### Step 6.1 Create the three aggregate views

```
python run_sql.py sql/06_1_continuous_aggregates.sql
python s61_refresh_aggregates.py
```

1. Creates three empty continuous aggregates over `energy_readings`:
   `agg_region_15min` (15-minute bucket and region), `agg_region_hourly` (CAT
   hour and region), `agg_meter_daily` (CAT day and meter). The regional views
   inner-join `meters` on `meter_id`. Each stores the bucket, its key, the sum
   of `energy_kwh`, the sum of `power_kw` and the reading count. Real-time
   aggregation is off (`materialized_only = TRUE`).
2. For each view: refreshes the whole generated period manually, reports the
   refresh seconds and the stored data and index size. **After** all three
   measurements it adds the refresh policies (3-day lookback, 1-hour end
   offset, every 15 minutes) and prints the view settings, sample rows, a
   check that the aggregates add up to the raw table, and the job status.

The policy offsets are relative to today's clock, so the policies alone would
never reach the September data. That is why the manual refresh comes first.

**Screenshots:** the view definitions, sample rows, the storage and refresh
table, the policy settings and job status.

### Step 6.2 Test freshness and delayed arrivals

```
python s62_freshness_test.py
```

Creates a separate test hypertable and an hourly aggregate with real-time
aggregation off and no policy. It records the test time, H (start of the most
recent completed CAT hour) and H minus 48 hours, then walks through the four
stages: initial refresh, two new inserts, real-time on, refresh of both hours.
At each stage it queries the raw table and the aggregate and compares the
result with the expected table from the assignment.

**You should see:** `as expected YES` for all four stages.

**Screenshots:** table and view definitions, the inserts, the real-time
setting, and the raw and aggregate results at each stage.

---

## Section 7: Dashboards

Tool: Plotly Dash. One program serves both dashboards.

### Steps 7.1 and 7.2 Build the Raw and Aggregate dashboards

```
python s71_dashboard.py
```

Leave it running and open:

- http://localhost:8050/raw (dashboard **Raw**, reads `energy_readings`)
- http://localhost:8050/aggregate (dashboard **Aggregate**, reads the views)

Both have the same five panels, layout and filters (a range of whole CAT days
and a meter ID):

| Panel | Content | Raw source | Aggregate source |
| --- | --- | --- | --- |
| 1 | Hourly regional energy (kWh) | `energy_readings` + `meters` | `agg_region_hourly` |
| 2 | Daily network energy (kWh) | `energy_readings` | `agg_region_15min` |
| 3 | Energy per seven-day period (kWh) | `energy_readings` | `agg_region_15min` |
| 4 | Daily energy of the selected meter (kWh) | `energy_readings` | `agg_meter_daily` |
| 5 | Completeness by region (%) | `energy_readings` + `meters` | `agg_region_15min` + `meters` |

The panel queries are in `sql/07_dashboard_panels.sql`. To print them for the
"panel query definitions" screenshot, in a second terminal:

```
python s73_verify_dashboards.py --show-queries
```

**Screenshots:** each running dashboard with all five panels, and the panel
queries.

### Step 7.3 Verify matching results

In a second terminal (the dashboard may stay running):

```
python s73_verify_dashboards.py
```

Runs the Raw and the Aggregate query of every panel for 22 September 00:00 to
29 September 00:00 (exclusive), all regions, meter 1000000000. It exports the
data behind each panel to `results/7_3_panel<N>_<mode>.csv`, matches rows by
bucket, region or meter, and reports the compared row count and the largest
absolute difference.

**You should see:** `PASS` for all five panels (1,680 / 7 / 1 / 7 / 10 rows).

**Screenshots:** both dashboards with the same filters, and the check table.

### Step 7.4 Measure performance

```
python jobs.py pause
```

In the browser, with the default filters (22 to 28 September, meter
1000000000):

1. Open http://localhost:8050/raw and press **Run timing test**. Wait for the
   result table under the panels.
2. Open http://localhost:8050/aggregate in the same browser and press
   **Run timing test**.

Then in the terminal:

```
python s74_timing_summary.py
python jobs.py resume
```

How it is measured:

- The button performs one warm-up refresh and ten measured refreshes.
- **Panel query duration:** measured on the server with `time.perf_counter()`
  around each SQL statement.
- **Whole dashboard:** measured in the browser with `performance.now()`, from
  the refresh request until the last of the five panels has finished drawing.
- No query results are cached. Every refresh runs all five queries again.
- Every refresh is appended to `results/7_4_dashboard_timings.csv`.

`s74_timing_summary.py` prints the median, minimum and maximum per panel and
for the whole dashboard in both modes, next to the aggregate storage and
initial refresh cost from step 6.1.

**Screenshots:** the timing table on each dashboard, and the summary.

Stop the dashboard with Ctrl+C when finished.

---

## Section 8: Forecast the next day

Hourly regional consumption in kWh, forecast at 00:00 CAT for the 24 hours of
that day.

### Step 8.1 Prepare chronological data and features

```
python s81_prepare_features.py
```

Builds one row per region and CAT hour (6,720 rows), checks for absent hours,
adds the features, reports the splits and exclusions, and proves that every
lag source hour ends at or before its forecast origin.

| Feature | Lag or window | Earliest usable target |
| --- | --- | --- |
| `lag_24h` | 24 hours | 2 Sept 00:00 |
| `lag_48h` | 48 hours | 3 Sept 00:00 |
| `lag_168h` | 168 hours | 8 Sept 00:00 |
| `prev_day_mean` | mean of the previous CAT day (24 hours) | 2 Sept 00:00 |
| `hour_of_day`, `day_of_week`, `region` | calendar and identifier | 1 Sept 00:00 |

**You should see:** train 3,360 rows before exclusions, 1,680 excluded,
1,680 retained; validation 1,680; test 1,680; zero violations in the lag check.

### Step 8.2 Evaluate the previous-day baseline

```
python s82_baseline.py
```

Predicts each test hour with the same hour of the previous day.
**You should see:** 1,680 predictions, MAE about 42.71 kWh, RMSE about 79.40 kWh.

### Step 8.3 Train and evaluate one regression model

```
python s83_train_model.py
```

Ridge regression, four configurations (alpha 0.1, 1, 10, 100) trained on the
same 1,680 training rows. Scaling and one-hot encoding are fitted on training
rows only. The configuration with the lowest validation MAE is saved
(`results/8_3_frozen_model.joblib`) and then used unchanged for the 1,680 test
predictions.

### Step 8.4 Judge forecast usefulness

```
python s84_evaluate.py
```

MAE and RMSE for baseline and model over all test observations and per
region, the peak hour of each region with both predictions and absolute
errors, MAE by test day, and the plot `results/8_4_forecast_plot.png`.
Use `--region "Region 8"` to plot another region.

**Screenshots for Section 8:** each run with its tables, and the forecast plot.

---

## Section 9: Report and submission

1. Open `docs/Assignment_I_Report_Template.docx` in Word. Paste each
   screenshot into its box, replace every yellow marker with your value from
   `results/*.md`, delete the yellow note on the first page, update the
   contents list (right-click > Update Field) and export one PDF
   (File > Save As > PDF).
2. Create the GitHub repository and a ZIP with the same files. Both must
   contain the unchanged generator, the programs, `sql/`, `assets/`,
   `results/` (recorded timings, validation comparison, environment record),
   this README and `.env.example`. They must not contain `.env` or `data/`.
3. Check the generator is unchanged. Its SHA-256 must be
   `6b16d6bb3191e528844d0ec75656096d8bfb2e92c99f83e2b75d586bf21cfff8`:

   ```
   certutil -hashfile smart_meter_simulator.py SHA256      (Windows)
   sha256sum smart_meter_simulator.py                      (Linux / macOS)
   ```
4. Run the pilot once more from this README (step 1.3) and screenshot the four
   counts for 9.2.
5. Fill in the contributions table (9.3) in the report.

---

## 4. Command list on one page

```
# Section 1
python run_sql.py sql/01_1a_create_database.sql --db postgres
python run_sql.py sql/01_1b_enable_timescaledb.sql
python s11_environment.py
python run_sql.py sql/01_2_create_tables.sql
python s12_load_meters.py
python s13_subscriber.py            # terminal A, start first
python s13_publisher.py             # terminal B
python s13_pilot_counts.py

# Section 2
python s21_capture_and_load.py
python s22_data_quality.py
python s23_clean.py

# Section 3
python run_sql.py sql/03_1_chunk_tables.sql
python s31_verify_chunks.py
python jobs.py pause
python s32_benchmark.py

# Section 4  (replace energy_readings if you chose another interval)
python s41_load_and_compress.py --baseline energy_readings
python s42_storage_report.py
python s32_benchmark.py --label 4_3 --tables energy_time_compressed energy_meter_compressed --reference energy_readings --plan-query Q4
python s43_compare.py
python jobs.py resume --kind compression

# Section 5
python s51_demand_patterns.py
python s52_groups.py
python s53_reporting_quality.py
python s54_anomalies.py

# Section 6
python run_sql.py sql/06_1_continuous_aggregates.sql
python s61_refresh_aggregates.py
python s62_freshness_test.py

# Section 7
python s71_dashboard.py             # leave running, open /raw and /aggregate
python s73_verify_dashboards.py --show-queries
python s73_verify_dashboards.py
python jobs.py pause
#   press "Run timing test" on /raw, then on /aggregate
python s74_timing_summary.py
python jobs.py resume

# Section 8
python s81_prepare_features.py
python s82_baseline.py
python s83_train_model.py
python s84_evaluate.py
```

---

## 5. Regenerating the dataset

The full dataset is not stored in the repository. To rebuild it on any machine:

```
python run_sql.py sql/01_1a_create_database.sql --db postgres
python run_sql.py sql/01_1b_enable_timescaledb.sql
python run_sql.py sql/01_2_create_tables.sql
python s12_load_meters.py
python s21_capture_and_load.py
python s23_clean.py
```

`s21_capture_and_load.py` regenerates `data/energy_readings.csv` from the
generator and reloads it. If the CSV still exists, add `--reuse-csv` to skip
generation. The generator is deterministic, so the result is the same
10,696,848 emitted rows and 10,643,735 cleaned rows every time.

To start over completely, drop the database first:

```
python run_sql.py --db postgres -c "DROP DATABASE energy_grid WITH (FORCE)"
```

---

## 6. Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `connection failed` or `password authentication failed` | PostgreSQL is not running, or `.env` has the wrong host, port, user or password. |
| `extension "timescaledb" is not available` | TimescaleDB is not installed for this PostgreSQL, or `shared_preload_libraries = 'timescaledb'` is missing from `postgresql.conf`. Add it and restart PostgreSQL. |
| `EMQX broker DOWN` or `ConnectionRefusedError` in the pilot | EMQX is not running, or `MQTT_HOST` / `MQTT_PORT` in `.env` are wrong. |
| Publisher finishes but the subscriber received 0 | The subscriber was started after the publisher. Start the subscriber first and wait for `Waiting for messages`. |
| Pilot `Connection refused: Not authorized` | The broker requires a login. Set `MQTT_USERNAME` and `MQTT_PASSWORD` in `.env`. |
| `database "energy_grid" already exists` | Not an error. The runner prints a notice and continues. |
| `relation ... already exists` in step 3.1 or 6.1 | Not expected: those files drop and recreate their objects. Re-run the file from the top. |
| Benchmark prints `WARNING: background job(s) still scheduled` | Run `python jobs.py pause`, then repeat the benchmark. |
| Step 4.1 leaves some chunks uncompressed | Their end is newer than the cutoff (start minus 48 hours). With September data in October this does not happen; it is reported in the output if it does. |
| Continuous aggregate with a join is rejected | Joins in continuous aggregates need TimescaleDB 2.10 or later. Check the version from step 1.1. |
| Dashboard page stays empty | Step 6.1 has not been run (Aggregate needs the views), or the terminal running `s71_dashboard.py` shows a database error. |
| `Address already in use` when starting the dashboard | Another program uses port 8050, or the dashboard is already running in another terminal. |
| Strange characters in the terminal on Windows | Run `chcp 65001` once in that terminal. |
