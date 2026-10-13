# 7.3 Raw vs Aggregate dashboard data

| panel                                 | matched by        | raw rows | aggregate rows | compared rows | keys      | reading-count mismatches | max abs difference | allowed | result |
| ------------------------------------- | ----------------- | -------- | -------------- | ------------- | --------- | ------------------------ | ------------------ | ------- | ------ |
| 1 Hourly regional energy              | bucket + region   | 1,680    | 1,680          | 1,680         | identical | 0                        | 0.000000000 kWh    | 0.001   | PASS   |
| 2 Daily network energy                | bucket            | 7        | 7              | 7             | identical | 0                        | 0.000000005 kWh    | 0.001   | PASS   |
| 3 Network energy per seven-day period | bucket            | 1        | 1              | 1             | identical | 0                        | 0.000000011 kWh    | 0.001   | PASS   |
| 4 Daily energy of the selected meter  | bucket + meter_id | 7        | 7              | 7             | identical | 0                        | 0.000000000 kWh    | 0.001   | PASS   |
| 5 Completeness by region              | region            | 10       | 10             | 10            | identical | 0                        | 0.000000000 pp     | 1e-06   | PASS   |
