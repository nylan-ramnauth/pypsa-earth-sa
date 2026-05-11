# 10 Earth–RSA Baseline Diagnostic

## Goal

Quantify the gap between what PyPSA-Earth retrieves by default for South Africa
and what PyPSA-RSA uses. This module is **audit-only**: it produces no model
inputs and does not modify any file written by modules 01–09. All outputs are
diagnostic CSVs and one canonical report.

The four comparisons below answer the question: *how wrong would the V1 model be
if the ZA overrides from modules 06–09 had not been applied?*

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
(line ratings, demand profile).

---

## Comparison 1 — Conventional and Renewable Fleet (PPM vs RSA)

### Objective

Identify which plants IRENA/powerplantmatching would supply for ZA by default,
which are missing relative to the RSA fleet, and which PPM entries have no RSA
counterpart.

### Procedure

1. Read `configs/za/za_2023_fixed_validation.yaml`. Temporarily override
   `electricity.custom_powerplants` to `Country in ['ZA']` **in memory only** —
   do not write to the YAML. Run `powerplantmatching` (PPM) to extract the ZA
   slice of the global database:

   ```python
   import powerplantmatching as pm
   ppl = pm.powerplants(from_url=False)
   za_ppm = ppl[ppl.Country == 'ZA'].copy()
   ```

   If PPM data is not available locally, read
   `resources/za_2023_fixed_validation/powerplants.csv` if it exists from a
   prior build; otherwise trigger `build_powerplants` with a temporary config
   that uses `custom_powerplants: Country in ['ZA']` and saves the intermediate
   file.

2. Load `data/za_audit/za_powerplant_reconciliation.csv` (229 rows from module
   08). For each row, attempt fuzzy-match to PPM by (carrier, lat/lon ±20 km,
   capacity ±30%). Record matched PPM capacity in `capacity_mw_ppm` and
   `source_ppm`.

3. Produce `data/za_audit/za_ppm_vs_rsa_fleet_comparison.csv`:

   ```text
   carrier, capacity_mw_ppm_total, capacity_mw_rsa_total,
   delta_mw, n_plants_ppm_only, n_plants_rsa_only,
   n_plants_matched, notes
   ```

   One row per carrier. Carriers: coal, nuclear, oil (OCGT diesel), gas
   (OCGT gas), hydro, ror, PHS, solar, onwind, csp, battery, bioenergy, other.

4. Write a "plants-in-PPM-only" appendix CSV:
   `data/za_audit/za_ppm_plants_not_in_rsa.csv` — PPM rows with no RSA match.

5. Write a "plants-in-RSA-only" appendix CSV:
   `data/za_audit/za_rsa_plants_not_in_ppm.csv` — RSA rows with no PPM match.

6. Back-fill `capacity_mw_ppm` and `source_ppm` in
   `data/za_audit/za_powerplant_reconciliation.csv` for matched rows.

### Acceptance Gates

- `za_ppm_vs_rsa_fleet_comparison.csv` exists, one row per carrier, no NaN
  totals.
- `capacity_mw_ppm` back-filled for every PPM-matched row in the reconciliation
  CSV; unmatched rows explicitly flagged `source_ppm = "no_ppm_match"`.
- Delta for Hard Coal and Nuclear documented; explain any >500 MW discrepancy.

---

## Comparison 2 — Grid Per-Voltage Class (OSM vs RSA GeoJSON)

### Objective

Fill the NaN cells in `za_grid_reconciliation.csv` with a per-voltage breakdown
of the RSA GeoJSON, enabling a direct OSM vs RSA line count and length comparison
by voltage class.

### Procedure

1. Read `data/za_audit/za_rsa_existing_lines_220kv_plus.geojson` (324 features).
   The voltage is stored in property `NOMINAL_VO` (confirmed float, e.g. 275.0).

2. Group by voltage bucket (220, 275, 400, 765 kV). Compute per group: line
   count, total length km (Haversine on `LineString` coordinates), mean length
   km.

3. Update `data/za_audit/za_grid_reconciliation.csv` — fill `rsa_line_count` and
   `rsa_length_km` for the four per-voltage rows. Add `rsa_mean_length_km` column
   if not present. Rewrite the file in-place.

4. Add derived columns to the reconciliation CSV:
   - `delta_line_count = osm_line_count - rsa_line_count`
   - `delta_length_km = osm_length_km - rsa_length_km`
   - `osm_coverage_ratio = osm_length_km / rsa_length_km`

### Acceptance Gates

- No NaN values in `rsa_line_count` or `rsa_length_km` for the four voltage rows.
- `osm_coverage_ratio` computed for all four voltage classes.
- Total RSA length across voltage classes cross-checks against the
  `rsa_220kv_plus_aggregate` row already present (151 lines, 21,390 km).

---

## Comparison 3 — Line Ratings (OSM Type-Based s_nom vs St Clair N-1)

### Objective

Quantify how far PyPSA-Earth's default line thermal ratings deviate from the
St Clair N-1 limits computed in module 09, for each of the 65 corridors.

### Procedure

1. Load `networks/za_2023_fixed_validation/elec_s_34.nc` using PyPSA.

2. For each of the 65 corridors in
   `data/za_audit/za_rsa_interregional_transfer_limits.csv`, identify the
   corresponding line(s) in `n.lines` by matching `bus0`/`bus1` region names
   against `n.lines.bus0`/`n.lines.bus1` (post-clustering, bus names are region
   names).

3. Read `n.lines.s_nom` for each matched line. Sum per corridor to get
   `osm_s_nom_total_mw`.

4. Produce `data/za_audit/za_osm_vs_stclair_ratings_comparison.csv`:

   ```text
   bus0, bus1, n_lines, voltage_max_kv, osm_s_nom_total_mw,
   st_clair_n1_mw, ratio_osm_to_stclair, direction,
   notes
   ```

   `direction`: `"osm_over"` if `ratio > 1.2`, `"osm_under"` if `ratio < 0.8`,
   `"within_20pct"` otherwise.

5. Summarise: count and MW of over-rated vs under-rated vs within-tolerance
   corridors.

### Acceptance Gates

- All 65 corridors matched or explained (document unmatched corridors — may
  occur if OSM does not carry a line between two regions).
- `ratio_osm_to_stclair` populated for all matched corridors.
- Summary row produced: total MW over-rated, under-rated, within tolerance.

---

## Comparison 4 — Demand Profile (GEGIS SSP2-2.6 vs Eskom 2023 Measured)

### Objective

Show what Earth's default demand model would have used for ZA and how it
compares to the Eskom 2023 measured demand applied in module 06.

### Procedure

1. Load the GEGIS Africa.csv at
   `data/ssp2-2.6/2030/era5_2023_custom/Africa.csv`. This file was written by
   module 06 as the custom 2023 demand route. Read the ZA national column (the
   implementing agent must inspect column names; the ZA entry may be `ZA` or a
   bus-prefixed variant).

   If the Africa.csv was already overwritten with the Eskom-derived profile in
   module 06, read the original GEGIS file from
   `data/ssp2-2.6/2030/era5_2023/Africa.csv` (un-modified upstream file) and
   extract the ZA column. If neither is available with original GEGIS values,
   document the limitation and skip the GEGIS side of the comparison — record
   `gegis_total_twh = null` with a note explaining the source was overwritten.

2. Load `data/za_validation/za_2023_demand_profile.csv` (8760 rows,
   `rsa_contracted_demand_mw` column). Eskom 2023 total: 225.9 TWh.

3. Produce `data/za_audit/za_demand_gegis_vs_eskom_comparison.csv`:

   ```text
   metric, gegis_value, eskom_value, delta_pct, notes
   ```

   Required metrics:
   - `annual_total_twh`
   - `peak_mw`
   - `min_mw`
   - `load_factor_pct` (mean/peak × 100)
   - `monthly_mape_pct` (mean absolute percentage error of monthly totals)
   - `seasonal_shape_correlation` (Pearson r of monthly totals)

### Acceptance Gates

- CSV exists with all six metrics populated (or `gegis_value = null` with note
  if GEGIS source unavailable).
- `annual_total_twh` delta and `monthly_mape_pct` both present and documented.

---

## New Snakemake Rule

```python
rule build_za_earth_rsa_diagnostic:
    input:
        reconciliation="data/za_audit/za_powerplant_reconciliation.csv",
        existing_lines="data/za_audit/za_rsa_existing_lines_220kv_plus.geojson",
        grid_reconciliation="data/za_audit/za_grid_reconciliation.csv",
        elec_s_34=f"networks/{RDIR}elec_s_34.nc",
        transfer_limits="data/za_audit/za_rsa_interregional_transfer_limits.csv",
        demand_eskom="data/za_validation/za_2023_demand_profile.csv",
    output:
        fleet_comparison="data/za_audit/za_ppm_vs_rsa_fleet_comparison.csv",
        ppm_only="data/za_audit/za_ppm_plants_not_in_rsa.csv",
        rsa_only="data/za_audit/za_rsa_plants_not_in_ppm.csv",
        ratings_comparison="data/za_audit/za_osm_vs_stclair_ratings_comparison.csv",
        demand_comparison="data/za_audit/za_demand_gegis_vs_eskom_comparison.csv",
        report="doc/za_earth_rsa_baseline_diagnostic.md",
    log:
        f"logs/{RDIR}build_za_earth_rsa_diagnostic.log",
    script:
        "scripts/build_za_earth_rsa_diagnostic.py"
```

Note: `za_grid_reconciliation.csv` is updated in-place (both input and output).
Declare it as both input and output in Snakemake; use `ancient()` on the input
side to prevent a circular dependency:
`ancient("data/za_audit/za_grid_reconciliation.csv")`.

---

## New Script and Package

```text
scripts/build_za_earth_rsa_diagnostic.py    — master orchestrator
scripts/za_diagnostic/__init__.py
scripts/za_diagnostic/fleet_comparison.py   — Comparison 1
scripts/za_diagnostic/grid_voltage.py       — Comparison 2
scripts/za_diagnostic/ratings_comparison.py — Comparison 3
scripts/za_diagnostic/demand_comparison.py  — Comparison 4
scripts/za_diagnostic/report.py             — canonical markdown report writer
```

---

## Outputs

| File | Description |
|---|---|
| `data/za_audit/za_ppm_vs_rsa_fleet_comparison.csv` | Per-carrier capacity delta: PPM vs RSA |
| `data/za_audit/za_ppm_plants_not_in_rsa.csv` | PPM plants with no RSA match |
| `data/za_audit/za_rsa_plants_not_in_ppm.csv` | RSA plants with no PPM match |
| `data/za_audit/za_grid_reconciliation.csv` | Updated in-place: RSA per-voltage columns filled |
| `data/za_audit/za_osm_vs_stclair_ratings_comparison.csv` | Per-corridor OSM s_nom vs St Clair N-1 |
| `data/za_audit/za_demand_gegis_vs_eskom_comparison.csv` | Six demand metrics: GEGIS vs Eskom |
| `doc/za_earth_rsa_baseline_diagnostic.md` | Canonical diagnostic report |
| `notebooks/za_validation/10_diagnostic/earth_rsa_diagnostic.ipynb` | Validation notebook |
| `doc/za_validation/figures/10_diagnostic/earth_rsa_diagnostic.html` | HTML export |

No file written by modules 01–09 is overwritten except `za_grid_reconciliation.csv`
(in-place fill of NaN cells only).

---

## Acceptance Gates

1. `za_ppm_vs_rsa_fleet_comparison.csv` has one row per carrier, no NaN totals.
2. `capacity_mw_ppm` back-filled in `za_powerplant_reconciliation.csv` for all
   PPM-matched rows.
3. `za_grid_reconciliation.csv` has no NaN in `rsa_line_count` or `rsa_length_km`.
4. `za_osm_vs_stclair_ratings_comparison.csv` covers all 65 corridors.
5. `za_demand_gegis_vs_eskom_comparison.csv` has all six metrics (null with note
   acceptable if GEGIS source was overwritten).
6. `doc/za_earth_rsa_baseline_diagnostic.md` exists and documents all four
   comparisons with key numbers.
7. Notebook executes without error; HTML exported.

---

## Out of Scope

- Do not modify `custom_powerplants.csv`, `custom_busmap_elec_s_34.csv`, or any
  config YAML.
- Do not re-run `build_powerplants` with `replace` disabled against the live
  network pipeline; query PPM directly or use an intermediate CSV.
- Renewable profile comparison (atlite vs RSA plant-specific availability) —
  deferred; requires re-running atlite.
- Cost delta table (PPM technology-data defaults vs ZA-specific) — partially
  covered by module 07 audit; not repeated here.
