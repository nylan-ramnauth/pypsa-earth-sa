# Earth–RSA Baseline Diagnostic Report

**Module 10 — Calibration Plan.** Audit-only. Quantifies the gap between
what PyPSA-Earth retrieves by default for South Africa (PPM fleet, OSM grid)
and what PyPSA-RSA uses (modules 06–09 overrides).

## Summary

| Dimension | Earth side | RSA side | Verdict |
|---|---|---|---|
| Fleet | PPM live query, 263 plants | 137 plants | total delta +15452 MW |
| Lines (220kV+) | 380 | 310 | see Comparison 2 |
| Substations (220kV+) | 2723 | 164 | ratio 16.604 |
| Ratings (65 corridors) | s_nom from elec_s_34 | St Clair N-1 | over=52, under=2, within=11, unmatched=0 |

---

## Comparison 1 — Powerplant fleet (PPM vs RSA)

PPM live query → ZA subset → fuzzy match (same carrier, ±20 km, ±30% capacity)
against `za_powerplant_reconciliation.csv`. Per-carrier aggregate:

| carrier     |   capacity_mw_ppm_total |   capacity_mw_rsa_total |   delta_mw |   n_plants_ppm_only |   n_plants_rsa_only |   n_plants_matched | notes              |
|:------------|------------------------:|------------------------:|-----------:|--------------------:|--------------------:|-------------------:|:-------------------|
| PHS         |                 2892    |                 2904    |     -12    |                   1 |                   1 |                  3 | nan                |
| battery     |                    0    |                   20    |     -20    |                   0 |                   1 |                  0 | nan                |
| bioenergy   |                   56.19 |                    0    |      56.19 |                   8 |                   0 |                  0 | nan                |
| biomass     |                    0    |                  296.56 |    -296.56 |                   0 |                   4 |                  0 | nan                |
| coal        |                50087.4  |                40696    |    9391.43 |                  25 |                  28 |                  1 | delta>500MW: +9391 |
| csp         |                  200    |                  500    |    -300    |                   1 |                   5 |                  1 | nan                |
| hydro       |                  622.24 |                  683.02 |     -60.78 |                   3 |                   3 |                  3 | nan                |
| nuclear     |                 1959.01 |                 1854    |     105.01 |                   3 |                   1 |                  0 | nan                |
| ocgt_diesel |                 2420.3  |                 3419    |    -998.7  |                   0 |                   2 |                  4 | delta>500MW: -999  |
| ocgt_gas    |                 1359.54 |                    0    |    1359.54 |                   5 |                   0 |                  0 | delta>500MW: +1360 |
| onwind      |                 5555.4  |                 3506.78 |    2048.62 |                  24 |                   7 |                 28 | delta>500MW: +2049 |
| ror         |                   56.12 |                    0    |      56.12 |                   8 |                   0 |                  0 | nan                |
| solar       |                 6420.2  |                 2296.81 |    4123.39 |                 112 |                  12 |                 33 | delta>500MW: +4123 |

![Fleet capacity by carrier](figures/10_diagnostic/01_fleet_capacity_by_carrier.png)

Appendix files:
- `data/za_audit/za_ppm_plants_not_in_rsa.csv` — PPM rows with no RSA match
- `data/za_audit/za_rsa_plants_not_in_ppm.csv` — RSA rows with no PPM match

Reconciliation back-fill: `capacity_mw_ppm` / `source_ppm` populated in
`data/za_audit/za_powerplant_reconciliation.csv` for matched rows;
unmatched rows tagged `source_ppm="no_ppm_match"`.

---

## Comparison 2 — Transmission lines per voltage

RSA GeoJSON (324 features) bucketed by `NOMINAL_VO`; lengths via haversine over
each feature's `LineString` coords. Standard buckets {220, 275, 400, 765} kV;
features outside reported under `other_kv` (informational).

| voltage_bucket                      |   osm_line_count |   osm_length_km |   rsa_line_count |   rsa_length_km |   rsa_mean_length_km |   delta_line_count |   delta_length_km |   osm_coverage_ratio |
|:------------------------------------|-----------------:|----------------:|-----------------:|----------------:|---------------------:|-------------------:|------------------:|---------------------:|
| <220kV                              |             1758 |        40642.4  |              nan |          nan    |             nan      |                nan |           nan     |             nan      |
| 220kV                               |               17 |         1457.32 |               12 |         1083.63 |              90.3027 |                  5 |           373.687 |               1.3448 |
| 275kV                               |              131 |         7778.26 |              133 |         7390.72 |              55.5693 |                 -2 |           387.539 |               1.0524 |
| 400kV                               |              219 |        23598.7  |              157 |        19395.1  |             123.535  |                 62 |          4203.6   |               1.2167 |
| 765kV                               |               13 |         3203.41 |                8 |         2428.64 |             303.58   |                  5 |           774.77  |               1.319  |
| rsa_220kv_plus_aggregate            |              nan |          nan    |              151 |        21390.6  |             nan      |                nan |           nan     |             nan      |
| rsa_existing_lines_220kv_plus_input |              nan |          nan    |              324 |          nan    |             nan      |                nan |           nan     |             nan      |
| other_kv                            |              nan |          nan    |               14 |         1294.09 |              92.4351 |                nan |           nan     |             nan      |

![Line count per voltage](figures/10_diagnostic/02a_line_count_per_voltage.png)
![Line length per voltage](figures/10_diagnostic/02b_line_length_per_voltage.png)
![Network overlay](figures/10_diagnostic/02c_network_overlay.png)

---

## Comparison 3 — Substations (Earth OSM vs RSA derived)

PyPSA-RSA has no dedicated substations file. RSA substations derived as the
unique union of `LINE_START` ∪ `LINE_END` from the 220kV+ existing-lines
GeoJSON. PyPSA-Earth side: OSM `all_clean_substations.geojson` filtered to
ZA + voltage ≥ 220 kV.

| voltage_bucket   |   osm_substation_count |   rsa_substation_count |   delta_count |   osm_coverage_ratio | notes                          |
|:-----------------|-----------------------:|-----------------------:|--------------:|---------------------:|:-------------------------------|
| 220kV            |                    113 |                      9 |           104 |               12.556 | nan                            |
| 275kV            |                   1118 |                     66 |          1052 |               16.939 | nan                            |
| 400kV            |                   1382 |                     80 |          1302 |               17.275 | nan                            |
| 765kV            |                    110 |                      9 |           101 |               12.222 | nan                            |
| other_kv         |                  13482 |                      7 |         13475 |             1926     | nan                            |
| 220kv_plus_total |                   2723 |                    164 |          2559 |               16.604 | sum of 220/275/400/765 buckets |

Top RSA substations by incident-line count (sample):

| substation_name   |   n_incident_lines |   voltage_max_kv | voltages_kv   |
|:------------------|-------------------:|-----------------:|:--------------|
| PERSEUS           |                 14 |              765 | 275,400,765   |
| HYDRA             |                 13 |              765 | 220,400,765   |
| APOLLO            |                 12 |              533 | 275,400,533   |
| GLOCKNER          |                 12 |              400 | 275,400       |
| PLUTO             |                 11 |              400 | 275,400       |
| MATLA             |                 10 |              400 | 275,400       |
| MINERVA           |                 10 |              400 | 275,400       |
| ARNOT             |                 10 |              400 | 275,400       |
| VENUS             |                 10 |              400 | 275,400       |
| CAMDEN            |                  9 |              400 | 275,400       |
| MERSEY            |                  8 |              400 | 275,400       |
| POSEIDON          |                  8 |              400 | 220,400       |
| LETHABO           |                  8 |              400 | 275,400       |
| PEGASUS           |                  8 |              400 | 400           |
| SPITSKOP          |                  8 |              400 | 275,400       |

![Substation count per voltage](figures/10_diagnostic/03a_substation_count_per_voltage.png)
![Substation map](figures/10_diagnostic/03b_substation_map.png)

---

## Comparison 4 — Line ratings (OSM s_nom vs St Clair N-1)

Per-corridor: sum `n.lines.s_nom` from `elec_s_34.nc` matched by (bus0, bus1)
to the 65-corridor St Clair N-1 table.

**Per-direction summary (corridor count):**

- `osm_over` (ratio > 1.2): 52
- `within_20pct`: 11
- `osm_under` (ratio < 0.8): 2
- `unmatched` (no OSM lines): 0

![Ratings ratio distribution](figures/10_diagnostic/04a_ratings_ratio_distribution.png)
![Ratings scatter](figures/10_diagnostic/04b_ratings_scatter.png)

Top 10 most over-rated corridors (OSM > St Clair):

| bus0             | bus1      |   n_lines |   voltage_max_kv |   osm_s_nom_total_mw |   n_osm_lines |   st_clair_n1_mw |   ratio_osm_to_stclair | direction   |   notes |
|:-----------------|:----------|----------:|-----------------:|---------------------:|--------------:|-----------------:|-----------------------:|:------------|--------:|
| Hydra Central    | Welkom    |         2 |              765 |              9087.03 |             1 |           843.98 |                10.7669 | osm_over    |     nan |
| Bloemfontein     | Kimberley |         2 |              275 |              7355.41 |             1 |           699.32 |                10.518  | osm_over    |     nan |
| Hydra Central    | Kimberley |         1 |              400 |              7594.49 |             1 |           753.24 |                10.0825 | osm_over    |     nan |
| East London      | Gqeberha  |         2 |              400 |              2426.5  |             1 |           241.83 |                10.0339 | osm_over    |     nan |
| Carletonville    | West Rand |         2 |              400 |              4552.48 |             1 |           454.77 |                10.0106 | osm_over    |     nan |
| Greater Komsberg | Peninsula |         1 |              400 |              7299.55 |             1 |           856.73 |                 8.5203 | osm_over    |     nan |
| Vaal             | Welkom    |         1 |              275 |              1941.65 |             1 |           311.54 |                 6.2324 | osm_over    |     nan |
| Mthatha          | Pinetown  |         1 |              400 |              6173.5  |             1 |          1025.89 |                 6.0177 | osm_over    |     nan |
| Nigel            | Vaal      |         2 |              275 |              3551.49 |             1 |           685.31 |                 5.1823 | osm_over    |     nan |
| Lephalale        | Polokwane |         2 |              400 |              5362.43 |             1 |          1038.42 |                 5.164  | osm_over    |     nan |

Top 10 most under-rated corridors (OSM < St Clair):

| bus0           | bus1       |   n_lines |   voltage_max_kv |   osm_s_nom_total_mw |   n_osm_lines |   st_clair_n1_mw |   ratio_osm_to_stclair | direction    |   notes |
|:---------------|:-----------|----------:|-----------------:|---------------------:|--------------:|-----------------:|-----------------------:|:-------------|--------:|
| Johannesburg   | Pretoria   |         8 |              400 |              1130.58 |             1 |          6447    |                 0.1754 | osm_under    |     nan |
| Johannesburg   | West Rand  |         1 |              275 |               393.24 |             1 |           644.7  |                 0.61   | osm_under    |     nan |
| Nigel          | Welkom     |         1 |              275 |               277.38 |             1 |           277.38 |                 1      | within_20pct |     nan |
| Johannesburg   | Vaal       |         1 |              275 |               633.01 |             1 |           633.01 |                 1      | within_20pct |     nan |
| Johannesburg   | Warmbad    |         1 |              275 |               461.39 |             1 |           461.39 |                 1      | within_20pct |     nan |
| Johannesburg   | Witbank    |         6 |              400 |              6170.38 |             1 |          6170.38 |                 1      | within_20pct |     nan |
| Highveld South | West Rand  |         1 |              400 |              1119.54 |             1 |          1119.54 |                 1      | within_20pct |     nan |
| Carletonville  | Pretoria   |         1 |              275 |               465.05 |             1 |           465.05 |                 1      | within_20pct |     nan |
| Johannesburg   | Polokwane  |         2 |              400 |               557.33 |             1 |           557.33 |                 1      | within_20pct |     nan |
| Johannesburg   | Middelburg |         1 |              400 |              1017.69 |             1 |          1017.69 |                 1      | within_20pct |     nan |

---

## Limitations

- Demand profile comparison is intentionally omitted; module 06 already
  overwrote the GEGIS source with the Eskom 2023 measured profile.
- PPM live query may rotate between cache and source database; rerun annually.
- RSA substation set is derived from line endpoints; missing endpoint
  attribution in the GeoJSON will under-count. OSM substation count uses
  `voltage` tag — substations without a voltage tag are excluded.
- Line-ratings comparison maps clustered-network lines (post-`simplify` +
  cluster to 34 regions) to RSA corridors; if cluster topology fails to span
  a corridor it is flagged `unmatched`.

---

## Reproduction

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml \
    --cores 1 build_za_earth_rsa_diagnostic
```

Or directly:
```bash
python scripts/build_za_earth_rsa_diagnostic.py \
    --configfile configs/za/za_2023_fixed_validation.yaml
```
