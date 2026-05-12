# ZA Grid Reconciliation — Module 09

_Generated: 2026-05-12 20:01_

## Spatial level

- Locked level: **34** Eskom local areas
- Source decision: Stage 4b (pre-implementation-decisions.md Q2)
- Voltage threshold: ≥ 220 kV
- St Clair coefficients: [53.736, -0.65]

## St Clair coefficient note

PyPSA-RSA uses `(53.736, -0.65)` digitised from the St Clair curve reference linked in `pypsa-rsa/scripts/build_topology.py:241-253`. This differs from the literature-standard Dunlop fit `(43.261, -0.6678)`. Module 09 uses the pypsa-rsa value verbatim for consistency with the reference model.

## OSM grid summary (PyPSA-Earth `base.nc`)

| metric                   | value                                     | voltage_bucket   | line_count   | total_length_km    |
|:-------------------------|:------------------------------------------|:-----------------|:-------------|:-------------------|
| total_buses              | 1606                                      |                  |              |                    |
| total_lines              | 2138                                      |                  |              |                    |
| total_links_dc           | 0                                         |                  |              |                    |
| total_transformers       | 315                                       |                  |              |                    |
| total_line_length_km     | 76680.09700566337                         |                  |              |                    |
| unique_v_nom_kv          | 66|88|110|132|150|220|275|400|500|765     |                  |              |                    |
| source_base_nc           | networks/za_2023_fixed_validation/base.nc |                  |              |                    |
| lines_per_voltage_bucket |                                           | <220kV           | 1758         | 40642.44329711116  |
| lines_per_voltage_bucket |                                           | 220kV            | 17           | 1457.3188662513662 |
| lines_per_voltage_bucket |                                           | 275kV            | 131          | 7778.257415207871  |
| lines_per_voltage_bucket |                                           | 400kV            | 219          | 23598.66549791645  |
| lines_per_voltage_bucket |                                           | 765kV            | 13           | 3203.4119291765273 |

## RSA interregional corridor capacities (≥220 kV, N-1 derated)

| bus0             | bus1           |   n_lines |   voltage_max_kv |   voltage_min_kv |   total_length_km |   thermal_sum_mw |   sil_sum_mw |   st_clair_sum_mw |   st_clair_n1_mw |   n1_factor |   st_clair_a |   st_clair_b |
|:-----------------|:---------------|----------:|-----------------:|-----------------:|------------------:|-----------------:|-------------:|------------------:|-----------------:|------------:|-------------:|-------------:|
| Bloemfontein     | Carletonville  |         1 |              765 |              765 |          234.749  |             5512 |         2280 |          3526.21  |         2468.35  |         0.7 |       53.736 |        -0.65 |
| Bloemfontein     | Highveld South |         1 |              400 |              400 |          361.697  |             1788 |          602 |           702.971 |          492.08  |         0.7 |       53.736 |        -0.65 |
| Bloemfontein     | Hydra Central  |         3 |              765 |              400 |          997.865  |             9088 |         3484 |          4024.68  |         1645.67  |         0.7 |       53.736 |        -0.65 |
| Bloemfontein     | Kimberley      |         2 |              275 |              275 |          179.341  |             1842 |          490 |          1416.87  |          699.318 |         0.7 |       53.736 |        -0.65 |
| Bloemfontein     | Welkom         |         5 |              400 |              275 |          458.246  |             8073 |         2653 |          6690.48  |         4902.48  |         0.7 |       53.736 |        -0.65 |
| Carletonville    | Highveld South |         1 |              765 |              765 |          267.663  |             5512 |         2280 |          3237.93  |         2266.55  |         0.7 |       53.736 |        -0.65 |
| Carletonville    | Kalahari       |         1 |              400 |              400 |          228.827  |             1788 |          602 |           946.633 |          662.643 |         0.7 |       53.736 |        -0.65 |
| Carletonville    | Lephalale      |         2 |              400 |              400 |          706.726  |             3576 |         1204 |          1428.27  |          698.597 |         0.7 |       53.736 |        -0.65 |
| Carletonville    | Midrand        |         1 |              400 |              400 |           74.8626 |             1788 |          602 |          1788     |         1251.6   |         0.7 |       53.736 |        -0.65 |
| Carletonville    | Pretoria       |         1 |              275 |              275 |           98.9528 |              921 |          245 |           664.36  |          465.052 |         0.7 |       53.736 |        -0.65 |
| Carletonville    | Rustenburg     |         3 |              400 |              275 |          331.643  |             3630 |         1092 |          2721.47  |         1651.65  |         0.7 |       53.736 |        -0.65 |
| Carletonville    | West Rand      |         2 |              400 |              275 |          193.696  |             2709 |          847 |          2242.77  |          454.765 |         0.7 |       53.736 |        -0.65 |
| East London      | Gqeberha       |         2 |              400 |              220 |          315.305  |             2280 |          724 |          1460.93  |          241.831 |         0.7 |       53.736 |        -0.65 |
| East London      | Mthatha        |         1 |              400 |              400 |          183.62   |             1788 |          602 |          1092.23  |          764.56  |         0.7 |       53.736 |        -0.65 |
| East London      | Welkom         |         1 |              400 |              400 |          407.138  |             1788 |          602 |           650.923 |          455.646 |         0.7 |       53.736 |        -0.65 |
| Empangeni        | Highveld South |         2 |              765 |              400 |          344.481  |             7300 |         2882 |          5103.68  |         1371.4   |         0.7 |       53.736 |        -0.65 |
| Empangeni        | Newcastle      |         3 |              400 |              400 |          473.67   |             5364 |         1806 |          3870.76  |         2118.8   |         0.7 |       53.736 |        -0.65 |
| Empangeni        | Pinetown       |         2 |              275 |              275 |          231.171  |             1842 |          490 |          1201.09  |          600.384 |         0.7 |       53.736 |        -0.65 |
| Gqeberha         | Hydra Central  |         2 |              400 |              400 |          589.141  |             3576 |         1204 |          1606.66  |          801.047 |         0.7 |       53.736 |        -0.65 |
| Greater Komsberg | Outeniqua      |         3 |              400 |              400 |          664.687  |             5364 |         1806 |          3002.21  |         1752.7   |         0.7 |       53.736 |        -0.65 |
| Greater Komsberg | Peninsula      |         1 |              400 |              400 |          154.125  |             1788 |          602 |          1223.9   |          856.727 |         0.7 |       53.736 |        -0.65 |
| Highveld South   | Ladysmith      |         2 |              400 |              400 |          384.941  |             3576 |         1204 |          2140.12  |          974.786 |         0.7 |       53.736 |        -0.65 |
| Highveld South   | Middelburg     |         2 |              400 |              275 |          199.656  |             2709 |          847 |          2223.22  |          721.646 |         0.7 |       53.736 |        -0.65 |
| Highveld South   | Newcastle      |         4 |              400 |              400 |          643.321  |             7152 |         2408 |          4872.53  |         3486.84  |         0.7 |       53.736 |        -0.65 |
| Highveld South   | Welkom         |         4 |              765 |              400 |         1374.01   |            14600 |         5764 |          6500.42  |         4136.4   |         0.7 |       53.736 |        -0.65 |
| Highveld South   | West Rand      |         1 |              400 |              400 |          102.119  |             1788 |          602 |          1599.34  |         1119.54  |         0.7 |       53.736 |        -0.65 |
| Highveld South   | Witbank        |         7 |              400 |              400 |          508.018  |            12516 |         4214 |         11771.8   |         9983.79  |         0.7 |       53.736 |        -0.65 |
| Hydra Central    | Kimberley      |         1 |              400 |              400 |          187.884  |             1788 |          602 |          1076.05  |          753.236 |         0.7 |       53.736 |        -0.65 |
| Hydra Central    | Outeniqua      |         3 |              400 |              400 |          738.26   |             5364 |         1806 |          2708.81  |         1803.22  |         0.7 |       53.736 |        -0.65 |
| Hydra Central    | Welkom         |         2 |              765 |              400 |          552.683  |             7300 |         2882 |          3990.95  |          843.975 |         0.7 |       53.736 |        -0.65 |
| Johannesburg     | Middelburg     |         1 |              400 |              400 |          118.26   |             1788 |          602 |          1453.84  |         1017.69  |         0.7 |       53.736 |        -0.65 |
| Johannesburg     | Midrand        |         3 |              400 |              275 |           71.4957 |             3630 |         1092 |          3630     |         1842     |         0.7 |       53.736 |        -0.65 |
| Johannesburg     | Nigel          |         1 |              275 |              275 |           34.0046 |              921 |          245 |           921     |          644.7   |         0.7 |       53.736 |        -0.65 |
| Johannesburg     | Polokwane      |         2 |              400 |              400 |         1031.76   |             3576 |         1204 |          1116.18  |          557.334 |         0.7 |       53.736 |        -0.65 |
| Johannesburg     | Pretoria       |         8 |              400 |              275 |          219.458  |             8235 |         2317 |          7963.93  |         6447     |         0.7 |       53.736 |        -0.65 |
| Johannesburg     | Vaal           |         1 |              275 |              275 |           61.5768 |              921 |          245 |           904.295 |          633.007 |         0.7 |       53.736 |        -0.65 |
| Johannesburg     | Warmbad        |         1 |              275 |              275 |          100.163  |              921 |          245 |           659.131 |          461.392 |         0.7 |       53.736 |        -0.65 |
| Johannesburg     | West Rand      |         1 |              275 |              275 |           33.3299 |              921 |          245 |           921     |          644.7   |         0.7 |       53.736 |        -0.65 |
| Johannesburg     | Witbank        |         6 |              400 |              275 |          583.57   |             8994 |         2898 |          7958.38  |         6170.38  |         0.7 |       53.736 |        -0.65 |
| Kalahari         | Kimberley      |         3 |              275 |              275 |          280.182  |             2763 |          735 |          2082.69  |         1336.36  |         0.7 |       53.736 |        -0.65 |
| Kimberley        | Namaqualand    |         1 |              400 |              400 |          163.713  |             1788 |          602 |          1176.81  |          823.768 |         0.7 |       53.736 |        -0.65 |
| Ladysmith        | Newcastle      |         3 |              400 |              275 |          342.279  |             3630 |         1092 |          2620.83  |         1304.18  |         0.7 |       53.736 |        -0.65 |
| Ladysmith        | Pinetown       |         4 |              400 |              275 |          485.581  |             5418 |         1694 |          4289.31  |         2504.42  |         0.7 |       53.736 |        -0.65 |
| Lephalale        | Polokwane      |         2 |              400 |              400 |          350.016  |             3576 |         1204 |          2275.77  |         1038.42  |         0.7 |       53.736 |        -0.65 |
| Lephalale        | Pretoria       |         2 |              400 |              400 |          220.508  |             3576 |         1204 |          3043.24  |         1521.38  |         0.7 |       53.736 |        -0.65 |
| Lephalale        | Rustenburg     |         5 |              400 |              275 |          773.582  |             7206 |         2296 |          5105.99  |         3334.73  |         0.7 |       53.736 |        -0.65 |
| Lowveld          | Middelburg     |         2 |              275 |              275 |          111.136  |             1842 |          490 |          1842     |          921     |         0.7 |       53.736 |        -0.65 |
| Lowveld          | Phalaborwa     |         2 |              275 |              275 |          193.914  |             1842 |          490 |          1346.43  |          673.19  |         0.7 |       53.736 |        -0.65 |
| Middelburg       | Phalaborwa     |         3 |              400 |              275 |          407.857  |             4497 |         1449 |          3171.01  |         1936.48  |         0.7 |       53.736 |        -0.65 |
| Middelburg       | Witbank        |        11 |              400 |              275 |          726.177  |            17067 |         5551 |         16836     |        15048     |         0.7 |       53.736 |        -0.65 |
| Mthatha          | Pinetown       |         1 |              400 |              400 |          116.809  |             1788 |          602 |          1465.56  |         1025.89  |         0.7 |       53.736 |        -0.65 |
| Namaqualand      | Vredendal      |         1 |              400 |              400 |          168.88   |             1788 |          602 |          1153.28  |          807.298 |         0.7 |       53.736 |        -0.65 |
| Newcastle        | Pinetown       |         2 |              400 |              400 |          329.752  |             3576 |         1204 |          2382.18  |         1054.95  |         0.7 |       53.736 |        -0.65 |
| Nigel            | Vaal           |         2 |              275 |              275 |          128.891  |             1842 |          490 |          1606.31  |          685.308 |         0.7 |       53.736 |        -0.65 |
| Nigel            | Welkom         |         1 |              275 |              275 |          219.123  |              921 |          245 |           396.263 |          277.384 |         0.7 |       53.736 |        -0.65 |
| Nigel            | Witbank        |         2 |              275 |              275 |          133.152  |             1842 |          490 |          1719.11  |          859.421 |         0.7 |       53.736 |        -0.65 |
| Outeniqua        | Peninsula      |         3 |              400 |              400 |          599.173  |             5364 |         1806 |          3966.11  |         2178.11  |         0.7 |       53.736 |        -0.65 |
| Peninsula        | West Coast     |         2 |              400 |              400 |          164.004  |             3576 |         1204 |          3576     |         1788     |         0.7 |       53.736 |        -0.65 |
| Phalaborwa       | Polokwane      |         1 |              400 |              400 |           93.8655 |             1788 |          602 |          1689.4   |         1182.58  |         0.7 |       53.736 |        -0.65 |
| Polokwane        | Warmbad        |         1 |              275 |              275 |          171.006  |              921 |          245 |           465.558 |          325.891 |         0.7 |       53.736 |        -0.65 |

## Reconciliation

| voltage_bucket                      | osm_line_count   | osm_length_km      | rsa_line_count   | rsa_length_km     |
|:------------------------------------|:-----------------|:-------------------|:-----------------|:------------------|
| <220kV                              | 1758             | 40642.44329711116  |                  |                   |
| 220kV                               | 17               | 1457.3188662513662 |                  |                   |
| 275kV                               | 131              | 7778.257415207871  |                  |                   |
| 400kV                               | 219              | 23598.66549791645  |                  |                   |
| 765kV                               | 13               | 3203.4119291765273 |                  |                   |
| rsa_220kv_plus_aggregate            |                  |                    | 151              | 21390.63313364369 |
| rsa_existing_lines_220kv_plus_input |                  |                    | 324              |                   |
