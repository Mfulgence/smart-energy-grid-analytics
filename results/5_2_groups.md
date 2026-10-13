# 5.2 Regions and customer types

| region    | meter_count | energy_kwh     | energy_per_meter_kwh |
| --------- | ----------- | -------------- | -------------------- |
| Region 1  | 400         | 383,539.805155 | 958.849513           |
| Region 2  | 400         | 378,448.8881   | 946.12222            |
| Region 3  | 400         | 392,376.593951 | 980.941485           |
| Region 4  | 400         | 324,404.477429 | 811.011194           |
| Region 5  | 400         | 411,040.393514 | 1,027.600984         |
| Region 6  | 400         | 346,512.837387 | 866.282093           |
| Region 7  | 400         | 362,288.54376  | 905.721359           |
| Region 8  | 400         | 503,475.828891 | 1,258.689572         |
| Region 9  | 400         | 400,467.195021 | 1,001.167988         |
| Region 10 | 400         | 351,149.783608 | 877.874459           |

| customer_type | meter_count | energy_kwh       | energy_per_meter_kwh |
| ------------- | ----------- | ---------------- | -------------------- |
| industrial    | 406         | 2,220,672.035775 | 5,469.635556         |
| commercial    | 1,010       | 825,475.153184   | 817.302132           |
| residential   | 2,584       | 807,557.157858   | 312.52212            |

| region    | residential | commercial | industrial | avg_base_power_kw |
| --------- | ----------- | ---------- | ---------- | ----------------- |
| Region 1  | 247         | 116        | 37         | 2.426             |
| Region 2  | 263         | 98         | 39         | 2.346             |
| Region 3  | 260         | 94         | 46         | 2.370             |
| Region 4  | 277         | 94         | 29         | 2.060             |
| Region 5  | 258         | 94         | 48         | 2.459             |
| Region 6  | 263         | 105        | 32         | 2.230             |
| Region 7  | 262         | 103        | 35         | 2.274             |
| Region 8  | 234         | 105        | 61         | 2.937             |
| Region 9  | 259         | 96         | 45         | 2.423             |
| Region 10 | 261         | 105        | 34         | 2.235             |

| Comparison                                  | Result       |
| ------------------------------------------- | ------------ |
| Regions: highest vs lowest TOTAL            | 55.2 % apart |
| Regions: highest vs lowest PER METER        | 55.2 % apart |
| Customer types: highest vs lowest TOTAL     | 2.75 x       |
| Customer types: highest vs lowest PER METER | 17.50 x      |
