# 8.3 Validation comparison

Shared predictors: lag_24h, lag_48h, lag_168h, prev_day_mean, hour_of_day, day_of_week, region

| configuration ID | model settings     | training rows | validation rows | validation MAE (kWh) | validation RMSE (kWh) |
| ---------------- | ------------------ | ------------- | --------------- | -------------------- | --------------------- |
| R1               | Ridge(alpha=0.1)   | 1,680         | 1,680           | 4.4316               | 5.6433                |
| R2               | Ridge(alpha=1.0)   | 1,680         | 1,680           | 4.4399               | 5.6517                |
| R3               | Ridge(alpha=10.0)  | 1,680         | 1,680           | 4.8189               | 6.1843                |
| R4               | Ridge(alpha=100.0) | 1,680         | 1,680           | 7.9553               | 11.7728               |

Selected: R1 Ridge(alpha=0.1)
