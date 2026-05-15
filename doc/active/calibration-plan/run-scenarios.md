# Re-run All SA 2023 Scenarios — Full Setup to Results

---

## 1. Clone repos

```bash
# Main model (our fork of pypsa-earth)
git clone https://github.com/nylanramnauth-droid/pypsa-earth-sa.git pypsa-earth
cd pypsa-earth

# pypsa-rsa — needed for fleet data, EAF workbook, and OPC workbook
# Clone alongside pypsa-earth (same parent directory)
cd ..
git clone https://github.com/nylanramnauth-droid/pypsa-rsa.git pypsa-rsa

# Pin pypsa-rsa to the validated commit
cd pypsa-rsa
git checkout 0831ce243f0badbba6f09b418c2b57774ea89a5f
cd ../pypsa-earth
```

> **IMPORTANT — Edit before running on any machine other than the original workstation:**
> `za_2023_fixed_validation.yaml` contains an absolute path for `pypsa_rsa_root`
> (`/Users/nylan/.../pypsa-rsa`). Update this to your local absolute path before
> running any builder. Also update `za.operational_constraints.workbook` if your
> pypsa-rsa is not a sibling directory of pypsa-earth.

The config uses an absolute path for `pypsa_rsa_root` and a relative path for the OPC/EAF workbooks:
```yaml
pypsa_rsa_root: "/Users/nylan/.../pypsa-rsa"                       # absolute
za.operational_constraints.workbook: ../pypsa-rsa/scenarios/...    # relative to pypsa-earth/ working dir
```
**If your directory layout differs, update both in `za_2023_fixed_validation.yaml` before running anything:**
- `pypsa_rsa_root` — used by audit and fleet scripts
- `za.operational_constraints.workbook` — used by solves 3 and 4; assumes pypsa-rsa is a sibling directory of pypsa-earth

---

## 2. Create and activate environment

```bash
conda env create -f envs/za_environment.yaml
conda activate pypsa-earth-za
```

Key packages locked: `python=3.11.13`, `pypsa=0.30.3`, `snakemake-minimal=7.32.4`, `gurobi=12.0.3`.

---

## 3. Gurobi license

A valid `gurobi.lic` must exist at `~/gurobi.lic`. The env contains `gurobipy=12.0.3`; the local binary is `gurobi_cl` 13.0.0 — both work for solving.

If you need a new license: https://www.gurobi.com/academia/academic-program-and-licenses/

---

## 4. Retrieve external data (first run only)

All three steps below run automatically as Snakemake dependencies when you later build the network. Trigger them explicitly first to isolate download failures before any heavy computation.

### 4a. Standard data bundle

GADM shapes, EEZ boundaries, Copernicus land cover, etc. Downloaded from Zenodo.

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml --cores 4 \
  retrieve_databundle_light
```

### 4b. OSM grid data

Downloads ZA transmission network (substations, lines, generators) from OpenStreetMap via Geofabrik.

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml --cores 4 \
  download_osm_data
```

Then clean and build the OSM network:

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml --cores 4 \
  build_osm_network
```

### 4c. Cost data

Downloads `costs_2030.csv` from the PyPSA technology-data repository (v0.13.2) into `resources/za_2023_fixed_validation/`. Used by `add_electricity` and downstream rules.

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml --cores 4 \
  resources/za_2023_fixed_validation/costs_2030.csv
```

`build_za_costs_fuels_efficiencies` also reads `data/costs_2030.csv` directly (not the run-specific resources path). That file is not in git. Create it once from the tracked `data/costs.csv`:

```bash
cp data/costs.csv data/costs_2030.csv
```

### 4d. Powerplant matching (PPM)

Downloads and matches plant data from global registries (GEO, CARMA, ENTSOE, etc.) for ZA. Even though the calibrated runs use `custom_powerplants: replace` (PPM fleet is discarded), Snakemake still runs `build_powerplants` as a dependency. The STOCK run uses PPM directly.

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml --cores 4 \
  build_powerplants
```

---

## 5. ERA5 2023 weather cutout

`cutouts/cutout-2023-era5.nc` is not in git (large binary). Two options:

**Option A — copy from the existing working repo (faster):**
```bash
cp /path/to/working/pypsa-earth/cutouts/cutout-2023-era5.nc cutouts/
```
Verify SHA256 after copying:
```bash
shasum -a 256 cutouts/cutout-2023-era5.nc
# expected: 0c6b22fa6b8a0a469cc24460df2014fdb9c041035985dfb3b1aa7d6608e19076
```

**Option B — build from CDS (requires a Copernicus account):**

Complete section 4a first — `build_cutout` needs country shapes from the databundle.

1. Create a CDS account at https://cds.climate.copernicus.eu and get your API key.
2. Write `~/.cdsapirc`:
   ```
   url: https://cds.climate.copernicus.eu/api/v2
   key: <your-uid>:<your-api-key>
   ```
3. Temporarily enable cutout building in `configs/za/za_2023_fixed_validation.yaml`:
   ```yaml
   enable:
     retrieve_cutout: false
     build_cutout: true   # ← change this line
   ```
4. Build:
   ```bash
   snakemake --configfile configs/za/za_2023_fixed_validation.yaml --cores 4 \
     cutouts/cutout-2023-era5.nc
   ```
5. Set `build_cutout` back to `false` after the cutout is built.

---

## Config reference

Two configs. Calibrated solves 1–4 use `za_2023_fixed_validation.yaml`. STOCK uses `za_2023_stock_baseline.yaml`.

**The only config change in the entire workflow is switching configs for the STOCK run.** EAF, OPC, and CAP are controlled entirely by the Snakemake target path — not by config flags.

| Key | `za_2023_fixed_validation.yaml` | `za_2023_stock_baseline.yaml` |
|---|---|---|
| `run.name` | `za_2023_fixed_validation` | `za_2023_stock_baseline` |
| `costs.output_currency` | `ZAR` | `EUR` |
| `electricity.custom_powerplants` | `replace` (227-row ZA fleet) | `false` (PPM fleet) |
| `electricity.conventional_carriers` | `[coal, nuclear]` | `[nuclear, oil, OCGT, CCGT, coal, biomass]` |
| `electricity.estimate_renewable_capacities.stats` | `false` | `"irena"` (IRENA 2023 scaling) |
| `za.operational_constraints.workbook` | path to pypsa-rsa `operational_constraints.xlsx` | *(absent)* |
| `renewable.hydro.multiplier` | `1.20` | `1.1` |
| `za_stock_baseline` | *(absent)* | `true` (nuclear CF = 1.0, no dynamic overlay) |

---

## Dry-run any target before building

Always verify the job plan before running a heavy step:

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml --dry-run \
  results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc
```

> **Do not use `-F`** — it triggers the Module 09 DAG quirk where `data/custom_powerplants.csv` is treated as upstream-touched and rebuilds the entire fleet pipeline from scratch.

---

## Calibrated runs (solves 1–4)

There are only **2 prepared input networks**. Solve 1 uses Network A. Solves 2, 3, and 4 all use Network B — same network, different constraints injected at solve time by `solve_network.py`.

```
Network A:  networks/za_2023_fixed_validation/elec_s_34_ec_lc1_NoCO2-1H.nc
                └── used by solve 1

            apply_za_coal_eaf  (writes station-level weekly coal p_max_pu)
                │
Network B:  networks/za_2023_fixed_validation/elec_s_34_ec_lc1_NoCO2-1H-EAF.nc
                ├── solve 2  — no extra constraints at solve time
                ├── solve 3  — OPC injected at solve time (weekly OCGT CF cap + nuclear min)
                └── solve 4  — OPC + annual OCGT energy cap injected at solve time
```

### Build Step 1 of 4 — Data and audit artefacts

Produces the ZA fleet, costs, carrier taxonomy, and grid files.

> **Warning:** `build_za_grid_spatial` requires `elec_s.nc` as input, which triggers the full OSM → base network → add_electricity → simplify pipeline automatically. This is expected but takes several hours on a fresh clone. Complete sections 4 and 5 before running this step.

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml --cores 4 \
  build_za_carrier_taxonomy \
  build_za_costs_fuels_efficiencies \
  build_za_fleet_reconciliation \
  build_za_source_audits \
  build_za_grid_spatial
```

Key outputs:
- `data/za_audit/za_carrier_taxonomy.csv`
- `data/za_audit/za_local_carrier_cost_rows.csv` — ZA-specific cost rows consumed by `apply_za_local_carriers`
- `data/za_audit/za_costs_fuels_efficiencies_audit.csv`
- `data/custom_powerplants.csv` — 135-row ZA fleet, no Sasol (original 227-row count was pre-Module-12 Sasol removal)
- `data/custom_busmap_elec_s_34.csv` — 34 Eskom supply region busmap
- `data/za_audit/za_named_plant_inventory.csv`

### Build Step 2 of 4 — Cluster to 34 regions

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml --cores 4 \
  networks/za_2023_fixed_validation/elec_s_34.nc
```

Output: 34 buses, 72 lines, 109 generators (custom busmap applied).

### Build Step 3 of 4 — Build Network A

Snakemake runs these sub-steps in order automatically:
1. `build_za_custom_lines` — builds `data/za_audit/za_custom_missing_lines.csv` (missing 275/400 kV corridors)
2. `apply_za_custom_lines` — injects those lines into `elec_s_34.nc`, creates `.pre_custom.nc` backup
3. `apply_za_local_carriers` — attaches `ocgt_diesel` / `ocgt_gas`, creates `.pre_local.nc` backup
4. `add_extra_components` — adds CSP Stores/Links → `elec_s_34_ec.nc`
5. `za_fix_csp_links_stores` — pins CSP to 500 MW / 2850 MWh, non-extendable, creates `.pre_csp.nc` backup
6. `prepare_network` — applies `lc1` (fixed transmission), `NoCO2`, 1H snapshots

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml --cores 4 \
  networks/za_2023_fixed_validation/elec_s_34_ec_lc1_NoCO2-1H.nc
```

**→ Network A. Used by solve 1.**

### Build Step 4 of 4 — Build Network B (apply coal EAF overlay)

Reads `pypsa-rsa/scenarios/Coal_Flexibilisation/sub_scenarios/plant_availability.xlsx` (**BASE scenario**, filtered to `scenario == 'BASE'`). Writes station-level weekly coal `p_max_pu` into Network A. Network A preserved as `.pre_eaf.nc` backup.

> **Note:** The EAF workbook (`plant_availability.xlsx`) uses the **BASE** scenario. The OPC/CAP workbook (`operational_constraints.xlsx`) uses the **HIGH_GAS** scenario. These are two different workbooks with different scenario filters — do not conflate them.

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml --cores 4 \
  networks/za_2023_fixed_validation/elec_s_34_ec_lc1_NoCO2-1H-EAF.nc
```

**→ Network B. Used by solves 2, 3, and 4.**

Audit: `data/za_audit/za_coal_eaf_audit.csv`

---

### Solve 1 — Structural baseline

Input: Network A. No EAF, no OPC, no CAP.

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml --cores 20 \
  results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H.nc
```

### Solve 2 — EAF only

Input: Network B. No additional constraints at solve time.

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml --cores 20 \
  results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF.nc
```

### Solve 3 — EAF + OPC

Input: Network B. At solve time, `solve_network.py` reads `operational_constraints.xlsx` (HIGH_GAS scenario) and injects: `ocgt_diesel` weekly CF max 0.50, nuclear hourly CF min 1.0.

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml --cores 20 \
  results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC.nc
```

### Solve 4 — EAF + OPC + CAP ← Module 13 accepted solve

Input: Network B. Same constraints as solve 3, plus annual OCGT energy cap of 5.5 TWh. **The cap is not hardcoded — it is a row in `pypsa-rsa/scenarios/Coal_Flexibilisation/sub_scenarios/operational_constraints.xlsx`** (HIGH_GAS scenario, scope `global`, carrier `ocgt_diesel`, constraint type `output_energy / year / max`, value 5,500,000 MWh), added 2026-05-13. To change the cap, edit that workbook row and re-run this solve.

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml --cores 20 \
  results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc
```

---

## STOCK baseline (Module 13b)

Uses `za_2023_stock_baseline.yaml`. PPM fleet, EUR costs, IRENA RE scaling, no EAF hook, nuclear CF = 1.0. Same 34-region busmap and 2023 demand as the calibrated runs.

**Build Step 1 ("Data and audit artefacts") must have completed under the calibrated config.** `share_za_base_network` reads `data/custom_powerplants.csv`, `data/custom_busmap_elec_s_34.csv`, and `networks/za_2023_fixed_validation/base.nc` — all outputs of Build Step 1. **Build Step 2 ("Cluster to 34 regions") does not need to re-run** — `share_za_base_network` seeds the stock OSM/shapes/cost resources so the stock `cluster_network` starts from the calibrated base. Only the network build and solve need to run under the stock config.

### Build STOCK network

Same sub-steps as calibrated Build Step 3, but no custom fleet and no EAF hook. `za_stock_baseline: true` disables the nuclear CF overlay.

```bash
snakemake --configfile configs/za/za_2023_stock_baseline.yaml --cores 4 \
  networks/za_2023_stock_baseline/elec_s_34_ec_lc1_NoCO2-1H.nc
```

### Solve STOCK

```bash
snakemake --configfile configs/za/za_2023_stock_baseline.yaml --cores 20 \
  results/za_2023_stock_baseline/networks/elec_s_34_ec_lc1_NoCO2-1H-STOCK.nc
```

---

## Re-run validation notebooks

After any solve:

```bash
jupyter nbconvert --to notebook --execute --inplace \
  notebooks/za_validation/12_dispatch_calibration/dispatch_calibration_validation.ipynb

jupyter nbconvert --to html \
  --output-dir doc/za_validation/figures/12_dispatch_calibration/ \
  notebooks/za_validation/12_dispatch_calibration/dispatch_calibration_validation.ipynb
```

Before/after acceptance comparison:

```bash
jupyter nbconvert --to notebook --execute --inplace \
  notebooks/za_validation/12_acceptance/before_after_comparison.ipynb

jupyter nbconvert --to html \
  --output-dir doc/za_validation/figures/12_acceptance/ \
  notebooks/za_validation/12_acceptance/before_after_comparison.ipynb
```

---

## Reproduce Module 13 acceptance package

After all solves complete, run the Module 13 validation orchestrator to produce
the acceptance CSVs and manifest. This step is **required** — the acceptance
evidence package is not produced by the notebooks.

```bash
python scripts/za_validation/build_module13_validation.py \
  --configfile configs/za/za_2023_fixed_validation.yaml
```

Outputs written to `data/za_validation/`:
- `za_2023_validation_annual.csv` — per-carrier annual energy vs Eskom targets
- `za_2023_validation_capacity.csv` — per-carrier installed capacity vs anchors
- `za_2023_validation_plant_identity.csv` — 27-station identity gate
- `za_2023_validation_monthly.csv` — per-carrier monthly dispatch vs Eskom
- `za_2023_validation_hourly_metrics.csv` — RMSE / MAE / bias per carrier
- `za_2023_validation_cost_dual_frame.csv` — solver EUR + policy ZAR cost frame
- `za_2023_validation_secondary_sources.csv` — IRENA cross-check
- `za_2023_validation_manifest.json` — sha256 hashes for all 12 acceptance artefacts

For the STOCK comparison (Module 13b):

```bash
python scripts/za_validation/build_module13_validation.py \
  --configfile configs/za/za_2023_stock_baseline.yaml
```

---

## Baseline acceptance status (Module 13)

The accepted solve (Solve 4 — EAF+OPC+CAP) is accepted **with documented
limitations**, not as a clean tolerance pass. Key residuals at annual level:

| Carrier | Eskom 2023 | Delta | Tolerance | Status |
|---|---|---|---|---|
| Coal | 165,627 GWh | +11.34% | ±2% | FAIL — documented |
| Wind | — | −37% | ±2% | FAIL — ERA5 CF bias (Module 14 fix: 1.58× scale) |
| Solar PV | — | −29% | ±2% | FAIL — ERA5 CF bias (Module 14 fix: 1.40× scale) |
| Hydro | 1,992 GWh | −29.79% | ±5% | FAIL — ERA5 inflow (Module 14 fix: inflow data swap) |
| PHS | 4,294 GWh | −96.6% | ±5% | FAIL — structural (LP energy-only, no reserves) |
| Load shedding | — | −35.85% | — | diagnostic |

All failures are documented in `doc/za_model_limitations.md`. Module 14 inputs
(atlite scale factors 1.58×/1.40×/1.71×, PHS inflow replacement) address
wind/solar/hydro residuals.

---

## Notes

- Solver: Gurobi (`gurobipy=12.0.3` in env)
- Network build steps: `--cores 4` sufficient
- Solve steps: `--cores 20` (Gurobi uses `threads: 2`; rest is Snakemake overhead)
- Data bundle and OSM downloads only run once and are skipped automatically on subsequent runs
