# Plan: Module 10 — Earth–RSA Baseline Diagnostic

## Context

Module 10 is the final calibration module for the ZA PyPSA-Earth pipeline. It is
audit-only — no model inputs are modified. Its purpose: quantify how wrong the V1
model would have been without the ZA overrides from modules 06–09. It implements
5 comparisons (PPM fleet, grid voltage, buses, line ratings, demand profile) and
writes a canonical diagnostic report.

Neither `scripts/za_diagnostic/` package nor
`scripts/build_za_earth_rsa_diagnostic.py` exist. Both must be created. The
Snakemake rule must be added to `Snakefile`.

---

## Pre-flight State (confirmed by inspection)

| Item | State |
|---|---|
| `networks/za_2023_fixed_validation/elec_s_34.nc` | EXISTS |
| `data/za_audit/za_powerplant_reconciliation.csv` | 229 rows; `capacity_mw_ppm` and `source_ppm` are blank |
| `data/za_audit/za_grid_reconciliation.csv` | 6 rows; `rsa_line_count`/`rsa_length_km` are NaN for voltage rows |
| `networks/za_2023_fixed_validation/base.nc` | EXISTS (1,606 raw OSM buses, 2,138 lines) |
| `networks/za_2023_fixed_validation/elec_s.nc` | EXISTS (803 simplified buses) |
| `data/za_audit/za_custom_busmap_coverage.csv` | EXISTS (803 buses → 34 regions; mean 23.6 buses/region) |
| `data/bundle/supply_regions/rsa_supply_regions.gpkg` | EXISTS at `pypsa_rsa_root`; layer `'34'`; 34 features with `SupplyArea`/`name` columns |
| `data/za_audit/za_rsa_existing_lines_220kv_plus.geojson` | EXISTS (324 features, `NOMINAL_VO` property) |
| `data/za_audit/za_rsa_interregional_transfer_limits.csv` | EXISTS (65 corridors, `st_clair_n1_mw` column) |
| `data/za_validation/za_2023_demand_profile.csv` | EXISTS (8760 rows, `rsa_contracted_demand_mw`) |
| `data/ssp2-2.6/2030/era5_2023_custom/Africa.csv` | EXISTS but already overwritten with Eskom data |
| `data/ssp2-2.6/2030/era5_2023/Africa.csv` | Does NOT exist |

**Consequence for Comparison 4:** GEGIS values are unavailable — `gegis_value = null` with explanatory note.

---

## Files to Create

```text
scripts/za_diagnostic/__init__.py
scripts/za_diagnostic/fleet_comparison.py    # Comparison 1
scripts/za_diagnostic/grid_voltage.py        # Comparison 2
scripts/za_diagnostic/ratings_comparison.py  # Comparison 3
scripts/za_diagnostic/demand_comparison.py   # Comparison 4
scripts/za_diagnostic/report.py              # markdown report writer
scripts/build_za_earth_rsa_diagnostic.py     # master orchestrator
```

## Files to Modify

```text
Snakefile    # add build_za_earth_rsa_diagnostic rule
```

---

## Script Pattern (follow existing `build_za_*` convention)

All existing scripts follow this pattern — replicate it exactly:

- Dual-mode entry: `_main_from_snakemake()` checks `globals().get("snakemake")` + `_main_from_cli()` with argparse
- Config resolved from `snakemake.config` (not `snakemake.input`/`output`)
- Paths computed from config: `RDIR = config["run"]["name"] + "/"` for network path
- Logging via `logging.getLogger("build_za_earth_rsa_diagnostic")`
- Consistent path constants at top of orchestrator

---

## Implementation Detail

### `fleet_comparison.py` — Comparison 1

1. Attempt `import powerplantmatching as pm; ppl = pm.powerplants(from_url=False); za_ppm = ppl[ppl.Country == 'ZA']`
2. Fallback: read `resources/za_2023_fixed_validation/powerplants.csv` if PPM fails
3. Carrier normalization table (PPM → ZA):
   - `Hard Coal` → `coal`
   - `Nuclear` → `nuclear`
   - `Oil` → `ocgt_diesel`
   - `Natural Gas` → `ocgt_gas`
   - `Hydro` → `hydro`
   - `Run-Of-River` → `ror`
   - `Pumped Storage` → `PHS`
   - `Solar` → `solar`
   - `Onshore` → `onwind`
   - `CSP` → `csp`
   - `Batteries` → `battery`
   - `Bioenergy` → `bioenergy`
4. Fuzzy match each RSA row to PPM: same carrier + `haversine(lat/lon) < 20 km` + capacity within 30%
5. Back-fill `capacity_mw_ppm` and `source_ppm` in `za_powerplant_reconciliation.csv`; unmatched → `source_ppm = "no_ppm_match"`
6. Aggregate by carrier → `za_ppm_vs_rsa_fleet_comparison.csv`
7. Write `za_ppm_plants_not_in_rsa.csv` (PPM rows unmatched) and `za_rsa_plants_not_in_ppm.csv` (RSA rows unmatched)

### `grid_voltage.py` — Comparison 2

1. Load GeoJSON via `json` stdlib (no geopandas dependency)
2. Group features by `NOMINAL_VO` into buckets: 220, 275, 400, 765
3. Haversine length per `LineString` using `math` stdlib
4. For each bucket: count lines, sum length km, mean length km
5. Cross-check: sum across 220+275+400+765 should be ≈151 lines / 21,390 km (the `rsa_220kv_plus_aggregate` row)
6. Rewrite `za_grid_reconciliation.csv` in-place: fill `rsa_line_count`, `rsa_length_km`; add `rsa_mean_length_km`, `delta_line_count`, `delta_length_km`, `osm_coverage_ratio` columns

### `ratings_comparison.py` — Comparison 3

1. Load `networks/za_2023_fixed_validation/elec_s_34.nc` using `pypsa.Network`
2. For each corridor in `za_rsa_interregional_transfer_limits.csv`: find `n.lines` where `(bus0 == row.bus0 and bus1 == row.bus1)` or `(bus0 == row.bus1 and bus1 == row.bus0)`
3. Sum `n.lines.s_nom` for matched lines → `osm_s_nom_total_mw`
4. `ratio_osm_to_stclair = osm_s_nom_total_mw / st_clair_n1_mw`; direction: `osm_over` > 1.2, `osm_under` < 0.8, `within_20pct` otherwise
5. Unmatched corridors → `osm_s_nom_total_mw = NaN`, `notes = "no_osm_lines_found"`
6. Write `za_osm_vs_stclair_ratings_comparison.csv`

### `demand_comparison.py` — Comparison 4

1. Check `data/ssp2-2.6/2030/era5_2023_custom/Africa.csv` — values match Eskom demand exactly → already overwritten; GEGIS unavailable
2. Check `data/ssp2-2.6/2030/era5_2023/Africa.csv` — does not exist
3. Set `gegis_value = null` for all metrics with `notes = "GEGIS source overwritten by module 06; era5_2023 original not present"`
4. Load Eskom demand; compute: `annual_total_twh`, `peak_mw`, `min_mw`, `load_factor_pct` (mean/peak × 100); `monthly_mape_pct = null`, `seasonal_shape_correlation = null` (both sides needed)
5. Write `za_demand_gegis_vs_eskom_comparison.csv`

### `report.py` — Report Writer

Reads all 4 output CSVs and writes `doc/za_earth_rsa_baseline_diagnostic.md` with:

- Section per comparison with key numbers
- Summary table of deltas
- Note on what was skipped (GEGIS unavailable)

### `build_za_earth_rsa_diagnostic.py` — Orchestrator

```python
def _run(cfg):
    from za_diagnostic.fleet_comparison import run_fleet_comparison
    from za_diagnostic.grid_voltage import run_grid_voltage
    from za_diagnostic.ratings_comparison import run_ratings_comparison
    from za_diagnostic.demand_comparison import run_demand_comparison
    from za_diagnostic.report import write_report
    run_fleet_comparison(cfg)
    run_grid_voltage(cfg)
    run_ratings_comparison(cfg)
    run_demand_comparison(cfg)
    write_report(cfg)
```

### Snakemake Rule

Add after `build_za_grid_spatial` rule (line ~240 in Snakefile):

```python
rule build_za_earth_rsa_diagnostic:
    input:
        reconciliation="data/za_audit/za_powerplant_reconciliation.csv",
        existing_lines="data/za_audit/za_rsa_existing_lines_220kv_plus.geojson",
        grid_reconciliation=ancient("data/za_audit/za_grid_reconciliation.csv"),
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

---

## Acceptance Gate Verification

After implementation, run:

```bash
cd /Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth
python scripts/build_za_earth_rsa_diagnostic.py --configfile configs/za/za_2023_fixed_validation.yaml
```

Check:

1. `data/za_audit/za_ppm_vs_rsa_fleet_comparison.csv` — one row per carrier, no NaN totals
2. `capacity_mw_ppm` back-filled in `za_powerplant_reconciliation.csv` for PPM-matched rows
3. `za_grid_reconciliation.csv` — no NaN in `rsa_line_count`/`rsa_length_km` for 4 voltage rows
4. `za_osm_vs_stclair_ratings_comparison.csv` — all 65 corridors present
5. `za_demand_gegis_vs_eskom_comparison.csv` — 6 metric rows (null GEGIS values with note)
6. `doc/za_earth_rsa_baseline_diagnostic.md` — exists, documents all 4 comparisons
