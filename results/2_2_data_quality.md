# 2.2 Data quality (before cleaning)

| Entry                   | Measured   | Expected   | Difference | Status |
| ----------------------- | ---------- | ---------- | ---------- | ------ |
| planned_readings        | 10,752,000 | 10,752,000 | 0          | OK     |
| emitted_readings        | 10,696,848 | 10,696,848 | 0          | OK     |
| unique_readings         | 10,643,735 | 10,643,735 | 0          | OK     |
| duplicate_readings      | 53,113     | 53,113     | 0          | OK     |
| delayed_unique_readings | 213,090    | 213,090    | 0          | OK     |
| missing_readings        | 108,265    | 108,265    | 0          | OK     |

| Measure              | Formula                       | Value     |
| -------------------- | ----------------------------- | --------- |
| Missing percentage   | 100 * missing / planned       | 1.0069 %  |
| Duplicate percentage | 100 * extra copies / unique   | 0.4990 %  |
| Delayed percentage   | 100 * delayed unique / unique | 2.0020 %  |
| Completeness         | 100 * unique / planned        | 98.9931 % |

Five meters with the most missing readings

| meter_id   | region    | customer_type | observed | missing | missing % |
| ---------- | --------- | ------------- | -------- | ------- | --------- |
| 1000003622 | Region 3  | commercial    | 2,641    | 47      | 1.749     |
| 1000000106 | Region 7  | industrial    | 2,643    | 45      | 1.674     |
| 1000000366 | Region 7  | commercial    | 2,643    | 45      | 1.674     |
| 1000001259 | Region 10 | residential   | 2,644    | 44      | 1.637     |
| 1000000189 | Region 10 | commercial    | 2,645    | 43      | 1.600     |
