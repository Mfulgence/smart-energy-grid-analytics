# Smart Energy Grid Analytics: report template

Advanced Big Data Analytics, Assignment I. Group: `[names]`. Date: `[date]`.

**How to use this template**

- Keep the subsection order. Put each screenshot beside its subsection. Every
  screenshot must show the command, its result, the taskbar and the clock.
- `[YOURS: ...]` marks a value that depends on your machine or your run
  (timings, sizes, versions). Copy it from the file named beside it.
- Numbers written out in this template are properties of the common dataset.
  They are the same for every group, but still check them against your own
  output before submitting.
- Tables saved as `results/*.md` can be pasted directly.
- Where a subsection asks for a judgment, the template gives the structure
  and the reasoning to apply. The conclusion must follow your measurements.

---

## 1 Build the ingestion pipeline

### 1.1 Confirm the environment

Evidence: `sql/01_1a_create_database.sql`, `sql/01_1b_enable_timescaledb.sql`,
`s11_environment.py` -> `results/1_1_environment.md`.

Paste the environment table from `results/1_1_environment.md`. It covers CPU
model and cores, RAM, OS and version, storage type, Python, EMQX, PostgreSQL
and TimescaleDB versions, `shared_buffers`, `work_mem`,
`max_parallel_workers_per_gather`, `jit`, and how PostgreSQL runs.

State in one sentence: PostgreSQL runs `[YOURS: natively / in a container /
in a virtual machine]` with `[YOURS: CPU or RAM limits, or "no limits"]`.

Time zone: the database default and every session use `Africa/Kigali`. Daily
buckets are aligned to CAT midnight by passing the zone to `time_bucket`
(`time_bucket('1 day', event_time, 'Africa/Kigali')`).

Clock: the machine clock is synchronised (`[YOURS: NTP offset or OS sync
status]`). All recorded times are CAT.

Screenshots: running broker | database connection, extension and session time
zone | environment table.

### 1.2 Create the database structures

Evidence: `sql/01_2_create_tables.sql`, `s12_load_meters.py`.

**Data dictionary**

`energy_live` (regular table, pilot messages) and `energy_readings`
(hypertable partitioned by `event_time`, one-day chunks). Same eight columns:

| Column | PostgreSQL type | Meaning | Unit |
| --- | --- | --- | --- |
| `meter_id` | BIGINT | Ten-digit meter identifier, 1000000000 to 1000003999 | none |
| `event_time` | TIMESTAMPTZ | Start of the 15-minute measurement interval | timestamp (CAT) |
| `received_time` | TIMESTAMPTZ | Simulated arrival time of the reading. Not the database insert time | timestamp (CAT) |
| `power_kw` | DOUBLE PRECISION | Average power over the interval | kW |
| `voltage_v` | DOUBLE PRECISION | Voltage | V |
| `current_a` | DOUBLE PRECISION | Current | A |
| `frequency_hz` | DOUBLE PRECISION | Frequency | Hz |
| `energy_kwh` | DOUBLE PRECISION | Energy used during the interval, about `power_kw` x 0.25 h. Not a cumulative register | kWh |

`meters` (one row per meter, 4,000 rows):

| Column | PostgreSQL type | Meaning | Unit |
| --- | --- | --- | --- |
| `meter_id` | BIGINT, primary key | Meter identifier, joins to the reading tables | none |
| `region` | TEXT | Region 1 to Region 10, 400 meters each | none |
| `customer_type` | TEXT | residential, commercial or industrial | none |
| `base_power_kw` | DOUBLE PRECISION | Typical load of the customer | kW |
| `power_factor` | DOUBLE PRECISION | Ratio of real to apparent power, 0.95 | no unit |

Neither reading table has a primary key or unique constraint, so duplicate
readings are accepted at this stage. `energy_readings` has two non-unique
b-tree indexes: `(event_time DESC)` and `(meter_id, event_time DESC)`.

Result: `meters` contains 4,000 rows.

Screenshots: columns and types of the three tables | hypertable chunk
interval | 4,000-row count.

### 1.3 Capture and publish a pilot stream

Evidence: `s13_subscriber.py`, `s13_publisher.py`, `s13_pilot_counts.py` ->
`results/1_3_pilot_counts.md`.

Paste the four-count table. Expected on a healthy pipeline:

| Stage | Count | Target |
| --- | --- | --- |
| Dictionaries taken from the generator | 2,000 | 2,000 |
| Messages acknowledged by the broker (PUBACK) | 2,000 | 2,000 |
| Messages received by the subscriber | 2,000 | 2,000 |
| Rows committed in `energy_live` | 2,000 | 2,000 |

Topic `energy/meters/{meter_id}`, QoS 1, not retained. The subscriber was
started first on an empty table. The 2,000 messages include 6 deliberate
generator duplicates, stored as separate rows (1,994 distinct pairs).

If any count differed in an earlier attempt, state the size of the difference,
what the logs (`logs/publisher.log`, `logs/subscriber.log`) showed, what was
corrected, and that the pilot was repeated: `[YOURS, or "no difference
occurred"]`.

Screenshots: publisher completion and acknowledged count | subscriber received
count | stored count and sample rows.

---

## 2 Capture and prepare the historical dataset

### 2.1 Capture and load the complete stream

Evidence: `s21_capture_and_load.py` -> `results/2_1_capture_and_load.md`.

Route: generator -> CSV file -> `COPY` into `energy_readings`, in batches
(100,000 rows per file write, 500,000 rows per `COPY` and commit).

| Count | Measured | Expected |
| --- | --- | --- |
| Dictionaries consumed | 10,696,848 | 10,696,848 |
| CSV data rows | 10,696,848 | 10,696,848 |
| Rows committed in `energy_readings` | 10,696,848 | 10,696,848 |

| Timing | Seconds |
| --- | --- |
| File generation | `[YOURS]` |
| Database loading (first COPY to final commit) | `[YOURS]` |
| Total elapsed (start of generation to final commit) | `[YOURS]` |

Database checks: 4,000 distinct meters; earliest `event_time` 2026-09-01
00:00 CAT; latest 2026-09-28 23:45 CAT. Size including all chunks: table data
`[YOURS]`, indexes `[YOURS]`, combined `[YOURS]`.

Screenshots: completed generation | completed load | count agreement |
database checks.

### 2.2 Investigate data quality

Evidence: `s22_data_quality.py`, `sql/02_2_data_quality.sql` ->
`results/2_2_data_quality.md`.

| Entry | Measured | Expected |
| --- | --- | --- |
| planned_readings | 10,752,000 | 10,752,000 |
| emitted_readings | 10,696,848 | 10,696,848 |
| unique_readings | 10,643,735 | 10,643,735 |
| duplicate_readings | 53,113 | 53,113 |
| delayed_unique_readings | 213,090 | 213,090 |
| missing_readings | 108,265 | 108,265 |

| Measure | Formula | Value |
| --- | --- | --- |
| Missing | 100 x 108,265 / 10,752,000 | 1.0069 % |
| Duplicate | 100 x 53,113 / 10,643,735 | 0.4990 % |
| Delayed | 100 x 213,090 / 10,643,735 | 2.0020 % |
| Completeness | 100 x 10,643,735 / 10,752,000 | 98.9931 % |

Checks: 10,643,735 + 53,113 = 10,696,848 (emitted). 10,752,000 - 10,643,735 =
108,265 (missing). Delayed readings arrive 30 to 180 minutes after
`event_time`; on-time readings arrive at exactly 15 minutes.

Five meters with the most missing readings (of 2,688 planned each):

| meter_id | region | customer_type | missing |
| --- | --- | --- | --- |
| 1000003622 | Region 3 | commercial | 47 |
| 1000000106 | Region 7 | industrial | 45 |
| 1000000366 | Region 7 | commercial | 45 |
| 1000001259 | Region 10 | residential | 44 |
| 1000000189 | Region 10 | commercial | 43 |

Screenshots: diagnostic queries and results.

### 2.3 Clean and preserve a consistent benchmark

Evidence: `s23_clean.py`, `sql/02_3_clean_duplicates.sql` -> `results/2_3_clean.md`.

Method: rows sharing `(meter_id, event_time)` were compared on the six other
values. No conflicting pair was found (0), so one row per pair was kept and
the extra copies were deleted with a repeatable statement that numbers
identical rows with `row_number()` and deletes copies 2 and above by their
physical address (`tableoid`, `ctid`). Missing intervals were left as gaps.

| Measure | Before | After | Change |
| --- | --- | --- | --- |
| Row count | 10,696,848 | 10,643,735 | -53,113 |
| Sum of `energy_kwh` | 3,872,863.893 | 3,853,704.347 | -19,159.546 |

Final row count equals `expected_counts.unique_readings` and no duplicate
pair remains.

**Why missing readings must not become zero.** A missing reading means the
measurement did not arrive. It does not mean the customer consumed nothing.
Filling zeros would understate consumption and bias totals, averages and the
forecast downward, would create false "unusual drop" anomalies, and would make
completeness look like 100 % and hide the reporting problem. Keeping the gap
keeps the unknown as unknown.

Screenshots: cleaning completion | before-and-after results.

---

## 3 Compare chunk intervals

### 3.1 Create and verify three configurations

Evidence: `sql/03_1_chunk_tables.sql`, `s31_verify_chunks.py` ->
`results/3_1_verify_chunks.md`.

| Table | Chunk interval | Chunks | Rows | Meters |
| --- | --- | --- | --- | --- |
| `energy_readings_3h` | 3 hours | 225 | 10,643,735 | 4,000 |
| `energy_readings` | 1 day | 29 | 10,643,735 | 4,000 |
| `energy_readings_week` | 1 week | 5 | 10,643,735 | 4,000 |

All three have the same eight columns, the same two non-unique b-tree indexes
(`event_time DESC`; `meter_id, event_time DESC`), the same first and last
`event_time`, and sums of `power_kw` (15,414,817.388) and `energy_kwh`
(3,853,704.347) that agree within 0.001. Chunk boundaries follow UTC (02:00
CAT), which is why 28 CAT days occupy 29 one-day chunks.

Screenshots: chunk intervals | chunk counts and date ranges | indexes |
matching data checks.

### 3.2 Implement and time the five workloads

Evidence: `s32_benchmark.py`, `sql/03_2_workloads.sql` -> `results/3_2_summary.md`,
`results/3_2_timings.csv`, `results/3_2_plans.txt`.

Procedure: one machine (`[YOURS: machine id]`), one client (`[YOURS: Python
and psycopg versions]`), timer `time.perf_counter()` from statement submission
until the last result row was fetched. Settings unchanged, competing workloads
closed, background jobs paused, queries run sequentially. One warm-up then
five measured executions per query and table. **These are warm-cache
measurements.** PostgreSQL was not restarted and caches were not cleared.

Paste the timing table (median, minimum, maximum per query and table) and the
session seconds from `results/3_2_summary.md`. All results matched across the
three tables within 0.001: `[YOURS: confirm]`.

Screenshots: completed timing comparison | one `EXPLAIN (ANALYZE, BUFFERS)`
plan per configuration.

### 3.3 Explain the chunk results

For each query write three short parts. Keep what you observed apart from why
you think it happened.

| Query | Fastest interval | Median comparison | Explanation supported by evidence |
| --- | --- | --- | --- |
| Q1 one day, all meters | `[YOURS]` | `[YOURS: x ms vs y ms vs z ms]` | `[YOURS]` |
| Q2 one week, top ten intervals | `[YOURS]` | `[YOURS]` | `[YOURS]` |
| Q3 full period per meter | `[YOURS]` | `[YOURS]` | `[YOURS]` |
| Q4 one meter, one week | `[YOURS]` | `[YOURS]` | `[YOURS]` |
| Q5 full scan | `[YOURS]` | `[YOURS]` | `[YOURS]` |

Evidence you can cite (from 3.1 and the "Chunks touched" table of 3.2):

| Query | 3-hour chunks touched | 1-day chunks touched | 1-week chunks touched |
| --- | --- | --- | --- |
| Q1 | 9 of 225 | 2 of 29 | 1 of 5 |
| Q2, Q4 | 57 of 225 | 8 of 29 | 2 of 5 |
| Q3, Q5 | 225 | 29 | 5 |

Reasoning to apply, where your numbers support it:

- **Time-filtered queries (Q1, Q2).** Small chunks let the planner skip more
  data, because excluded chunks are never read. A weekly chunk that matches a
  one-day filter still holds a week of rows, so the query relies on the index
  or filters rows inside the chunk.
- **Unfiltered queries (Q3, Q5).** Every chunk is read whatever the interval,
  so nothing is saved by exclusion. What differs is the per-chunk overhead:
  more chunks means more planning, more scan nodes and more small aggregates
  to combine.
- **Single-meter query (Q4).** One index lookup per touched chunk, so the cost
  grows with the number of chunks the time range spans.

Sentence pattern: "Observation: for Q3 the weekly table had the lowest median
(`x` ms against `y` ms for 3-hour chunks, `y/x` times slower). Explanation: Q3
has no time filter, so all chunks are scanned; the plan shows 225 chunk scans
for the 3-hour table against 5 for the weekly table."

---

## 4 Compare compression strategies

### 4.1 Create the two compressed configurations

Evidence: `s41_load_and_compress.py`, `sql/04_1_compressed_tables.sql` ->
`results/4_1_load_and_compress.md`, `results/4_1_compression_log.csv`.

Chosen chunk interval: `[YOURS]` (baseline table `[YOURS]`), because
`[YOURS: reason from Section 3]`.

- `energy_time_compressed`: order by `event_time DESC`, no segmentation.
- `energy_meter_compressed`: order by `event_time DESC`, segment by `meter_id`.
- Policy on each: compress chunks whose end is more than 48 hours old. Both
  were paused until the 4.3 measurements were complete.
- Experiment start `[YOURS]`, cutoff = start - 48 hours = `[YOURS]`, the same
  for both tables.
- Data was copied one chunk at a time. Each chunk was compressed manually
  after it was fully loaded if its end preceded the cutoff. Compression was
  timed separately from loading.

The same chunk ranges are compressed in both tables: `[YOURS: n of n]`. Both
tables hold 10,643,735 rows and 4,000 meters with matching dates and sums.

Screenshots: both configurations | policies | compressed-chunk lists |
matching data checks.

### 4.2 Measure storage and compression cost

Evidence: `s42_storage_report.py` -> `results/4_2_storage.md`.

Paste both tables from `results/4_2_storage.md`: sizes (data, index, total) of
the baseline and the two compressed tables; and per strategy the compression
ratio, percentage saved, summed compression seconds, compressed chunks out of
total, and the percentage of rows in compressed chunks.

Formulas: ratio = baseline total / compressed total. Saved % = 100 x (baseline
minus compressed) / baseline. Compression cost = sum of chunk compression times,
loading excluded.

Screenshots: compression timings | storage statistics for both strategies.

### 4.3 Repeat the query comparison

Evidence: `s32_benchmark.py --label 4_3 ...`, `s43_compare.py`,
`jobs.py resume --kind compression` -> `results/4_3_compare.md`,
`results/4_3_plans.txt`.

Paste the five-configuration table and the improvement table from
`results/4_3_compare.md`. Improvement % = 100 x (baseline median - compressed
median) / baseline median; positive means faster. Warm-cache, same client and
timer as 3.2.

Screenshots: completed results | plans for both compressed tables | policies
enabled after measurement.

### 4.4 Select a storage configuration

1. **Effect of meter segmentation.** Compare Q4 (single meter) with Q1, Q2, Q3
   and Q5 (all meters) between the two compressed tables: `[YOURS: numbers]`.
   Reasoning to check against your plans: with `segmentby = meter_id` each
   compressed batch holds one meter, so Q4 decompresses only that meter's
   batches. Without segmentation every batch mixes all meters, so Q4 must
   decompress every batch in the time range. For queries across all meters,
   segmentation creates many small batches (one set per meter per chunk),
   which adds per-batch overhead.
2. **Recommendation.** Chunk interval `[YOURS]` with `[YOURS: strategy]`.
   Storage: `[YOURS: ratio and % saved]`. Queries: `[YOURS: the medians that
   matter for your workload]`.
3. **One cost or tradeoff.** `[YOURS: for example the compression time
   difference between the two strategies, or the query that became slower
   under the chosen strategy]`.

---

## 5 Investigate the utility data

### 5.1 Identify demand patterns

Evidence: `s51_demand_patterns.py` -> `results/5_1_demand_patterns.md`,
`5_1_daily_energy.png`, `5_1_weekly_energy.png`, `5_1_load_profile.png`.

Insert the daily chart and the weekly chart.

| Seven-day period | Energy (kWh) |
| --- | --- |
| 1 to 7 September | 934,199.06 |
| 8 to 14 September | 953,714.97 |
| 15 to 21 September | 973,230.03 |
| 22 to 28 September | 992,560.29 |

| Rank | Interval start (CAT) | Network demand (kW) |
| --- | --- | --- |
| 1 | Monday 28 September 13:00 | 7,993.69 |
| 2 | Monday 28 September 12:45 | 7,943.95 |
| 3 | Monday 28 September 13:15 | 7,943.64 |

**Patterns.** (1) A weekly rhythm: working days average 146,571 kWh, weekend
days 115,284 kWh, 21.3 % lower. (2) Steady growth: each seven-day period is
about 2 % above the previous one, 6.25 % from the first to the fourth.
(3) A daily shape: on working days demand peaks around 13:00, driven by
business-hours load, and stays high until about 19:00. At weekends the midday
peak disappears and the highest demand moves to about 18:00. Demand is lowest
between midnight and 04:00 on every day.

**Operational implications.** Capacity and staffing must cover the working-day
midday peak, not the average. The three highest intervals are all on the last
Monday, so with the present growth each new week is likely to set a new peak.
Planned maintenance fits best at weekends or at night, when demand is lowest.

**kW versus kWh.** kW is a rate: how much power the network must deliver at
one moment. It decides whether equipment is overloaded. kWh is an amount: power
accumulated over time. It decides how much energy is generated, bought and
billed. The peak interval drew 7,993.7 kW; over its 15 minutes that is
7,993.7 x 0.25 = 1,998.4 kWh. Demand is found by summing `power_kw` across
meters at one `event_time`. Consumption is found by summing `energy_kwh` over
time.

Screenshots: executed analysis | charts | peak-interval results.

### 5.2 Compare regions and customer types

Evidence: `s52_groups.py` -> `results/5_2_groups.md`.

Paste the region table and the customer-type table (total energy, registered
meters, energy per meter).

| Customer type | Meters | Energy (kWh) | Energy per meter (kWh) |
| --- | --- | --- | --- |
| industrial | 406 | 2,220,672.04 | 5,469.64 |
| commercial | 1,010 | 825,475.15 | 817.30 |
| residential | 2,584 | 807,557.16 | 312.52 |

**What remains after normalisation.**

- *Customer types.* Totals differ by a factor of 2.75 between the largest and
  smallest group. Per meter the gap widens to 17.5 times: an industrial meter
  uses about 17.5 times a residential one. Industrial customers are 10 % of
  meters and 58 % of energy. Residential customers are 65 % of meters and
  21 % of energy.
- *Regions.* Every region has 400 registered meters, so dividing by the meter
  count changes no ranking: Region 8 remains highest (1,258.7 kWh per meter)
  and Region 4 lowest (811.0), 55 % apart. The difference is explained by the
  customer mix: Region 8 has 61 industrial meters, Region 4 has 29.

**Implication.** Load, revenue and risk are concentrated in a small number of
industrial meters. A data gap or fault on an industrial meter matters far more
than on a residential one, and regional planning should follow the industrial
count, not the number of meters.

Screenshots: group counts | comparison results.

### 5.3 Assess reporting quality

Evidence: `s53_reporting_quality.py` -> `results/5_3_reporting_quality.md`.

Network completeness: 10,643,735 / 10,752,000 = 98.9931 %. Paste the regional
table: regions range from 98.9693 % (Region 6) to 99.0129 % (Region 8), so
losses are spread evenly and no region stands out.

| 21 September | Value |
| --- | --- |
| Energy from readings received by 22 Sept 00:00 CAT | 149,400.545 kWh |
| Energy from all arrivals (final) | 149,552.723 kWh |
| Difference | 152.178 kWh |
| Difference as % of the final total | 0.1018 % |

**Effects.** *Delayed readings* arrive 30 to 180 minutes late, so a total taken
at midnight misses 531 readings from the last hours of the day and is 0.10 %
too low. It corrects itself within three hours. *Missing readings* never
arrive: 3,964 of 384,000 planned readings for that day (1.03 %) are absent, so
even the final total slightly understates true consumption. A daily report
should therefore be labelled provisional until three hours after midnight and
should always be shown with its completeness.

Screenshots: completeness calculation | the two daily totals.

### 5.4 Investigate abnormal consumption

Evidence: `s54_anomalies.py` -> `results/5_4_anomalies.md`,
`5_4_example_demand_spike.png`, `5_4_example_unusual_drop.png`.

**Rule.** For each meter, each 15-minute time-of-day slot and each day type
(working day or weekend), the typical power is the median over the 28 days.
A reading is flagged when `power_kw` is at least 2.0 times (demand spike) or
at most 0.5 times (unusual drop) that typical value. Each flag identifies a
`meter_id` and an `event_time`.

**Reasons.** Comparing a meter only with itself at the same time of day and
day type removes the normal daily and weekly rhythm. The median is not moved
by a few abnormal readings. The thresholds follow from the measured spread of
normal readings: the central 99.98 % of ratios lie between 0.76 and 1.29, so
0.5 and 2.0 are far outside normal variation.

The rule was applied to the cleaned readings and the flags were stored before
`anomaly_events()` was called. Labels were used only for evaluation.

| Result | Value |
| --- | --- |
| Injected events | 40 |
| Detected | 40 of 40 |
| Missed | 0 of 40 |
| Flagged readings | 474 |
| False flags | 0 |
| False flags as % of readings outside injected intervals (10,643,261) | 0.000000 % |
| Percentage of meters affected by false flags | 0.000 % (0 of 4,000) |

**Missed events and false alarms.** None occurred. The injected events
multiply power by a large factor for three hours, which is far outside normal
variation, so a wide margin separates them from normal readings. This is the
easy case. Real anomalies that are smaller than a factor of two, or that build
up slowly, would be missed by these thresholds, and tightening them towards
the normal range (0.76 to 1.29) would start to produce false alarms. Readings
missing inside an event cannot be flagged at all: 474 of the 480 readings
planned in the 40 intervals were observed. The typical value is also computed
from the whole month, so in live use it would have to come from past weeks
only.

Screenshots: executed detection | flagged readings | comparison with injected
events.

### 5.5 Management recommendation (no more than 500 words)

Write this last. Structure and facts to draw on:

**Operational actions.**
- Plan capacity for the working-day midday peak: 7,993.7 kW on Monday 28
  September at 13:00, with weekly energy growing about 2 % per week.
- Prioritise industrial meters (10 % of meters, 58 % of energy) for
  monitoring and data-quality follow-up.
- Treat daily totals as provisional for three hours after midnight (0.10 %
  understatement on 21 September) and report completeness (98.99 %) with them.
- Run the anomaly rule (40 of 40 events detected, 0 false flags) as a daily
  check, with the typical values taken from past weeks.

**Storage and reporting configuration.** `[YOURS: chunk interval and
compression strategy from 4.4, with one measured benchmark result, its unit
and its baseline, for example "Q3 median fell from x ms on the uncompressed
one-day table to y ms"]`. Serve dashboards from the continuous aggregates:
`[YOURS: Aggregate dashboard median ms against Raw median ms from 7.4, and
the storage and refresh cost from 6.1]`.

**Forecast model.** Use it. On the test week the Ridge model has MAE 4.56 kWh
and RMSE 5.79 kWh per region-hour, against 42.71 kWh and 79.40 kWh for the
previous-day baseline: 89 % lower MAE. The gain comes almost entirely from
Saturday and Monday, where the baseline copies the wrong day type. State the
limits: the model was tested on one week, it needs the previous day's totals
to be complete at midnight, and about 1 % of readings are missing from every
total.

Check the word count: `[YOURS]` words.

---

## 6 Create and investigate continuous aggregates

### 6.1 Create the three aggregate views

Evidence: `sql/06_1_continuous_aggregates.sql`, `s61_refresh_aggregates.py`,
`sql/06_1_policies.sql` -> `results/6_1_aggregates.md`.

| View | Grouped by | Stored rows |
| --- | --- | --- |
| `agg_region_15min` | 15-minute bucket, region | 26,880 |
| `agg_region_hourly` | CAT hour, region | 6,720 |
| `agg_meter_daily` | CAT day, meter_id | 112,000 |

Each stores the bucket, the grouping key, sum of `energy_kwh`, sum of
`power_kw` and the reading count. The regional views use an inner join on
`meter_id` between `energy_readings` and `meters`. All three were created
empty with `timescaledb.materialized_only = TRUE` (real-time aggregation off).

Paste the refresh and storage table from `results/6_1_aggregates.md`: refresh
seconds `[YOURS]`, data and index size `[YOURS]` per view. These were measured
before the policies were added.

Policies: 3-day lookback, 1-hour end offset, 15-minute schedule. The offsets
are relative to the database clock, so the policy window lies in October and
would never populate the September data. That is why the whole period was
refreshed manually.

Screenshots: view definitions | sample populated rows | storage and initial
refresh | policy settings | background job status.

### 6.2 Test freshness and delayed arrivals

Evidence: `s62_freshness_test.py`, `sql/06_2_freshness_test.sql` ->
`results/6_2_freshness.md`.

Paste the recorded times (test time, H, H - 48 hours, the three event times)
and the stage comparison table from `results/6_2_freshness.md`.

| Stage | Older hour aggregate | Hour H aggregate |
| --- | --- | --- |
| Initial older-hour refresh, real-time off | 1 kWh, 1 row | no bucket returned |
| After both new inserts, before refresh, real-time off | 1 kWh, 1 row | no bucket returned |
| Real-time on, still before refresh | 1 kWh, 1 row | 2 kWh, 1 row |
| After manual refresh of both hours | 1.5 kWh, 2 rows | 2 kWh, 1 row |

Raw table after all inserts: 1.5 kWh and two rows in the older hour, 2 kWh and
one row in H.

**What became visible when.**

- After the first refresh only the older hour is materialised. Hour H has no
  bucket. An absent bucket is not a zero reading.
- After the two inserts nothing changes in the aggregate. With real-time off
  it returns only stored buckets.
- With real-time on, the aggregate adds raw rows newer than the last
  materialised point. Hour H is newer, so its 2 kWh appears. The late 0.5 kWh
  falls in an hour that is already materialised, behind that point, so it
  stays invisible and the older hour still shows 1 kWh.
- After refreshing both hours the aggregate equals the raw table.

**Which hours the 6.1 policy could refresh at the test time.** The window was
`[YOURS: now - 3 days]` to `[YOURS: now - 1 hour]`. The older hour (48 hours
back) lies inside it and would be refreshed, which is how late arrivals get
picked up. Hour H ends after the window end, so the policy would not yet
refresh it; it becomes eligible on a later run.

Screenshots: table and view definitions | inserts | real-time settings |
initial refresh | raw and aggregate results at each stage.

---

## 7 Build and compare dashboards

### 7.1 Raw dashboard and 7.2 Aggregate dashboard

Evidence: `s71_dashboard.py`, `dashboard_queries.py`,
`sql/07_dashboard_panels.sql`, `assets/`.

Tool: Plotly Dash. Both dashboards have the same five panels, layout and
filters (whole CAT days and a selected meter). Energy is labelled in kWh and
completeness in percent.

| Panel | Raw reads | Aggregate reads |
| --- | --- | --- |
| 1 Hourly regional energy | `energy_readings` joined to `meters` | `agg_region_hourly` |
| 2 Daily network energy | `energy_readings` | `agg_region_15min` |
| 3 Energy per seven-day period | `energy_readings` | `agg_region_15min` |
| 4 Daily energy of the selected meter | `energy_readings` | `agg_meter_daily` |
| 5 Completeness by region | `energy_readings` joined to `meters` | `agg_region_15min`, with `meters` for registered counts |

In Aggregate mode stored energy sums and reading counts are summed when
buckets are combined. Planned readings = registered meters x number of
15-minute intervals in the selected period.

Screenshots: Raw dashboard with all panels | Aggregate dashboard with all
panels | panel query definitions.

### 7.3 Verify matching results

Evidence: `s73_verify_dashboards.py` -> `results/7_3_verify_dashboards.md`,
`results/7_3_panel*.csv`.

Filters: 22 September 00:00 to 29 September 00:00 (exclusive), all regions,
meter 1000000000. Paste the check table. Expected compared rows: panel 1
1,680; panel 2 7; panel 3 1; panel 4 7; panel 5 10. Keys and reading counts
identical; maximum energy difference `[YOURS]` kWh (limit 0.001); maximum
completeness difference `[YOURS]` percentage points (limit 0.000001).

Screenshots: paired dashboard outputs | numerical checks for all five panels.

### 7.4 Measure performance and judge the tradeoff

Evidence: the **Run timing test** button on each dashboard,
`s74_timing_summary.py` -> `results/7_4_dashboard_timing.md`,
`results/7_4_dashboard_timings.csv`.

Method: same browser (`[YOURS]`), machine and connection for both modes.
Writes and background jobs paused. No query-result caching. One warm-up
refresh then ten measured refreshes per mode. Panel query duration measured
on the server with `time.perf_counter()`. Whole-dashboard time measured in the
browser with `performance.now()` from the refresh request until all five
panels finished rendering.

Paste the timing table (median, minimum, maximum per panel and for the whole
dashboard, both modes) and the aggregate cost table from
`results/7_4_dashboard_timing.md`.

**Judgment.** `[YOURS]`. Points to weigh: the whole-dashboard median in each
mode; the storage of the three views (`[YOURS]` MB) against the raw table
(`[YOURS]` MB); the initial refresh time (`[YOURS]` s) and after how many
refreshes it is repaid; which panel gained least (the single-meter panel 4 is
already an index lookup on the raw table, so it has little to gain); and the
freshness cost shown in 6.2, where aggregates show late data only after a
refresh.

Screenshots: completed timing results | comparison. Jobs resumed afterwards.

---

## 8 Forecast the next day

### 8.1 Prepare chronological data and features

Evidence: `s81_prepare_features.py`, `forecast_common.py`,
`sql/08_hourly_region_energy.sql` -> `results/8_1_prepare_features.md`.

Dataset: one row per region and CAT hour, 10 x 672 = 6,720 rows, no absent
hour. Each hourly total is built from 1,562 to 1,597 readings (1,600 when
complete). Targets are the observed totals, never filled or adjusted. An
absent hour would have been left empty and its dependent rows excluded.

| Split | Target dates | Rows before exclusions | Excluded | Retained |
| --- | --- | --- | --- | --- |
| Train | 1 to 14 September | 3,360 | 1,680 | 1,680 (8 to 14 September) |
| Validation | 15 to 21 September | 1,680 | 0 | 1,680 |
| Test | 22 to 28 September | 1,680 | 0 | 1,680 |

| Feature | Lag or window (hours) | Earliest usable target (CAT) |
| --- | --- | --- |
| `lag_24h` | 24 | 2 September 00:00 |
| `lag_48h` | 48 | 3 September 00:00 |
| `lag_168h` | 168 | 8 September 00:00 |
| `prev_day_mean` | window of 24 (previous CAT day) | 2 September 00:00 |
| `hour_of_day`, `day_of_week`, `region` | calendar and identifier | 1 September 00:00 |

Forecast origin: 00:00 at the start of the target day. The initial lookback is
168 hours, so training rows with targets on 1 to 7 September are excluded. The
same 1,680 training rows are used by every configuration. Scaling and encoding
are fitted on training rows only. Check: every lag source hour ends at or
before its forecast origin (0 violations; the closest is `lag_24h` for hour
23, which ends exactly at the origin).

Screenshots: dataset preparation | split sizes and dates | feature examples |
lag-source check.

### 8.2 Evaluate the previous-day baseline

Evidence: `s82_baseline.py` -> `results/8_2_baseline.md`.

1,680 predictions (7 days x 24 hours x 10 regions). MAE 42.708 kWh, RMSE
79.403 kWh. The error is concentrated on Saturday (135.7 kWh) and Monday
(139.5 kWh), where the previous day is a different day type. On the other
five days it is 3.8 to 5.3 kWh.

Screenshots: completed run | prediction count | sample predictions | metrics.

### 8.3 Train and evaluate one regression model

Evidence: `s83_train_model.py` -> `results/8_3_validation_comparison.md`.

Model: Ridge regression. Shared predictors: `lag_24h`, `lag_48h`, `lag_168h`,
`prev_day_mean`, `hour_of_day`, `day_of_week`, `region`.

| Configuration | Settings | Training rows | Validation rows | Validation MAE (kWh) | Validation RMSE (kWh) |
| --- | --- | --- | --- | --- | --- |
| R1 | Ridge(alpha=0.1) | 1,680 | 1,680 | 4.4316 | 5.6433 |
| R2 | Ridge(alpha=1.0) | 1,680 | 1,680 | 4.4399 | 5.6517 |
| R3 | Ridge(alpha=10.0) | 1,680 | 1,680 | 4.8184 | 6.1827 |
| R4 | Ridge(alpha=100.0) | 1,680 | 1,680 | 7.9553 | 11.7728 |

Selected: R1, the lowest validation MAE. The fitted model and its
preprocessing were saved and used unchanged for the 1,680 test predictions.
Lag values for later test days come from earlier completed days. The model was
not refitted.

(Confirm these figures against your own run; a different scikit-learn version
can change the last decimals.)

Screenshots: training completion | validation MAE per configuration | selected
settings | prediction count | sample test predictions.

### 8.4 Judge forecast usefulness

Evidence: `s84_evaluate.py` -> `results/8_4_evaluate.md`, `8_4_forecast_plot.png`.

| Scope | Baseline MAE | Model MAE | Baseline RMSE | Model RMSE |
| --- | --- | --- | --- | --- |
| All 1,680 observations | 42.708 | 4.559 | 79.403 | 5.791 |

Paste the per-region rows and the peak-hour table from
`results/8_4_evaluate.md`, and insert the forecast plot.

**Does the model improve on the baseline?** Yes. MAE falls by 89.3 % and RMSE
by 92.7 % overall, and by 88 % to 91 % in every region. The improvement is not
uniform across days: on Tuesday to Friday and on Sunday the two methods are
equally good (about 4 to 5 kWh), because the previous day is the same day
type. The model wins on Saturday and Monday, where the baseline is wrong by
about 136 to 139 kWh and the model by 3.6 to 4.9 kWh, because `lag_168h`
supplies the same weekday of the previous week.

**Are the errors useful for planning?** The model's MAE is 0.77 % of the mean
hourly regional consumption (590.8 kWh), small enough for day-ahead scheduling
at regional level.

**Peak errors.** At each region's highest test hour the model's absolute
error is 2.0 to 17.7 kWh, against up to 270 kWh for the baseline on the
Monday peaks. The model under-predicts 9 of the 10 peaks, and its mean
error at the peaks is -5.4 kWh. For planning, a small margin should be added
at peak hours.

**Missing readings.** About 1 % of readings are absent from every hourly
total, in targets and predictors alike. The model therefore forecasts
*observed* consumption, slightly below true consumption. An hour with unusual
losses would look like a drop in demand.

**Delayed arrivals in live use.** This offline test treats every hourly total
as final. In live operation, at 00:00 about 2 % of readings arrive 30 to 180
minutes late, so the last three hours of the previous day are still
incomplete. `lag_24h` for hours 21 to 23 and `prev_day_mean` would be slightly
too low at forecast time (the midnight total for 21 September was 0.10 % below
final). Options are to issue the forecast at 03:00, or to accept the small
bias.

**Limitations.** One training week and one test week of synthetic data with
very regular patterns. No holidays, weather or seasonal change were tested.

Screenshots: metric comparison | peak-hour results | forecast plot.

---

## 9 Submit the report and code

### 9.1 and 9.2

- GitHub repository: `[URL]`. ZIP contains the same final files.
- Both contain the unchanged generator (SHA-256 `6b16d6bb...cfff8`), the
  capture and ingestion programs, the SQL files, analysis and model code,
  recorded benchmark timings (`results/3_2_timings.csv`,
  `results/4_3_timings.csv`, `results/7_4_dashboard_timings.csv`), the
  validation comparison (`results/8_3_validation_comparison.md`), dashboard
  queries and configuration, and the environment record
  (`results/1_1_environment.md`).
- README gives the execution order and commands and explains how to regenerate
  and load the dataset. Passwords are placeholders in `.env.example`.
- Screenshot: the README pilot instructions run successfully with the four
  counts at 2,000.

### 9.3 Contributions

| Member | Student ID | Contribution |
| --- | --- | --- |
| `[name]` | `[id]` | `[contribution]` |
| `[name]` | `[id]` | `[contribution]` |
| `[name]` | `[id]` | `[contribution]` |
