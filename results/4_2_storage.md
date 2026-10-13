# 4.2 Storage and compression cost

Baseline: energy_readings

| table                   | data MB | index MB | total MB |
| ----------------------- | ------- | -------- | -------- |
| energy_readings         | 950.9   | 465.9    | 1,416.8  |
| energy_time_compressed  | 437.8   | 0.9      | 438.7    |
| energy_meter_compressed | 496.2   | 5.5      | 501.6    |

| strategy                | compression ratio | saved % | compression s (sum of chunks) | load s (excluded) | compressed chunks | rows in compressed chunks | rows % |
| ----------------------- | ----------------- | ------- | ----------------------------- | ----------------- | ----------------- | ------------------------- | ------ |
| energy_time_compressed  | 3.23 : 1          | 69.0    | 18.5                          | 97.6              | 29 of 29          | 10,643,735 of 10,643,735  | 100.00 |
| energy_meter_compressed | 2.82 : 1          | 64.6    | 40.3                          | 126.6             | 29 of 29          | 10,643,735 of 10,643,735  | 100.00 |
