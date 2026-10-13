# 2.1 Capture and load

| Count                                      | Measured   | Expected   | Status |
| ------------------------------------------ | ---------- | ---------- | ------ |
| Dictionaries consumed from iter_readings() | 10,696,848 | 10,696,848 | OK     |
| CSV data rows                              | 10,696,848 | 10,696,848 | OK     |
| Rows committed in energy_readings          | 10,696,848 | 10,696,848 | OK     |

| Measure                                                     | Value                                              |
| ----------------------------------------------------------- | -------------------------------------------------- |
| Ingestion route                                             | generator -> CSV file -> COPY into energy_readings |
| File generation seconds                                     | 75.2                                               |
| Database loading seconds (first COPY to final commit)       | 151.2                                              |
| Total elapsed seconds (start of generation to final commit) | 228.0                                              |
| Started (CAT)                                               | 2026-10-13 11:16:21.274 CAT                        |
| Final commit (CAT)                                          | 2026-10-13 11:20:09.231 CAT                        |
