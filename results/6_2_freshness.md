# 6.2 Freshness and delayed arrivals

| Recorded time                                        | Value                       |
| ---------------------------------------------------- | --------------------------- |
| Actual test time (CAT)                               | 2026-10-13 13:58:10.749 CAT |
| H = start of most recent completed CAT hour          | 2026-10-13 12:00:00.000 CAT |
| Older hour = H - 48 hours                            | 2026-10-11 12:00:00.000 CAT |
| event_time of the 1.0 kWh reading (older hour)       | 2026-10-11 12:10:00.000 CAT |
| event_time of the 0.5 kWh reading (older hour, late) | 2026-10-11 12:25:00.000 CAT |
| event_time of the 2.0 kWh reading (hour H)           | 2026-10-13 12:10:00.000 CAT |

| stage                                                   | raw older hour  | raw hour H         | aggregate older hour | aggregate hour H   | as expected |
| ------------------------------------------------------- | --------------- | ------------------ | -------------------- | ------------------ | ----------- |
| 1 Initial older-hour refresh, real-time off             | 1 kWh, 1 row    | no bucket returned | 1 kWh, 1 row         | no bucket returned | YES         |
| 2 After both new inserts, before refresh, real-time off | 1.5 kWh, 2 rows | 2 kWh, 1 row       | 1 kWh, 1 row         | no bucket returned | YES         |
| 3 Real-time on, still before refresh                    | 1.5 kWh, 2 rows | 2 kWh, 1 row       | 1 kWh, 1 row         | 2 kWh, 1 row       | YES         |
| 4 After manual refresh of both hours                    | 1.5 kWh, 2 rows | 2 kWh, 1 row       | 1.5 kWh, 2 rows      | 2 kWh, 1 row       | YES         |

| Question                                               | Answer                                                       |
| ------------------------------------------------------ | ------------------------------------------------------------ |
| Policy window at test time                             | 2026-10-10 13:58:10.749 CAT  to  2026-10-13 12:58:10.749 CAT |
| Hourly buckets fully inside the window                 | 2026-10-10 14:00  to  2026-10-13 11:00 (bucket starts)       |
| Older hour 2026-10-11 12:00 refreshable by the policy? | YES                                                          |
| Hour H 2026-10-13 12:00 refreshable by the policy?     | NO (it ends at 13:00, after the window end 12:58)            |
