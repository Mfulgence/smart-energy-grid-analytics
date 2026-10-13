# 4_3 warm-cache timing comparison (ms)

Client: Python 3.12.6 + psycopg 3.3.6 (s32_benchmark.py)  
Timer: time.perf_counter() around execute()+fetchall()  
Machine: Muhirwa  
Session: 2026-10-13 13:03:37.263 CAT to 2026-10-13 13:03:52.118 CAT = 14.9 s

| query | table                   | median ms | min ms | max ms |
| ----- | ----------------------- | --------- | ------ | ------ |
| Q1    | energy_time_compressed  | 420.3     | 415.4  | 434.5  |
| Q1    | energy_meter_compressed | 569.0     | 514.7  | 782.4  |
| Q2    | energy_time_compressed  | 168.0     | 158.0  | 171.9  |
| Q2    | energy_meter_compressed | 158.2     | 143.7  | 166.2  |
| Q3    | energy_time_compressed  | 250.6     | 240.5  | 251.3  |
| Q3    | energy_meter_compressed | 246.3     | 239.6  | 248.7  |
| Q4    | energy_time_compressed  | 86.0      | 82.5   | 188.0  |
| Q4    | energy_meter_compressed | 2.1       | 1.5    | 2.2    |
| Q5    | energy_time_compressed  | 190.7     | 186.7  | 204.5  |
| Q5    | energy_meter_compressed | 329.8     | 323.9  | 337.9  |

| query | energy_time_compressed | energy_meter_compressed | fastest                 | fastest vs slowest                         |
| ----- | ---------------------- | ----------------------- | ----------------------- | ------------------------------------------ |
| Q1    | 420.3                  | 569.0                   | energy_time_compressed  | 1.35 x faster than energy_meter_compressed |
| Q2    | 168.0                  | 158.2                   | energy_meter_compressed | 1.06 x faster than energy_time_compressed  |
| Q3    | 250.6                  | 246.3                   | energy_meter_compressed | 1.02 x faster than energy_time_compressed  |
| Q4    | 86.0                   | 2.1                     | energy_meter_compressed | 41.66 x faster than energy_time_compressed |
| Q5    | 190.7                  | 329.8                   | energy_time_compressed  | 1.73 x faster than energy_meter_compressed |

Chunks touched

| query | energy_time_compressed | energy_meter_compressed |
| ----- | ---------------------- | ----------------------- |
| Q1    | 2                      | 2                       |
| Q2    | 8                      | 8                       |
| Q3    | 29                     | 29                      |
| Q4    | 8                      | 8                       |
| Q5    | 29                     | 29                      |
