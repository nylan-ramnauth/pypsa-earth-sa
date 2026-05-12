# ZA Powerplant Reconciliation — Module 08

Module 08 reconciles the audited 2023-active candidates from Module 04
(PyPSA-RSA `fixed_technologies` BASE scenario, REIPPPP wind, REIPPPP
solar) into a single frozen `data/custom_powerplants.csv` that Module 10
loads under `electricity.custom_powerplants: replace`.

## Sources

- `data/za_audit/pypsa_rsa_fixed_technologies_2023_candidates.csv` — PyPSA-RSA fixed_technologies (scenario_set='ME IRP 2024', Scenario='BASE')
- `data/za_audit/reipppp_wind_2023_candidates.csv` — REIPPPP wind 2023 candidates (`included_2023 == True`)
- `data/za_audit/reipppp_solar_2023_candidates.csv` — REIPPPP solar 2023 candidates (`included_2023 == True`, Type ∈ PV)
- `data/za_audit/raw/eskom_data_2023_full.csv` — raw hourly Eskom 2023 feed; used to derive per-carrier installed-capacity anchors

## Per-carrier totals (custom_powerplants.csv)

Fueltype
Hard Coal    40696.00
Hydro         3587.02
Wind          3506.78
Oil           3419.00
Solar         2787.81
Nuclear       1854.00
Bioenergy      176.56
Battery         20.00

## Eskom 2023 capacity anchors (informational)



The Eskom hourly feed exposes installed capacity only for renewable carriers
(Wind, PV, CSP, Other RE) plus the aggregate `Installed Eskom Capacity`.
Per-carrier conventional anchors (coal/nuclear/OCGT/Sasol) are NOT available
from the hourly feed and are recorded as `available: False` in
`data/za_audit/za_eskom_2023_capacity_anchors.csv`. Module 12 must use the Eskom Annual Report 2023 / IRP 2023
for the conventional anchors.

## Required source decisions

### Hex 20 MW battery (PyPSA-RSA `battery_4h` row, COD 2023)
**Decision: include.** Audit flagged `included_2023 == True`. Decommissioning
year = 2038. Documented as the only V1 battery row in the 2023 fleet.

### Redstone Solar Thermal
**Decision: exclude.** DateIn 2024 — outside the 2023 fixed-validation
baseline. Module 13 forward-looking scenarios will reintroduce it.

### PHS — Drakensberg, Ingula, Palmiet, Steenbras
**Decision: include with per-station `StorageCapacity_MWh`.** Module 08
writes `StorageCapacity_MWh` directly into `custom_powerplants.csv`; the
audit `data/za_audit/za_phs_storage_hours.csv` records the source for each
station. The upstream contract at `add_electricity.py:1027` only replaces
`max_hours == 0` with `config.renewable.hydro.PHS_max_hours: 6`, so any
non-zero value survives.

Reference values (used when the Module 04 audit `Max Storage (GWh)` column
is absent for a station):

| Station | p_nom (MW) | max_hours | StorageCapacity_MWh |
|---|---|---|---|
| Drakensberg | 1000 | 24 | 24,000 |
| Ingula      | 1332 | 14 | 18,648 |
| Palmiet     | 400  | 12 | 4,800  |
| Steenbras   | 180  | 20 | 3,600  |

### CSP — six 2023 plants
**Decision: include with `Type=Solar/Technology=CSP`.** KaXu Solar One,
Khi Solar One, Bokpoort, Kathu, Xina Solar One, Ilanga CSP (≈500 MW total).
`StorageCapacity_MWh` left blank — Module 10 owns CSP storage representation
through the `renewable.csp.csp_model` config key. Per-plant
`CSP Storage Hours` are recorded in `za_named_plant_inventory.csv` notes.

### Conventional capacity checks
Coal / Nuclear / OCGT / Sasol totals are recorded in this report and in
`za_powerplant_reconciliation.csv` for cross-check against the Eskom Annual
Report 2023. The hard ≤2% tolerance gate is deferred to Module 12.

## Named-plant gate

Named-plant inventory: 30 stations.
Failures (operating + commissioning stations outside ±50 MW / ±10 km
tolerance):

- **Hendrina**: distance_exceeds_tolerance  (expected 1098.0 MW, got 1098.0 MW, distance 25.148410628759443 km)

## Smoke diff status counts

{'ok': 135}

If any row has `status` other than `ok` or `pending_smoke`, see
`data/za_audit/za_powerplants_normalization_diff.csv` for details.

## V1 Limitations (recorded for Module 12)

- Per-carrier conventional anchors are not in the Eskom hourly feed —
  Module 12 must use the Eskom Annual Report 2023 / IRP 2023 instead.
- `bus` column blank in Module 08 — upstream KDTree assigns; Module 09
  finalises explicit substation assignments.
- CSP storage is **not** in `custom_powerplants.csv`; Module 10 owns it
  via `renewable.csp.csp_model`.
- The PyPSA-RSA `Coal_Flexibilisation` scenario set is **not** used; only
  `ME IRP 2024 / BASE` rows are included in the canonical 2023 fleet.

## Artifacts

- `data/custom_powerplants.csv` — 135 rows
- `data/za_audit/za_powerplant_reconciliation.csv` — 137 reconciliation rows
- `data/za_audit/za_named_plant_inventory.csv` — 30 named-plant rows
- `data/za_audit/za_eskom_2023_capacity_anchors.csv` — 17 anchor rows
- `data/za_audit/za_phs_storage_hours.csv` — PHS storage audit
- `data/za_audit/za_powerplants_normalization_diff.csv` — normalization smoke diff
