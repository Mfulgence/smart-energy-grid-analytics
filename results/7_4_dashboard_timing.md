# 7.4 Dashboard timing (10 measured refreshes after 1 warm-up, ms)

| measurement (ms)                                     | Raw median | Raw min | Raw max | Aggregate median | Aggregate min | Aggregate max | Raw / Aggregate |
| ---------------------------------------------------- | ---------- | ------- | ------- | ---------------- | ------------- | ------------- | --------------- |
| Panel 1 query: hourly regional energy                | 2,254.5    | 1,924.6 | 2,524.4 | 16.4             | 12.0          | 80.7          | 137.1 x         |
| Panel 2 query: daily network energy                  | 2,174.7    | 1,699.5 | 4,534.4 | 38.4             | 19.7          | 70.4          | 56.7 x          |
| Panel 3 query: seven-day periods                     | 5,150.1    | 2,247.0 | 6,257.8 | 43.5             | 18.0          | 68.9          | 118.3 x         |
| Panel 4 query: selected meter daily                  | 4.3        | 4.0     | 8.1     | 25.6             | 0.9           | 86.1          | 0.2 x           |
| Panel 5 query: completeness by region                | 2,076.6    | 1,867.1 | 3,164.1 | 14.8             | 6.3           | 86.9          | 140.6 x         |
| Whole dashboard: refresh until all 5 panels rendered | 5,203.1    | 3,757.0 | 6,312.4 | 216.7            | 166.0         | 291.7         | 24.0 x          |

| continuous aggregate | stored rows | storage MB (data + index) | initial refresh s |
| -------------------- | ----------- | ------------------------- | ----------------- |
| agg_region_15min     | 26,880      | 4.15                      | 29.19             |
| agg_region_hourly    | 6,720       | 1.23                      | 38.11             |
| agg_meter_daily      | 112,000     | 12.55                     | 27.35             |
| TOTAL                | 145,600     | 17.94                     | 94.65             |
