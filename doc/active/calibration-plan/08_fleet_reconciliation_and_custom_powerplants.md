# 08 Fleet Reconciliation And Custom Powerplants

## Goal

Convert source audits into a frozen 2023 South Africa plant inventory that
PyPSA-Earth can load reproducibly.

## Reconciliation Output

Create one row per candidate plant:

```text
data/za_audit/za_powerplant_reconciliation.csv
doc/za_powerplant_reconciliation.md
```

Required columns:

```text
canonical_name
carrier
technology
capacity_mw_final
capacity_mw_ppm
capacity_mw_rsa
capacity_mw_reipppp
eskom_anchor_capacity_mw
anchor_delta_mw
date_in_final
date_out_final
lat_final
lon_final
source_ppm
source_rsa
source_reipppp
status_2023
included_2023
decision
decision_reason
notes
```

Carrier totals must be checked against `02_eskom_validation_data_pipeline.md`.
The reconciliation must consume active-2023 PyPSA-RSA candidates from `04`,
including the fixed technologies, REIPPPP, PHS, CSP, battery, and conventional
candidate audits.

## Required Source Decisions

The reconciliation report must explicitly decide and document:

- Hex 20 MW battery 2023 status: include only if active in 2023 and
  normalization smoke passes; otherwise exclude with audit reason.
- PHS capacity and storage energy for Drakensberg, Ingula, Palmiet, and
  Steenbras.
- six 2023 CSP plants totaling 500 MW, with CSP storage-hour metadata preserved.
- Redstone CSP exclusion from the 2023 baseline.
- conventional capacity checks for coal, nuclear, OCGT/diesel, OCGT/gas,
  Sasol coal, Sasol gas, hydro, and imports.

## Final Fleet Output

Write:

```text
data/custom_powerplants.csv
```

Use `electricity.custom_powerplants: replace`.

Required columns and conventions:

```text
Name, Fueltype, Technology, Set, Country, Capacity, Efficiency, Duration,
Volume_Mm3, DamHeight_m, StorageCapacity_MWh, DateIn, DateRetrofit, DateOut,
lat, lon, EIC, projectID, bus
```

Rules:

- Do not add an `id`-first rule. The upstream file header starts with
  `Name,Fueltype,...`, and the upstream loader reads the CSV without
  `index_col=0`.
- Use `Country = ZA`.
- Provide explicit `DateIn`.
- Leave `DateOut` blank only if available beyond 2023.
- Capacity is MW.
- `projectID` records provenance such as `RSA_FIXED_TECHNOLOGIES|REIPPPP|PPM`.
- Write `bus` blank or provisional in `08`; `09` finalizes audited bus
  assignments, and `10` consumes only finalized values.
- Duplicate and near-duplicate source records resolve to one canonical
  reconciliation row. Raw source names and IDs are retained in provenance
  columns and notes.
- The repo currently ships an empty header-only `data/custom_powerplants.csv`;
  this module replaces it atomically with the reconciled 2023 fleet.

Pin the 2023 upstream powerplant filter in the ZA overlay:

```yaml
electricity:
  powerplants_filter: (DateOut >= 2022 or DateOut != DateOut) and (DateIn <= 2023 or DateIn != DateIn)
```

## Normalization Smoke

Before writing the full fleet, create and run a tiny fixture with one row for:

```text
coal, nuclear, OCGT, diesel peaker, gas OCGT, sasol_gas, sasol_coal,
onwind, solar PV, CSP, run-of-river hydro, reservoir hydro, pumped storage,
battery, biomass, other_re
```

`hydro_import` is not a `custom_powerplants.csv` plant. It is tested through the
import/export attachment path owned by `06_demand_import_export_model_inputs.md`
and consumed by `10_fixed_capacity_network_build.md`.

The `other_re` smoke row validates local carrier normalization and metadata. The
final V1 `other_re` asset is attached from the `06` fixed-dispatch time series,
not from an inferred renewable-capacity rule.

Run through:

```text
resources/<run>/powerplants.csv
networks/<run>/elec.nc
```

After the smoke build, run a notebook-style post-build normalization cross-tab
using the PyPSA-Earth capacity-validation pattern:

```text
data/za_audit/za_powerplants_normalization_diff.csv
```

The diff must compare `data/custom_powerplants.csv`,
`resources/<run>/powerplants.csv`, and `networks/<run>/elec.nc` by canonical
plant where possible and by normalized carrier totals otherwise. It must detect
source rows dropped by PyPSA-Earth filtering, carrier normalization changes,
capacity shifts, duplicate collapse, and unintended additions from default
IRENA or powerplantmatching data. `hydro_import` is excluded from the
custom-powerplants side of this diff because it is an exogenous import handled
by `06` and `10`.

## Acceptance Gates

- Reconciliation table is complete and documented.
- Final `custom_powerplants.csv` exists and passes PyPSA-Earth filtering.
- Smoke network shows expected normalized carriers.
- `data/za_audit/za_powerplants_normalization_diff.csv` exists and leaves no
  unexplained custom-source drops, carrier remappings, capacity shifts, or
  unintended default additions.
- No unintended IRENA renewable capacity or extendable capacity is added.
- Wind, PV, and CSP installed capacities match Eskom anchors within the `12`
  locked `<= 2%` reconciliation tolerance.
- Conventional fleet totals, coal/nuclear/OCGT/Sasol capacities, PHS storage
  energy, and CSP storage-hour metadata are checked against audit sources.
- Hex 20 MW battery, six 2023 CSP plants, Redstone exclusion, and PHS energy are
  explicitly resolved in the reconciliation report.
