# 1.3 Pilot counts

| Stage                                       | Count | Target | Difference | Status    |
| ------------------------------------------- | ----- | ------ | ---------- | --------- |
| 1. Dictionaries taken from generator        | 2,000 | 2,000  | 0          | OK        |
| 2. Messages acknowledged by broker (PUBACK) | 2,000 | 2,000  | 0          | OK        |
| 3. Messages received by subscriber          | 1,952 | 2,000  | -48        | DIFFERENT |
| 4. Rows committed in energy_live            | 1,952 | 2,000  | -48        | DIFFERENT |
