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

### Named-Plant Inventory

A named-plant inventory must be maintained at:
```
data/za_audit/za_named_plant_inventory.csv
```

This file lists every Eskom-named station that must appear as one or more rows in
`custom_powerplants.csv`. Required columns:

| Column | Description |
|---|---|
| `station_name` | Canonical Eskom station name |
| `carrier` | PyPSA carrier string |
| `status_2023` | `operating`, `retired`, `commissioning` |
| `p_nom_mw_expected` | Expected 2023 capacity in MW |
| `lat_expected` | Expected latitude |
| `lon_expected` | Expected longitude |
| `source` | Primary source (IRP 2023, pypsa-rsa, Eskom Annual Report) |

Minimum required stations (2023 status):
Koeberg (nuclear), Medupi (coal, commissioning), Kusile (coal, commissioning),
Matimba (coal), Kendal (coal), Tutuka (coal), Lethabo (coal), Majuba (coal),
Matla (coal), Duvha (coal), Hendrina (coal), Kriel (coal), Arnot (coal),
Komati (retired 2023 — must appear with `DateOut`), Camden (retired),
Grootvlei (retired), Ankerlig (OCGT), Gourikwa (OCGT), Acacia (OCGT),
Port Rex (OCGT), Drakensberg (PHS), Ingula (PHS), Palmiet (PHS), Steenbras (PHS),
KaXu Solar One (CSP), Khi Solar One (CSP), Bokpoort (CSP), Kathu (CSP), Xina Solar One (CSP),
Ilanga CSP (CSP).

Acceptance gate: every station in this list must have a matching row in `custom_powerplants.csv`
within ±50 MW capacity and ±10 km location. Document any station that cannot be reconciled to
within tolerance in `doc/za_implementation_log.md`.

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

### lat/lon precision — PR #1622 impact

Upstream PR #1622 attaches wind and solar generators at real lat/lon coordinates from
`powerplants.csv` rather than cluster centroids. For ZA local carriers using
`custom_powerplants.csv`, this means lat/lon values are now load-bearing for bus assignment.

Requirement: `Lat` and `Lon` columns in `custom_powerplants.csv` must be precise to within ±10 km
of the physical plant location. Use the `za_named_plant_inventory.csv` expected values as the
reference.

### Bus column — post-PR #1622 clarification

The implementing agent must verify whether, after PR #1622, `add_electricity` still requires an
explicit `bus` column in `custom_powerplants.csv` for ZA local carriers, or whether bus assignment
now happens automatically from lat/lon coordinates.

Steps:
1. Read `scripts/add_electricity.py` lines that handle `custom_powerplants`
2. Determine whether `bus` column is mandatory or optional
3. Document the finding in `doc/za_implementation_log.md`
4. If `bus` is no longer required, leave it in `custom_powerplants.csv` for clarity (it may serve
   as a sanity cross-check) but do not rely on it for bus assignment if upstream ignores it.

### CSP thermal storage — schema approach

CSP plants (KaXu, Khi, Bokpoort, Kathu, Xina, Ilanga) have 2.5–13 hours of thermal storage.

Follow strictly the upstream PyPSA-Earth behaviour for CSP storage representation:
- If `csp_model: advanced` (SAM solar tower), thermal storage is modelled by `atlite`/PyPSA-Earth
  internally using the SAM model parameters. Do not add custom storage-hour columns.
- Handle any CSP-specific parameters (e.g., storage hours, solar multiple) entirely inside
  `apply_za_local_carriers` using the existing upstream config keys (`csp:` block in config).
- Do not modify `custom_powerplants.csv` schema for CSP storage. Do not repurpose `Duration`.

If upstream CSP storage handling is found to be insufficient for SA plants at implementation time,
document the gap in `doc/za_implementation_log.md` and propose a targeted fix — do not silently
deviate from upstream behaviour.

### PHS storage energy — upstream default override required

PyPSA-Earth's upstream default for PHS storage is 6 hours. SA PHS plants have significantly
larger reservoirs:
- Drakensberg: ~24 hours at rated power
- Ingula: ~12–15 hours at rated power
- Palmiet: ~12 hours at rated power
- Steenbras: ~20+ hours at rated power

The implementing agent must override the upstream 6-hour default for each SA PHS station using the
`StorageCapacity_MWh` and `p_nom_MW` columns in `custom_powerplants.csv` to set the correct
`max_hours = StorageCapacity_MWh / p_nom_MW`.

Use pypsa-rsa's `plant_availability.xlsx` or Eskom data as the source for storage capacity per
station. Document the values used in `doc/za_implementation_log.md`.

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
