# 8.1 Dataset and features

| feature       | kind                                 | lag / window length (hours) | earliest usable target timestamp (CAT) |
| ------------- | ------------------------------------ | --------------------------- | -------------------------------------- |
| lag_24h       | lag                                  | 24                          | 2026-09-02 00:00                       |
| lag_48h       | lag                                  | 48                          | 2026-09-03 00:00                       |
| lag_168h      | lag                                  | 168                         | 2026-09-08 00:00                       |
| prev_day_mean | window: mean of the previous CAT day | 24                          | 2026-09-02 00:00                       |
| hour_of_day   | calendar (0-23)                      | 0                           | 2026-09-01 00:00                       |
| day_of_week   | calendar (Monday=0 ... Sunday=6)     | 0                           | 2026-09-01 00:00                       |
| region        | identifier (one of 10)               | 0                           | 2026-09-01 00:00                       |

| split      | rows before exclusions | excluded (no lookback) | rows retained | first retained target | last retained target | split dates              |
| ---------- | ---------------------- | ---------------------- | ------------- | --------------------- | -------------------- | ------------------------ |
| train      | 3,360                  | 1,680                  | 1,680         | 2026-09-08 00:00      | 2026-09-14 23:00     | 2026-09-01 to 2026-09-14 |
| validation | 1,680                  | 0                      | 1,680         | 2026-09-15 00:00      | 2026-09-21 23:00     | 2026-09-15 to 2026-09-21 |
| test       | 1,680                  | 0                      | 1,680         | 2026-09-22 00:00      | 2026-09-28 23:00     | 2026-09-22 to 2026-09-28 |

| feature       | rows checked | smallest gap h | largest gap h | violations | result                                          |
| ------------- | ------------ | -------------- | ------------- | ---------- | ----------------------------------------------- |
| lag_24h       | 5,040        | 0              | 23            | 0          | OK                                              |
| lag_48h       | 5,040        | 24             | 47            | 0          | OK                                              |
| lag_168h      | 5,040        | 144            | 167           | 0          | OK                                              |
| prev_day_mean | 5,040        | 0              | 0             | 0          | OK (window = the 24 hours ending at the origin) |
