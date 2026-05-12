# 10 Earth–RSA Baseline Diagnostic

## Goal

Quantify the gap between what PyPSA-Earth retrieves by default for South Africa
and what PyPSA-RSA uses, across four dimensions: **powerplants, transmission
lines, substations, and per-corridor line ratings**.

This module is **audit-only**: it produces no model inputs and does not modify
any file written by modules 01–09 except the two existing reconciliation CSVs,
both of which are filled in-place (no schema change, only NaN cells back-filled).

The four comparisons below answer the question: *how wrong would the V1 model
be if the ZA overrides from modules 06–09 had not been applied?*

---

## Context: What Was Skipped in Modules 08 and 09

Module 08 built `custom_powerplants.csv` entirely from PyPSA-RSA + REIPPPP data
and set `custom_powerplants: replace`. The `capacity_mw_ppm` column in
`za_powerplant_reconciliation.csv` was left empty (0/229 rows filled) because
the IRENA/powerplantmatching database was never queried.

Module 09 built the 34-region busmap and 65-corridor St Clair limits, but the
`rsa_line_count` and `rsa_length_km` columns in `za_grid_reconciliation.csv` are
NaN for every per-voltage row because the RSA GeoJSON was never broken down by
voltage class.

This module fills both gaps and adds two additional comparison dimensions
(substations, line ratings).

---

## Comparison 1 — Powerplant Fleet (PPM vs RSA)

### Objective

Identify which plants `powerplantmatching` (PPM) would supply for ZA by default,
which are missing relative to the RSA fleet, and which PPM entries have no RSA
counterpart.

### Procedure

1. Query `powerplantmatching` **live** for the ZA subset:

   ```python
   import powerplantmatching as pm
   ppl = pm.powerplants(from_url=False)
   za_ppm = ppl[ppl.Country == 'ZA'].copy()
   ```

   If `powerplantmatching` is unavailable in the active environment, the
   script errors loudly with guidance — there is no silent fallback (the
   `resources/za_2023_fixed_validation/powerplants.csv` artifact was already
   overwritten by module 08 with RSA fixed_technologies, so it cannot serve
   as a fallback).

2. Normalise PPM `Fueltype`/`Technology` to the ZA carrier vocabulary used in
   `za_powerplant_reconciliation.csv` (`coal`, `nuclear`, `ocgt_diesel`,
   `ocgt_gas`, `hydro`, `ror`, `PHS`, `solar`, `onwind`, `csp`, `battery`,
   `bioenergy`, `other`).

3. Fuzzy-match each RSA row to the PPM subset by: same carrier, haversine
   distance < 20 km, capacity within ±30%. Record matched PPM capacity in
   `capacity_mw_ppm` and a `source_ppm = "ppm_live:<projectID>"` tag.

4. Produce `data/za_audit/za_ppm_vs_rsa_fleet_comparison.csv`:

   ```text
   carrier, capacity_mw_ppm_total, capacity_mw_rsa_total,
   delta_mw, n_plants_ppm_only, n_plants_rsa_only,
   n_plants_matched, notes
   ```

5. Write `data/za_audit/za_ppm_plants_not_in_rsa.csv` (PPM rows unmatched)
   and `data/za_audit/za_rsa_plants_not_in_ppm.csv` (RSA rows unmatched).

6. Back-fill `capacity_mw_ppm` / `source_ppm` in
   `data/za_audit/za_powerplant_reconciliation.csv`; unmatched rows tagged
   `source_ppm = "no_ppm_match"`.

### Acceptance Gates

- `za_ppm_vs_rsa_fleet_comparison.csv` exists; one row per carrier; no NaN totals.
- `capacity_mw_ppm` populated for every PPM-matched RSA row.
- Delta for Hard Coal and Nuclear documented; > 500 MW deltas flagged in `notes`.

---

## Comparison 2 — Transmission Lines per Voltage

### Objective

Fill the NaN cells in `za_grid_reconciliation.csv` with a per-voltage breakdown
of the RSA GeoJSON, enabling a direct OSM vs RSA line count + length comparison
by voltage class.

### Procedure

1. Read `data/za_audit/za_rsa_existing_lines_220kv_plus.geojson` (324 features).
   The voltage is stored as `properties.NOMINAL_VO` (float, e.g. 275.0).

2. Group features into standard buckets `{220, 275, 400, 765} kV`. Features at
   other voltages (110, 132, 533 kV exist in the file) are appended as a
   single informational `other_kv` row.

3. Per bucket: line count, total length km (haversine over each `LineString`
   feature), mean length km.

4. Update `data/za_audit/za_grid_reconciliation.csv` in-place: fill
   `rsa_line_count` and `rsa_length_km` for the four per-voltage rows. Add
   columns: `rsa_mean_length_km`, `delta_line_count`, `delta_length_km`,
   `osm_coverage_ratio = osm_length_km / rsa_length_km`.

### Acceptance Gates

- No NaN values in `rsa_line_count` / `rsa_length_km` for the four voltage rows.
- `osm_coverage_ratio` computed for all four voltage classes.
- Sum of {220,275,400,765} bucket lengths cross-checks against the
  `rsa_220kv_plus_aggregate` row (151 lines / 21,390 km — note that the line
  count in the aggregate is feature-deduplicated while the per-voltage rows
  count features, so the totals may exceed 151).

---

## Comparison 3 — Substations (Earth OSM vs RSA derived)

### Objective

PyPSA-RSA has no dedicated substations file, so we **derive** the RSA
substation set from the unique union of `LINE_START` ∪ `LINE_END` properties
of the 220kV+ existing-lines GeoJSON, and compare against the PyPSA-Earth
OSM `all_clean_substations.geojson`.

### Procedure

1. Read `data/za_audit/za_rsa_existing_lines_220kv_plus.geojson` once; build
   `rsa_subs` = set of unique uppercase-stripped names from `LINE_START` and
   `LINE_END`. For each name, track incident-line count and max voltage.

2. Read `resources/{run}/osm/clean/all_clean_substations.geojson`. Filter by
   `country == "ZA"`; parse `voltage` tag (volts; multi-valued like
   `"220000;400000"` — take max); keep only voltage ≥ 220 kV.

3. Aggregate per voltage bucket (220/275/400/765 + `other_kv`) and produce
   `data/za_audit/za_substations_comparison.csv` with one row per bucket plus
   a `220kv_plus_total` aggregate row:

   ```text
   voltage_bucket, osm_substation_count, rsa_substation_count,
   delta_count, osm_coverage_ratio, notes
   ```

4. Write `data/za_audit/za_rsa_substations_derived.csv`:

   ```text
   substation_name, n_incident_lines, voltage_max_kv, voltages_kv
   ```

### Acceptance Gates

- One row per voltage bucket plus the `220kv_plus_total` row.
- `osm_coverage_ratio` populated for every row where `rsa_substation_count > 0`.
- `za_rsa_substations_derived.csv` row count equals `|LINE_START ∪ LINE_END|`.

---

## Comparison 4 — Line Ratings (OSM Type-Based s_nom vs St Clair N-1)

### Objective

Quantify how far PyPSA-Earth's default line thermal ratings deviate from the
St Clair N-1 limits computed in module 09, for each of the 65 corridors.

### Procedure

1. Load `networks/{run}/elec_s_34.nc` using PyPSA.

2. For each of the 65 corridors in
   `data/za_audit/za_rsa_interregional_transfer_limits.csv`, match
   `n.lines.bus0`/`bus1` against the corridor `(bus0, bus1)` pair in either
   direction.

3. Sum `n.lines.s_nom` per corridor → `osm_s_nom_total_mw`.

4. Produce `data/za_audit/za_osm_vs_stclair_ratings_comparison.csv`:

   ```text
   bus0, bus1, n_lines, voltage_max_kv, osm_s_nom_total_mw,
   n_osm_lines, st_clair_n1_mw, ratio_osm_to_stclair,
   direction, notes
   ```

   `direction`: `osm_over` if ratio > 1.2, `osm_under` if ratio < 0.8,
   `within_20pct` otherwise, `unmatched` if no OSM lines connect the corridor.

5. Append per-direction `_summary_` footer rows: corridor count + total MW
   for over / within / under / unmatched.

### Acceptance Gates

- All 65 corridors covered (matched or `unmatched` with explanation).
- `ratio_osm_to_stclair` populated for all matched corridors.
- Summary footer rows present.

---

## New Snakemake Rule

```python
rule build_za_earth_rsa_diagnostic:
    input:
        reconciliation="data/za_audit/za_powerplant_reconciliation.csv",
        existing_lines="data/za_audit/za_rsa_existing_lines_220kv_plus.geojson",
        grid_reconciliation=ancient("data/za_audit/za_grid_reconciliation.csv"),
        elec_s_34="networks/" + RDIR + "elec_s_34.nc",
        transfer_limits="data/za_audit/za_rsa_interregional_transfer_limits.csv",
        clean_substations="resources/" + RDIR + "osm/clean/all_clean_substations.geojson",
    output:
        fleet_comparison="data/za_audit/za_ppm_vs_rsa_fleet_comparison.csv",
        ppm_only="data/za_audit/za_ppm_plants_not_in_rsa.csv",
        rsa_only="data/za_audit/za_rsa_plants_not_in_ppm.csv",
        substations_comparison="data/za_audit/za_substations_comparison.csv",
        rsa_substations_derived="data/za_audit/za_rsa_substations_derived.csv",
        ratings_comparison="data/za_audit/za_osm_vs_stclair_ratings_comparison.csv",
        report="doc/za_earth_rsa_baseline_diagnostic.md",
    log:
        "logs/" + RDIR + "build_za_earth_rsa_diagnostic.log",
    benchmark:
        "benchmarks/" + RDIR + "build_za_earth_rsa_diagnostic"
    script:
        "scripts/build_za_earth_rsa_diagnostic.py"
```

Note: `za_grid_reconciliation.csv` is updated in-place. It is declared with
`ancient()` on the input side to prevent Snakemake from treating it as
outdated. `za_powerplant_reconciliation.csv` is also updated in-place (PPM
back-fill); it is declared only as input — the side-effect is documented
in the report.

---

## New Script and Package

```text
scripts/build_za_earth_rsa_diagnostic.py    — master orchestrator
scripts/za_diagnostic/__init__.py
scripts/za_diagnostic/fleet_comparison.py   — Comparison 1
scripts/za_diagnostic/grid_voltage.py       — Comparison 2
scripts/za_diagnostic/substations.py        — Comparison 3
scripts/za_diagnostic/ratings_comparison.py — Comparison 4
scripts/za_diagnostic/plots.py              — shared plot helpers
scripts/za_diagnostic/report.py             — canonical markdown report writer
notebooks/za_validation/10_diagnostic/earth_rsa_diagnostic.ipynb
```

---

## Outputs

| File | Description |
|---|---|
| `data/za_audit/za_ppm_vs_rsa_fleet_comparison.csv` | Per-carrier capacity delta: PPM vs RSA |
| `data/za_audit/za_ppm_plants_not_in_rsa.csv` | PPM plants with no RSA match |
| `data/za_audit/za_rsa_plants_not_in_ppm.csv` | RSA plants with no PPM match |
| `data/za_audit/za_grid_reconciliation.csv` | Updated in-place: RSA per-voltage columns filled |
| `data/za_audit/za_substations_comparison.csv` | Per-voltage OSM vs RSA substation count delta |
| `data/za_audit/za_rsa_substations_derived.csv` | Unique RSA substations derived from line endpoints |
| `data/za_audit/za_osm_vs_stclair_ratings_comparison.csv` | Per-corridor OSM s_nom vs St Clair N-1 |
| `data/za_audit/za_powerplant_reconciliation.csv` | Updated in-place: `capacity_mw_ppm` back-filled |
| `doc/za_earth_rsa_baseline_diagnostic.md` | Canonical diagnostic report (with embedded PNGs) |
| `doc/za_validation/figures/10_diagnostic/*.png` | Static plots (8 figures) |
| `notebooks/za_validation/10_diagnostic/earth_rsa_diagnostic.ipynb` | Validation notebook |
| `doc/za_validation/figures/10_diagnostic/earth_rsa_diagnostic.html` | HTML export of executed notebook |

No file written by modules 01–09 is overwritten except `za_grid_reconciliation.csv`
and `za_powerplant_reconciliation.csv` (in-place NaN fill of pre-allocated
columns; no schema change).

---

## Acceptance Gates (Summary)

1. `za_ppm_vs_rsa_fleet_comparison.csv` has one row per carrier; no NaN totals.
2. `capacity_mw_ppm` back-filled in `za_powerplant_reconciliation.csv` for PPM-matched rows.
3. `za_grid_reconciliation.csv` has no NaN in `rsa_line_count` or `rsa_length_km`
   for the four voltage rows.
4. `za_substations_comparison.csv` covers four voltage buckets + `other_kv` +
   `220kv_plus_total`.
5. `za_osm_vs_stclair_ratings_comparison.csv` covers all 65 corridors.
6. `doc/za_earth_rsa_baseline_diagnostic.md` exists and documents all four
   comparisons with key numbers.
7. Notebook `earth_rsa_diagnostic.ipynb` executes top-to-bottom; HTML export
   produced (or warning logged if jupyter unavailable).
8. All 8 plot PNGs present in `doc/za_validation/figures/10_diagnostic/`.

---

## Out of Scope

- Demand profile comparison (GEGIS vs Eskom). The GEGIS source was overwritten
  by module 06; comparison provides little signal.
- Renewable profile comparison (atlite vs RSA plant-specific availability) —
  deferred; requires re-running atlite.
- Cost delta table (PPM technology-data defaults vs ZA-specific) — covered by
  module 07 audit; not repeated here.
- Modifications to `custom_powerplants.csv`, `custom_busmap_elec_s_34.csv`,
  any config YAML — strictly out of scope.
