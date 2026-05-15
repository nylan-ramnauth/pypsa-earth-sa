# Module 13d — PyPSA-RSA 2023 Dispatch Benchmark

**Target agent:** Claude Opus (standalone — no prior conversation context)
**Working directory:** `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-rsa`
**Conda environment:** `pypsa-rsa-repro`
**Solver:** Gurobi (`GRB_LICENSE_FILE=/Users/nylan/gurobi.lic`, gurobipy 13.0.2 verified)

---

## Purpose

Create a **2023 historical dispatch benchmark** in PyPSA-RSA. The goal is a solved `solved.nc` for calendar year 2023 using the same demand signal and comparable fleet conditions as the companion PyPSA-Earth calibration model (Module 12/13), so the two can be compared against each other and against Eskom observed 2023 generation data.

This is a **dispatch-only** run — no capacity expansion, no multi-year planning horizon. Single simulated year: 2023.

---

## Context

### PyPSA-RSA workflow structure

- Snakemake-based. Master config: `config.yaml`.
- Active scenario folder: `config["scenarios"]["working_folder"]` → currently `Coal_Flexibilisation`.
- Scenario rows defined in: `scenarios/<working_folder>/scenarios_to_run.xlsx`, sheet `scenario_definition`.
- Sub-scenario parameter tables: `scenarios/<working_folder>/sub_scenarios/*.xlsx`.
- Networks output: `networks/<working_folder>/<scenario>/`.
- Results output: `results/<working_folder>/<scenario>/`.

### Existing scenario S1 — do not touch

`Coal_Flexibilisation / S1` is a multi-year planning scenario (2025–2050). Do **not** modify anything under `scenarios/Coal_Flexibilisation/`. You are creating a parallel working folder `Benchmark_2023`.

### Verified data facts (gathered before writing this plan)

| Item | Value / Location | Note |
|---|---|---|
| `plant_availability.xlsx` `EAF_48` | coal EAF = 0.48 for 2023 | Data verified correct. Closest to actual Eskom 2023 coal performance (~48–52%). Use this. |
| `plant_availability.xlsx` `EAF_55` | coal EAF = **0.0055** for 2023 | **Data bug** — should be 0.55 but is 0.0055. Do not use. |
| Koeberg nuclear EAF 2023 | 0.7917 | Correct in all EAF scenarios. No change needed. |
| `annual_load.xlsx` `IRP23` 2023 | 243 TWh | Too high (projected without load shedding). Do not use. |
| `SystemEnergy2009_22.csv` | Ends **May 2020** (not 2022) | Filename is misleading. Current `reference_load_year: 2017`. Must append 2023 actuals. |
| `extendable_technologies.xlsx` sheet `active` | Columns: `BASE, NFS, NPS, NFS_NPS, P1, M2045, NO_GAS, BLEND` — all TRUE | No no-build column exists. See Step 3. |
| 2023 demand source | `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth/data/za_validation/za_2023_demand_profile.csv` | Columns: `time, rsa_contracted_demand_mw`. 8760 rows. Annual total: **225.87 TWh** (Eskom contracted demand — same input as PyPSA-Earth calibration). |

---

## Implementation Steps

### Step 1 — Append 2023 actual demand to SystemEnergy CSV

**File to modify:** `data/bundle/SystemEnergy2009_22.csv`

Read the source file:
```
/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth/data/za_validation/za_2023_demand_profile.csv
```

It has columns `time, rsa_contracted_demand_mw` with 8760 hourly rows for 2023.

Append rows to `data/bundle/SystemEnergy2009_22.csv`:
- `date` = `time` column values, formatted `YYYY-MM-DD HH:MM:SS` (match existing row format exactly)
- `pypsa_za_original` = empty
- `csir_ambitions` = empty
- `system_energy` = `rsa_contracted_demand_mw` values

The `remove_leap_day` function in `add_electricity.py` handles non-leap years correctly (2023 is not a leap year — no adjustment needed).

**Verify:** last row of `data/bundle/SystemEnergy2009_22.csv` is `2023-12-31 23:00:00`.

---

### Step 2 — Create Benchmark_2023 folder structure

```
mkdir -p scenarios/Benchmark_2023/sub_scenarios
cp scenarios/Coal_Flexibilisation/sub_scenarios/* scenarios/Benchmark_2023/sub_scenarios/
```

You will modify three of the copied files in Steps 3–4. The `scenarios_to_run.xlsx` for `Benchmark_2023` is created from scratch in Step 5.

---

### Step 3 — Add NONE column to extendable_technologies.xlsx

**File:** `scenarios/Benchmark_2023/sub_scenarios/extendable_technologies.xlsx`

Open sheet `active`. Current columns: `component, carrier, category, BASE, NFS, NPS, NFS_NPS, P1, M2045, NO_GAS, BLEND`.

Add a new column `NONE` after `BLEND`. Set every data value in this column to `False` (Python boolean, not the string `"False"`). This causes `get_carriers_from_model_file` to return an empty extendable carrier list.

> **Risk:** If pandas raises a `KeyError` when iterating over an empty DataFrame indexed by `category`, the `add_electricity` rule will fail. In that case, use the fallback: set `extendable_active: BASE` in the scenario row (Step 5) and accept that a small amount of extendable capacity may technically be available — in a single-year 2023 dispatch solve with real overnight CAPEX costs and load shedding available at R100/kWh, the optimizer will not add new capacity. Document this choice in the output.

---

### Step 4 — Add 2023_ACTUAL row to annual_load.xlsx

**File:** `scenarios/Benchmark_2023/sub_scenarios/annual_load.xlsx`

Open sheet `annual_load`. Columns include: `scenario, units, 2019, 2020, 2021, 2022, 2023, 2024, 2025, ..., source`.

Add one new row:

| Column | Value |
|---|---|
| `scenario` | `2023_ACTUAL` |
| `units` | `TWh/yr` |
| `2023` | `225.87` |
| All other year columns | empty / None |
| `source` | `Eskom 2023 actual contracted demand; za_2023_demand_profile.csv` |

The model reads only the column matching the simulation year, so leaving other years empty is safe.

---

### Step 5 — Create scenarios_to_run.xlsx

**File:** `scenarios/Benchmark_2023/scenarios_to_run.xlsx`

Create with one sheet named `scenario_definition`. Copy the header row exactly from `scenarios/Coal_Flexibilisation/scenarios_to_run.xlsx` (sheet `scenario_definition`, row 1). Add one data row:

| Column | Value | Note |
|---|---|---|
| index | 1 | |
| scenario | `S_2023BM` | |
| solver | `gurobi` | Use Gurobi |
| show | `True` | |
| export | `True` | |
| export_iteration | `0` | |
| run_scenario | `True` | |
| variable_storage_vom | `True` | |
| simulation_years | `[2023]` | Single dispatch year |
| weather | `W_P50` | Same as S1 |
| dispatch_coal_flex | `SL_0` | Same as S1 |
| regions | `1` | Single node |
| resource_area | `redz_corridors_eia` | Same as S1 |
| line_expansion | `none` | No transmission investment |
| options | `LC` | Same as S1 |
| transmission_grid | `existing` | Existing lines only — no TDP planned |
| fixed_conventional | `VAR_HR` | Existing fleet fixed |
| phased_decom | `DELAYED_ESKOM_2035` | No effect for 2023 single-year run |
| unit_committment | `True` | Same as S1 |
| endogenous_coal_decom | `True` | No effect for 2023 single-year run |
| override_coal_msl | `0.7` | Same as S1 |
| coal_ramp_rate_multiplier | `1.5` | Same as S1 |
| fixed_fuel_prices | `BASE_PMR1b` | Same as S1 |
| fixed_emissions | `FS_2045` | Same as S1 |
| fixed_renewables | `BASE` | Same as S1 |
| fixed_storage | `BASE` | Same as S1 |
| extendable_active | `NONE` | New column created in Step 3; use `BASE` fallback if Step 3 causes errors |
| extendable_parameters | `BASE_PMR1b` | Same as S1 |
| global_discount_rate | `0.092` | Same as S1 |
| extendable_fuel_prices | `BASE_PMR1b` | Same as S1 |
| extendable_emissions | `FS_2045` | Same as S1 |
| extendable_max_total | `MOD_CNST` | Same as S1 |
| extendable_min_total | `MTSAO_BQ` | Same as S1 |
| extendable_max_annual | `MOD_CNST` | Same as S1 |
| extendable_min_annual | `UNC` | Same as S1 |
| aux_stg_feed | `DIESEL_LNG` | Same as S1 |
| operational_limits | `NO_MIN_GAS` | Same as S1 |
| operational_reserves | `BASE` | Same as S1 |
| outage_profiles | `BASE` | Same as S1 |
| annual_availability | `EAF_48` | 48% coal EAF — verified correct for 2023 |
| carbon_constraints | `none` | No CO2 cap |
| carbon_tax | `BASE_PMR1b` | Same as S1 |
| load_trajectory | `2023_ACTUAL` | New row added in Step 4 — 225.87 TWh |
| reserve_margin | `RES_MRGN_10` | Same as S1 |
| capacity_credits | `BASE3` | Same as S1 |

---

### Step 6 — Modify config.yaml

Back up first:
```bash
cp config.yaml config.yaml.s1_backup
```

Make exactly these three changes:

```yaml
scenarios:
  working_folder: Benchmark_2023    # was: Coal_Flexibilisation

years:
  build_start_year: 2023            # was: 2025
  reference_load_year: 2023         # was: 2017
```

All other `config.yaml` settings remain unchanged.

---

### Step 7 — Run the pipeline

```bash
cd /Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-rsa
conda activate pypsa-rsa-repro

# Dry run first
GRB_LICENSE_FILE=/Users/nylan/gurobi.lic \
  snakemake --cores 2 --dryrun \
  "results/Benchmark_2023/S_2023BM/networks/solved.nc"

# If dry run passes, run unattended
GRB_LICENSE_FILE=/Users/nylan/gurobi.lic \
  snakemake --cores 2 \
  "results/Benchmark_2023/S_2023BM/networks/solved.nc"
```

Snakemake will execute rules in order:

1. `build_topology` → `resources/Benchmark_2023/S_2023BM/buses.geojson`
2. `base_network` → `networks/Benchmark_2023/S_2023BM/base-network.nc`
3. `add_electricity` → `networks/Benchmark_2023/S_2023BM/elec.nc`
4. `prepare_and_solve_network` → `results/Benchmark_2023/S_2023BM/networks/solved.nc`

---

## Acceptance Gates

After the run completes, execute the following and paste the output into your response:

```python
import pypsa

n = pypsa.Network("results/Benchmark_2023/S_2023BM/networks/solved.nc")

print("Snapshots:", n.snapshots[0], "→", n.snapshots[-1])
print("Total demand (TWh):", n.loads_t.p_set.sum().sum() / 1e6)
print("\nInstalled capacity by carrier (MW):")
print(n.generators.groupby("carrier")["p_nom"].sum().sort_values(ascending=False))
print("\nTotal generation by carrier (TWh):")
print((n.generators_t.p.sum() / 1e6).sort_values(ascending=False))
print("\nLoad shedding (TWh):", n.generators_t.p.filter(like="shedding").sum().sum() / 1e6)
```

**Pass criteria:**

| Check | Expected | Action if wrong |
|---|---|---|
| Snapshots | 2023-01-01 → 2023-12-31 | Fail — check `simulation_years` |
| Total demand | ≈ 225.87 TWh (±0.1 TWh) | Fail — check Step 1 and Step 4 |
| Load shedding | 10–20 TWh | Warn but pass; Eskom actual MLR = 16.56 TWh |
| `solved.nc` file size | > 1 MB | Fail — solve did not complete |

---

## Troubleshooting

| Error | Diagnosis | Fix |
|---|---|---|
| Gurobi license error | `GRB_LICENSE_FILE` not set in shell | Set `export GRB_LICENSE_FILE=/Users/nylan/gurobi.lic` before Snakemake |
| `add_electricity` fails on `reference_load_year: 2023` | 2023 rows not appended correctly to `SystemEnergy2009_22.csv` | Check datetime format matches existing rows exactly (`YYYY-MM-DD HH:MM:SS`) |
| `KeyError` in `get_carriers_from_model_file` | NONE column causes empty DataFrame iteration failure | Switch `extendable_active` to `BASE` in `scenarios_to_run.xlsx` and re-run |
| Snakemake cannot find `scenarios_to_run.xlsx` | `working_folder` mismatch | Confirm `config.yaml` has `working_folder: Benchmark_2023` (case-sensitive) |
| Dry run fails on missing bundle files | Missing shapefiles in `data/bundle/` | Report the specific missing file — do not guess paths |

---

## Files Created or Modified

| File | Action |
|---|---|
| `data/bundle/SystemEnergy2009_22.csv` | Modified — 2023 hourly rows appended |
| `config.yaml` | Modified — `working_folder`, `reference_load_year`, `build_start_year` |
| `config.yaml.s1_backup` | Created — backup of original |
| `scenarios/Benchmark_2023/scenarios_to_run.xlsx` | Created |
| `scenarios/Benchmark_2023/sub_scenarios/` | Created — copied from `Coal_Flexibilisation/sub_scenarios/` |
| `scenarios/Benchmark_2023/sub_scenarios/extendable_technologies.xlsx` | Modified — `NONE` column added |
| `scenarios/Benchmark_2023/sub_scenarios/annual_load.xlsx` | Modified — `2023_ACTUAL` row added |
| `networks/Benchmark_2023/S_2023BM/` | Created by Snakemake |
| `results/Benchmark_2023/S_2023BM/` | Created by Snakemake |

---

## Hard Constraints

- Do **not** modify anything under `scenarios/Coal_Flexibilisation/`
- Do **not** change any `config.yaml` fields other than the three specified in Step 6
- Do **not** use load trajectories `IRP23`, `IRP24_LOW`, or any other existing row — only `2023_ACTUAL`
- Do **not** use `EAF_55` — data bug: value is `0.0055` not `0.55`
- Do **not** modify `fixed_technologies.xlsx`
