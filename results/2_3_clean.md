# 2.3 Cleaning

| Measure                               | Before           | After            | Change         |
| ------------------------------------- | ---------------- | ---------------- | -------------- |
| Row count                             | 10,696,848       | 10,643,735       | -53,113        |
| Distinct (meter_id, event_time) pairs | 10,643,735       | 10,643,735       | 0              |
| Sum of energy_kwh                     | 3,872,863.893179 | 3,853,704.346816 | -19,159.546363 |

| Check                                                         | Result |
| ------------------------------------------------------------- | ------ |
| Rows deleted = extra copies found                             | OK     |
| Final row count = expected unique_readings (10,643,735)       | OK     |
| Row count = distinct pairs (one row per pair)                 | OK     |
| No duplicate pairs remain                                     | OK     |
| Distinct pairs unchanged (no reading lost, gaps kept as gaps) | OK     |
| Energy fell by the extra copies' energy (19,159.546363 kWh)   | OK     |
