# Module 13g — Coal Disaggregation: 15-Plant Injection into PyPSA-Earth

**Target agent:** Claude Opus or Codex (standalone — no prior conversation context)
**Working directory (Earth):** `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth`
**Working directory (RSA inputs):** `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-rsa`
**Conda environment:** `pypsa-earth`
**Solver:** Gurobi (required for re-solve)
**Prerequisites:** The prepared NoCO2 network for the target experiment mode must exist. For the accepted calibration path, Module 13f should be enabled and the comparable Module 12/13 scenario set should be fresh. For module-isolation testing, 13g must also run with Module 13f disabled so the impact of coal disaggregation can be measured independently. Current accepted pre-13g comparator from 2026-05-15: all four solved networks preserve 225.874862 TWh demand and use the same 82-line grid basis.

---

## Purpose

Replace PyPSA-Earth's aggregated `coal` carrier with 15 named Eskom coal stations. Each plant receives its own `p_nom`, `marginal_cost`, and time-varying `p_max_pu(t)`, built from the same RSA input files as the `S_2023BM` benchmark. **No unit commitment in this module** — UC is added in Module 13h.

Disaggregation alone addresses two of three structural gaps identified in Module 13e:
- Seasonal EAF variation (flat 0.48 → weekly outage profile normalized to 0.48)
- Plant-level merit order (single aggregated cost → 15 distinct marginal costs)

Expected: coal Pearson r should improve over the refreshed pre-13g EAF/OPC/CAP comparator and reach roughly ≥ 0.40. Module 13h (MSL + ramp limits + UC) carries the bulk of the shape correction toward RSA's 0.585; 13g alone cannot flatten the diurnal cycle because the cycle-flattening mechanism is MSL/ramps, not EAF. The r gate is deliberately modest: RSA's flat coal profile is owned by p_min_pu ≈ 0.7 and ramp limits, not by per-plant EAF or merit order. See "Why the 13g r gate is modest" below.

Module reads **same input files as RSA** — does not extract from RSA's solved network.

## Current Pre-13g Comparator Lock (2026-05-15)

Use these numbers as the baseline for judging 13g. They supersede older notebook/export values until `notebooks/za_validation/12_dispatch_calibration/dispatch_calibration_validation.ipynb` is rerun.

| Solve | Load TWh | Lines | Coal TWh | OCGT TWh | Load shedding TWh |
|---|---:|---:|---:|---:|---:|
| NoCO2 | 225.874862 | 82 | 195.851932 | 8.423951 | 0.000168 |
| EAF | 225.874862 | 82 | 185.271174 | 19.207360 | 0.058029 |
| EAF-OPC | 225.874862 | 82 | 185.905520 | 14.775223 | 3.518144 |
| EAF-OPC-CAP | 225.874862 | 82 | 186.347087 | 5.500000 | 12.315640 |

Operational interpretation:
- The refreshed EAF layer now moves coal in the expected direction: NoCO2 coal 195.852 TWh → EAF coal 185.271 TWh.
- The CAP layer now behaves coherently: OCGT is exactly 5.500 TWh and load shedding rises to 12.316 TWh.
- OPC/CAP remain useful downstream comparators, but 13g should first be accepted on the EAF layer before treating CAP as a final validation candidate.
- Do **not** cite stale `data/za_validation` CSV/HTML exports until the notebook/export path is rerun after 13g/13h.

---

## Independent Module Toggle Requirement

Module 13g must be independently switchable from Module 13f and from Module 13h UC. The implementation must support the modes below without code edits between runs:

| Mode | `za.isolated_load_transfer.enable` | `za_coal_disaggregation.enable` | `za_coal_disaggregation.uc.enable` | What it measures |
|---|---:|---:|---:|---|
| Baseline / Module 12 | `false` | `false` | `false` | Original demand-drop plus aggregated coal EAF overlay |
| 13f-only | `true` | `false` | `false` | Demand alignment impact only |
| 13g-only, no UC | `false` | `true` | `false` | Coal disaggregation impact only, on the lower-demand baseline |
| 13f + 13g, no UC | `true` | `true` | `false` | Combined demand + disaggregation candidate before UC |
| 13g + UC diagnostic | `false` | `true` | `true` | UC impact on the lower-demand baseline |
| 13f + 13g + UC | `true` | `true` | `true` | Full Module 13h candidate |

Design implications:
- `za_coal_disaggregation.enable` must only control the coal replacement at the `apply_za_coal_eaf` DAG slot.
- `za_coal_disaggregation.uc.enable` must only control UC attributes and LP-UC solver behavior. It must not be implicitly enabled by 13g.
- It must not assume `za.isolated_load_transfer.enable: true`.
- A 13g-only run is allowed to retain the lower pre-13f load; do not fail it on the ≥ 225.70 TWh demand gate.
- Demand-preservation gates apply only to modes where `za.isolated_load_transfer.enable: true`.
- UC gates apply only to modes where `za_coal_disaggregation.uc.enable: true`.
- The final notebook comparison should report all produced modes, so the marginal effects of 13f, 13g, 13h/UC, and their interactions are visible.

Recommended temporary config edits for isolated experiments:

```yaml
za:
  isolated_load_transfer:
    enable: false   # true only for 13f-enabled modes

za_coal_disaggregation:
  enable: true      # true for 13g-enabled modes
  uc:
    enable: false   # true only for 13h/UC-enabled modes
```

If all toggles are absent or false, the run must fall back to the Module 12 behavior. If `za_coal_disaggregation.uc.enable: true` while `za_coal_disaggregation.enable: false`, the implementation should fail fast with a clear config error; UC is only defined for the 15 disaggregated coal plants.

---

## EAF Overlap Design Decision

### Why the previous 13g plan had a structural problem

Earlier 13g draft injected 15 plants inside `add_electricity` (pre-cluster), then protected them via `exclude_carriers: [coal]` through `simplify_network` and `cluster_network`. Two problems with that path:

1. **Bus-name mismatch.** Step 3 assigned plants to nearest of the 34 cluster buses by KDTree, but the assignment file lists POST-cluster bus names. `add_electricity` emits `elec.nc` whose bus topology is built from `custom_busmap` and the OSM/PyPSA-Earth base; cluster bus names only stabilize after `simplify_network → cluster_network`. Attaching plants to bus IDs that do not yet exist breaks the network.
2. **EAF overlap (the stated problem).** `apply_za_coal_eaf` is a separate Snakemake rule that runs **after** `prepare_network` (input `elec_s_34_ec_lc1_NoCO2-1H.nc`, output `…-EAF.nc`). It iterates all `carrier == "coal"` generators and overwrites `generators_t.p_max_pu` with bus-level capacity-weighted profile from `custom_powerplants.csv`. If 15 per-plant generators are present, their per-plant p_max_pu gets squashed to whatever bus-level average exists — discarding the disaggregation.

### Chosen option — A (modified): swap the script at the EAF DAG slot

`apply_za_coal_eaf` rule is the natural injection point. It already:
- runs after clustering (bus names stable)
- writes `…-EAF.nc` (Module 12 filename convention preserved)
- has the audit-CSV contract downstream rules depend on
- isolates the mutation to `generators_t.p_max_pu` for coal only

Module 13g replaces the **script bound to that rule** when `za_coal_disaggregation.enable: true`. The new script:
1. Loads the prepared network (input network unchanged from current Module 12 rule).
2. Removes the existing aggregated coal generators.
3. Adds 15 named coal generators with per-plant `p_nom`, `marginal_cost`, bus assignment (post-cluster bus names, stable).
4. Writes per-plant `generators_t.p_max_pu` from `za_coal_eaf_hourly_2023.csv`.
5. Writes the same `data/za_audit/za_coal_eaf_audit.csv` schema so downstream rules see no change in their input contract.
6. Exports `…-EAF.nc` with the same filename.

When toggle off, the existing `apply_coal_eaf.py` runs unchanged (Module 12 accepted behavior).

### Why not Options B or C

- **Option B** (extend `apply_coal_eaf.py` to handle per-plant generators): conflates the bus-weighting code path with the plant-injection code path inside one script. Higher diff surface; harder to revert per-plant if it misbehaves. Rejected.
- **Option C** (new rule between `apply_za_coal_eaf` and `simplify_network`): the EAF rule runs **after** clustering, not before. The phrasing of the original problem statement was inverted on the DAG. A new rule after `apply_za_coal_eaf` could work, but it would have to undo the bus-weighted EAF that the previous rule just wrote — two writes of `p_max_pu`, second supersedes first. Wasteful, opaque ordering, more files. Rejected.

### Design summary

| Aspect | Decision |
|---|---|
| DAG slot | Same `apply_za_coal_eaf` rule slot — script chosen by config toggle |
| Output filename | `elec_s_34_ec_lc1_NoCO2-1H-EAF.nc` (unchanged) |
| Audit CSV | `data/za_audit/za_coal_eaf_audit.csv` (same path, schema additive) |
| Module 12 backward compatibility | If `za_coal_disaggregation.enable: false` or key absent → original `apply_coal_eaf.py` runs (no change) |
| Snakemake DAG change | None required — same rule, same I/O |
| `exclude_carriers` | NOT NEEDED — 13g operates post-cluster; cluster step never sees 15 plants |

---

## Config Toggle Spec

Add to `configs/za/za_2023_fixed_validation.yaml` (a new top-level block):

```yaml
# Module 13g — Per-plant coal disaggregation.
# When enable: true, the apply_za_coal_eaf rule executes
# scripts/za_fleet/build_za_coal_plants_network.py instead of
# scripts/za_fleet/apply_coal_eaf.py. It replaces the aggregated coal
# carrier with 15 named Eskom coal stations (p_nom, marginal_cost,
# hourly p_max_pu). Backward compatibility: if this block is absent or
# enable: false, the original apply_coal_eaf overlay runs unchanged.
za_coal_disaggregation:
  enable: true
  plants_csv:        data/za_validation/za_coal_plants_2023.csv
  eaf_hourly_csv:    data/za_validation/za_coal_eaf_hourly_2023.csv
  bus_assignment_csv: data/za_validation/za_coal_bus_assignment.csv
  # Source workbook for the plant_availability.xlsx referenced when
  # rebuilding eaf_hourly_csv. Default = Benchmark_2023 path.
  rsa_scenarios_root: "{pypsa_rsa_root}/scenarios/Benchmark_2023/sub_scenarios"
```

### Propagation

**Snakefile** — wrap the `apply_za_coal_eaf` rule so the bound script is config-driven:

```python
_za_coal_disagg = config.get("za_coal_disaggregation", {}).get("enable", False)

rule apply_za_coal_eaf:
    input:
        network_in = "networks/" + RDIR + "elec_s_34_ec_lc1_NoCO2-1H.nc",
        workbook   = config["pypsa_rsa_root"]
                     + "/scenarios/Coal_Flexibilisation/sub_scenarios/plant_availability.xlsx",
        custom_pp  = "data/custom_powerplants.csv",
        # Module 13g extras — empty list when toggle off; Snakemake ignores.
        plants_csv = (config.get("za_coal_disaggregation", {}).get(
                        "plants_csv", "data/za_validation/za_coal_plants_2023.csv")
                      if _za_coal_disagg else []),
        eaf_csv    = (config.get("za_coal_disaggregation", {}).get(
                        "eaf_hourly_csv", "data/za_validation/za_coal_eaf_hourly_2023.csv")
                      if _za_coal_disagg else []),
        buses_csv  = (config.get("za_coal_disaggregation", {}).get(
                        "bus_assignment_csv", "data/za_validation/za_coal_bus_assignment.csv")
                      if _za_coal_disagg else []),
    output:
        network_out = "networks/" + RDIR + "elec_s_34_ec_lc1_NoCO2-1H-EAF.nc",
        backup      = "networks/" + RDIR + "elec_s_34_ec_lc1_NoCO2-1H.pre_eaf.nc",
        audit       = "data/za_audit/za_coal_eaf_audit.csv",
    log:
        "logs/" + RDIR + "apply_za_coal_eaf.log",
    threads: 1
    resources:
        mem_mb = 4000,
    script:
        ("scripts/za_fleet/build_za_coal_plants_network.py"
         if _za_coal_disagg
         else "scripts/za_fleet/apply_coal_eaf.py")
```

Rule keeps its name → downstream `solve_network_eaf`, `solve_network_eaf_opc`, `solve_network_eaf_opc_cap`, and `ruleorder: apply_za_coal_eaf > prepare_network` lines need no edits.

**Python (`build_za_coal_plants_network.py`)** reads inputs via `snakemake.input.*` only; toggle decision is owned by Snakefile. No `config.get` check inside the script. Keeps the script callable from CLI with the same arg names.

**Backward compatibility check.** If `za_coal_disaggregation` key is missing → `_za_coal_disagg = False` → original script bound → no extra inputs required → Module 12 accepted state.

**Independence check.** The 13g toggle must not read or branch on `za.isolated_load_transfer.enable`. It should work against whichever prepared NoCO2 network the upstream simplify/cluster path produced. This allows 13g-only and 13f+13g comparisons from the same code path. It must also leave `committable=False` and no `generators_t.p_min_pu` UC overlay when `za_coal_disaggregation.uc.enable: false`; that is the no-UC control required before Module 13h.

---

## Architectural Corrections vs Previous 13g Draft

| # | Previous draft | Corrected |
|---|---|---|
| 1 | Plants injected inside `add_electricity` (pre-cluster) | Plants injected inside the `apply_za_coal_eaf` slot (post-cluster). Bus names are stable. |
| 2 | `exclude_carriers: [coal]` added to simplify+cluster blocks | NOT needed. Disaggregation runs after clustering. Removed from spec. |
| 3 | New Snakemake hook on `rule add_electricity` with 3 conditional inputs | NOT needed. Rule `apply_za_coal_eaf` already exists. Reuse it. |
| 4 | Source workbook path `Benchmark_2023/sub_scenarios/plant_availability.xlsx` | The existing `apply_coal_eaf.py` reads from `Coal_Flexibilisation/sub_scenarios/plant_availability.xlsx`. Module 13g's CSV-building step still reads `Benchmark_2023` (per source-of-truth lock for S_2023BM); the runtime Snakemake input continues to point at `Coal_Flexibilisation` for shape compatibility with the audit contract. Verify the two workbooks have identical `BASE` planned+unplanned rows before commit — if they differ, document which is canonical for 2023. |
| 5 | EAF normalized to 0.48 in 13g vs raw `1−planned−unplanned` in `apply_coal_eaf.py` | Real semantic difference; intentional. 13g enforces EAF_48 annual cap (matches RSA's `EAF_48 + BASE` scenario contract). Documented in Step 1. |
| 6 | Bus assignment loaded from solved `elec_s_34_…EAF-OPC-CAP.nc` | Load from the PRE-solve clustered network `elec_s_34.nc` (or `elec_s_34_ec_lc1_NoCO2-1H.nc`). Bus geometry is identical post-cluster regardless of solve. |

---

## Context

### Why RSA coal beats Earth (Module 13e)

Three structural reasons, addressed in two stages:

| Feature | Current Earth | After 13g | After 13h |
|---|---|---|---|
| Temporal EAF variation | Flat 0.48 | Weekly profile, normalized to 0.48 | Same as 13g |
| Plant-level merit order | Single aggregated coal | 15 plants, individual marginal costs | Same as 13g |
| Linearised UC (MSL + ramp) | None | None | committable=True, p_min_pu=0.7 |

### Why the 13g r gate is modest

July 2023 hourly dispatch panel (notebook `12_dispatch_calibration`) shows:

| Variant | MAE (MW) | Bias (MW) | Shape vs Eskom |
|---|---|---|---|
| STOCK | 2 999 | +2 298 | peaky, daily cycle |
| NoCO2 | 2 972 | +2 860 | peaky |
| EAF | 2 175 | +1 773 | peaky |
| EAF-OPC | 2 272 | +1 807 | peaky |
| EAF-OPC-CAP | 2 336 | +1 914 | peaky |
| **RSA-BM** | **2 235** | **+2 202** | **flat, ~baseload** |
| Eskom | — | — | flat, ~baseload |

Diagnostics:
- Earth's MAE is already competitive (EAF beats RSA-BM on MAE). Magnitude is not the 13g problem.
- All variants share a +1.8 to +2.3 GW positive bias including RSA-BM — structural over-dispatch of coal vs Eskom (likely OCGT/gas under-dispatch). 13g does not fix this and should not be measured against it.
- RSA's r ≈ 0.585 comes from **shape flatness**, which is generated by `p_min_pu ≈ 0.7` (MSL) + ramp limits + UC commitment cycle. Per-plant EAF and merit order do NOT flatten the diurnal cycle.
- 13g installs data (15 plants, per-plant cost, weekly-seasonal EAF) but not the dispatch mechanisms (MSL, ramps, UC) that produce flat coal. The lift from 0.332 is therefore primarily seasonal (Jan vs Jul weekly cap variation), not diurnal.

Realistic 13g r outcome: pre-13g EAF/OPC/CAP r should improve to roughly ~0.38–0.43. Gate set at ≥ 0.40 to confirm seasonal mechanism is wired correctly without setting an unreachable bar. The remaining ~0.40 → 0.585 lift is owned by Module 13h.

Load-bearing 13g gates remain: 15 generators present, ≥ 225.70 TWh load, coal Δ ≤ +8% vs Eskom, per-plant `generators_t.p_max_pu` non-flat across plants, audit `disaggregation_active = True`.

### Input data sources (RSA — read only, do not modify)

All source data:
```
/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-rsa/scenarios/Benchmark_2023/sub_scenarios/
```

| File | Sheet | Used for |
|---|---|---|
| `fixed_technologies.xlsx` | `conventional` | Plant specs (scenario `VAR_HR`): capacity, GPS, heat rates, ramp limits, MSL, fuel-price group |
| `plant_availability.xlsx` | `annual_availability` | Annual EAF per plant (scenario `EAF_48`): all Eskom coal = 0.48 for 2023 |
| `plant_availability.xlsx` | `outage_profiles` | Weekly outage fractions (scenario `BASE`, types `planned` + `unplanned`) |
| `fuel_prices.xlsx` | `fixed_generators` | Fuel price per group R/GJ (scenario `BASE_PMR1b`, year 2025 — 2023 column is NaN) |

UC config parameters (`override_coal_msl: 0.7`, `coal_ramp_rate_multiplier: 1.5`) are **recorded in the CSV but not wired into PyPSA in this module** — used in Module 13h.

### Verified plant list (VAR_HR scenario, Eskom coal only)

15 stations from `fixed_technologies.xlsx`, sheet `conventional`, scenario `VAR_HR`, carrier `coal`:

| Station | Capacity (MW) | Fuel group | Heat rate (GJ/MWh) | Lat | Lon |
|---|---|---|---|---|---|
| Arnot | 2100 | med_group | 13.54 | −25.944 | 29.792 |
| Camden | 1481 | high_group | 14.38 | −26.620 | 30.091 |
| Duvha | 2875 | low_group | 11.67 | −25.960 | 29.341 |
| Grootvlei | 570 | high_group | 15.00 | −26.770 | 28.500 |
| Hendrina | 1098 | med_group | 14.38 | −26.031 | 29.601 |
| Kelvin | 160 | high_group | 14.32 | −26.116 | 28.114 |
| Kendal | 3840 | med_group | 12.29 | −26.088 | 28.969 |
| Kriel | 2640 | high_group | 12.81 | −26.254 | 29.180 |
| Kusile | 4320 | high_group | 10.42 | −25.920 | 28.925 |
| Lethabo | 3558 | low_group | 11.25 | −26.740 | 27.975 |
| Majuba | 3807 | med_group | 13.02 | −27.096 | 29.771 |
| Matimba | 3690 | low_group | 10.31 | −23.668 | 27.613 |
| Matla | 3450 | high_group | 12.40 | −26.280 | 29.142 |
| Medupi | 4320 | low_group | 9.58 | −23.420 | 27.330 |
| Tutuka | 3510 | high_group | 12.81 | −26.776 | 29.352 |

**Fuel prices (BASE_PMR1b, R/GJ, 2025 proxy):**
- `low_group`: 27.93 R/GJ → cheapest (Medupi, Matimba, Duvha, Lethabo)
- `med_group`: 40.01 R/GJ → second (Arnot, Hendrina, Kendal, Majuba)
- `high_group`: 48.31 R/GJ → last (Camden, Grootvlei, Kelvin, Kriel, Kusile, Matla, Tutuka)

**Marginal cost formula (R/MWh, then convert to EUR/MWh):**
```
marginal_cost_R = heat_rate × fuel_price_R_per_GJ + variable_om_R_per_MWh
marginal_cost_EUR = marginal_cost_R / 20.0   # 1 EUR ≈ 20 ZAR, 2023 average
```

### How RSA builds hourly p_max_pu(t)

In EAF_48 + BASE, all 15 Eskom coal plants share the same annual EAF (0.48) and the same weekly outage profile. Temporal variation in `p_max_pu` comes entirely from the outage profile, not from plant-specific differences.

Algorithm:
1. Read `outage_profiles`, scenario `BASE`, types `planned` and `unplanned`. Keep only rows where `week` is a numeric integer (1–52); discard rows where `week` = `"average"`, `"std_dev_noise"`, etc.
2. For each week w: `avail_wk[w] = 1 − planned[w] − unplanned[w]` (use any plant column — all identical in BASE+EAF_48).
3. Normalize: `scale = 0.48 / mean(avail_wk)` → `avail_wk_scaled[w] = clip(avail_wk[w] × scale, 0, 1)`.
4. Expand to 8760 hours: for each hourly timestamp in 2023, look up ISO week number (1–52); use `avail_wk_scaled[min(iso_week, 52)]`.
5. Result: Jan mean ≈ 0.402, Jul mean ≈ 0.530, annual mean = 0.480.

Difference vs `apply_coal_eaf.py`: that script does NOT normalize to 0.48 — it uses raw `1 − planned − unplanned` and clips to `[0, 1]`. 13g normalization to EAF_48 is intentional (matches RSA's `EAF_48` scenario annual-cap contract).

---

## Implementation Steps

### Step 1 — Create the preprocessing script

Create `scripts/build_za_coal_plants.py` in the Earth repo. Run once; outputs are stable data files committed to `data/za_validation/`.

#### Outputs

**`data/za_validation/za_coal_plants_2023.csv`** — one row per plant, all columns including UC params (used in Module 13h):

```
station_name, carrier, p_nom_mw, gps_lat, gps_lon, fuel_group,
avg_heat_rate_gj_per_mwh, fuel_price_r_per_gj,
variable_om_r_per_mwh, marginal_cost_r_per_mwh, marginal_cost_eur_per_mwh,
p_min_pu, ramp_limit_up_per_h, ramp_limit_down_per_h,
min_up_time_h, min_down_time_h, start_up_cost_eur
```

Notes:
- `carrier` = `coal` for all rows
- `p_min_pu` = 0.7 (from `override_coal_msl = 0.7`) — stored but not used until 13h
- `ramp_limit_up_per_h` = `max_ramp_up (%/h)` × 1.5 / 100 — stored but not used until 13h
- `ramp_limit_down_per_h` = `max_ramp_down (%/h)` × 1.5 / 100 — stored but not used until 13h
- `start_up_cost_eur` = `start_up_cost (R)` / 20.0 — stored but not used until 13h

**`data/za_validation/za_coal_eaf_hourly_2023.csv`** — 8760 rows × 15 columns (one per plant name):
- Index: `datetime` (hourly, `2023-01-01 00:00` to `2023-12-31 23:00`)
- Values: `p_max_pu` float, same for all 15 columns (uniform EAF_48 + BASE profile)

#### Parsing `outage_profiles` (messy sheet)

Filter to numeric weeks only:

```python
op = pd.read_excel(pa, sheet_name='outage_profiles', header=0)
op.columns = op.iloc[0]      # row 0 is real header
op = op.iloc[1:].reset_index(drop=True)
op.columns.name = None

# Keep numeric weeks 1–52 only
op = op[pd.to_numeric(op['week'], errors='coerce').notna()].copy()
op['week'] = pd.to_numeric(op['week']).astype(int)
op = op[op['week'] <= 52]

base_plan = op[(op['scenario'] == 'BASE') & (op['type'] == 'planned')].set_index('week')
base_unplan = op[(op['scenario'] == 'BASE') & (op['type'] == 'unplanned')].set_index('week')
```

Use `Arnot` column (or any single plant column) for the weekly availability series — all plants identical in BASE+EAF_48.

#### Script CLI

```bash
python scripts/build_za_coal_plants.py \
  --rsa-scenarios /Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-rsa/scenarios/Benchmark_2023/sub_scenarios
```

---

### Step 2 — Run the preprocessing script and verify outputs

```bash
cd /Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth

conda run -n pypsa-earth python scripts/build_za_coal_plants.py \
  --rsa-scenarios /Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-rsa/scenarios/Benchmark_2023/sub_scenarios
```

Verify:
```python
import pandas as pd

plants = pd.read_csv("data/za_validation/za_coal_plants_2023.csv")
eaf = pd.read_csv("data/za_validation/za_coal_eaf_hourly_2023.csv",
                  index_col=0, parse_dates=True)

print(f"Plant count: {len(plants)}  (expected 15)")
print(f"EAF shape: {eaf.shape}  (expected (8760, 15))")
print(f"Annual mean EAF: {eaf.mean().mean():.4f}  (expected 0.480)")
print(f"Jan mean EAF: {eaf.loc['2023-01'].mean().mean():.4f}  (expected ~0.402)")
print(f"Jul mean EAF: {eaf.loc['2023-07'].mean().mean():.4f}  (expected ~0.530)")
print(f"Total p_nom: {plants['p_nom_mw'].sum():.0f} MW  (expected ~43419 MW)")
print("\nMarginal costs EUR/MWh (should increase: low < med < high group):")
print(plants[['station_name','fuel_group','marginal_cost_eur_per_mwh']]
      .sort_values('marginal_cost_eur_per_mwh').to_string())
```

**Pass criteria:**

| Check | Expected |
|---|---|
| Plant count | 15 |
| Annual mean EAF | 0.478–0.482 |
| Jan mean EAF | 0.390–0.415 |
| Jul mean EAF | 0.510–0.545 |
| Total p_nom | ~43 419 MW |
| Cheapest marginal cost | Medupi or Matimba (low_group, lowest heat rate) |
| Most expensive | Grootvlei (high_group, 15.00 GJ/MWh) |

---

### Step 3 — Compute bus assignment (post-cluster bus names)

Each plant attaches to the geographically nearest of the 34 cluster buses. Load the **pre-solve clustered** network so bus names are stable but no solve has run yet.

```python
import pypsa
import pandas as pd
from scipy.spatial import KDTree

# Use the pre-EAF clustered+prepared network — bus geometry matches what
# build_za_coal_plants_network.py will load at runtime.
n = pypsa.Network(
    "networks/za_2023_fixed_validation/elec_s_34_ec_lc1_NoCO2-1H.nc"
)
plants = pd.read_csv("data/za_validation/za_coal_plants_2023.csv")

# Bus coordinates (y=lat, x=lon)
bus_coords = n.buses[["y", "x"]].dropna()
tree = KDTree(bus_coords.values)

assignments = []
for _, row in plants.iterrows():
    _, idx = tree.query([row["gps_lat"], row["gps_lon"]])
    assignments.append({
        "station_name": row["station_name"],
        "bus": bus_coords.index[idx]
    })

df = pd.DataFrame(assignments)
df.to_csv("data/za_validation/za_coal_bus_assignment.csv", index=False)
print(df.to_string())
```

**Sanity check:** Matimba and Medupi (Limpopo, ~−23.4° lat) → northern cluster buses. Lethabo (Free State, ~−26.7° lat) and Kendal/Duvha/Kriel (Mpumalanga, ~−25.9 to −26.3° lat) → eastern/central buses.

Write `za_coal_bus_assignment.csv` as a static committed file — does not change unless clustering changes.

**Preflight from the 2026-05-15 refresh.** If any upstream fleet rule is forced, `data/custom_powerplants.csv` can be regenerated with blank `bus` values. The old Module 12 `apply_coal_eaf.py` then fails with `No bus-level weekly availability profiles could be built`. Before running 13g or any fallback EAF path, verify:

```bash
conda run -n pypsa-earth python -c "
import pandas as pd
pp = pd.read_csv('data/custom_powerplants.csv')
coal = pp[pp['Fueltype'].eq('Hard Coal')]
print('coal rows', len(coal), 'blank bus', int(coal['bus'].isna().sum()))
assert coal['bus'].notna().all(), 'Run build_za_grid_spatial to backfill plant bus assignments'
"
```

If this fails, run:

```bash
conda run -n pypsa-earth snakemake \
  --configfile configs/za/za_2023_fixed_validation.yaml \
  --cores 1 --ignore-incomplete \
  --allowed-rules build_za_grid_spatial \
  --forcerun build_za_grid_spatial \
  data/custom_busmap_elec_s_34.csv
```

13g's own plant-to-bus mapping is `data/za_validation/za_coal_bus_assignment.csv`, but keeping `custom_powerplants.csv` bus assignments valid protects the fallback path and prevents confusing pre-13g failures.

---

### Step 4 — Create `scripts/za_fleet/build_za_coal_plants_network.py`

This script is the toggle-on replacement for `apply_coal_eaf.py`. Same I/O contract: reads a network file, writes a network file plus audit CSV plus backup.

```python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Module 13g — Replace aggregated coal carrier with 15 named Eskom stations.

Drop-in replacement for scripts/za_fleet/apply_coal_eaf.py when
za_coal_disaggregation.enable: true. Same input/output filename contract.
Mutation surface: coal generator rows + generators_t.p_max_pu for those
generators only. No UC fields set here (Module 13h).
"""

import logging, shutil, sys
from pathlib import Path
import pandas as pd
import pypsa

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("build_za_coal_plants_network")


def attach_za_coal_plants(n, plants_csv, eaf_csv, bus_assignment_csv):
    plants = pd.read_csv(plants_csv)
    eaf = pd.read_csv(eaf_csv, index_col=0, parse_dates=True)
    bus_assign = pd.read_csv(bus_assignment_csv).set_index("station_name")["bus"]

    eaf = eaf.reindex(n.snapshots)
    if eaf.isna().any().any():
        raise SystemExit(
            f"za_coal_eaf_hourly_2023.csv does not cover all snapshots. "
            f"First missing: {eaf.index[eaf.isna().any(axis=1)][0]}"
        )

    existing_coal = n.generators[n.generators.carrier == "coal"].index
    if len(existing_coal) == 0:
        raise SystemExit("No coal generators found in input network — refusing to proceed")
    logger.info("Removing %d aggregated coal generators", len(existing_coal))
    n.mremove("Generator", existing_coal)

    missing_bus = []
    for _, row in plants.iterrows():
        name = row["station_name"]
        bus = bus_assign.loc[name]
        if bus not in n.buses.index:
            missing_bus.append((name, bus))
            continue
        n.add(
            "Generator",
            name,
            bus=bus,
            carrier="coal",
            p_nom=row["p_nom_mw"],
            marginal_cost=row["marginal_cost_eur_per_mwh"],
            efficiency=3.6 / row["avg_heat_rate_gj_per_mwh"],
            committable=False,   # UC in Module 13h
        )
    if missing_bus:
        raise SystemExit(f"Bus IDs missing from network: {missing_bus}")

    # Ensure p_max_pu DataFrame exists
    if n.generators_t.p_max_pu.empty:
        n.generators_t.p_max_pu = pd.DataFrame(index=n.snapshots)
    else:
        n.generators_t.p_max_pu = n.generators_t.p_max_pu.reindex(index=n.snapshots)

    # Apply per-plant hourly p_max_pu AFTER n.add() (static at add → series here)
    for _, row in plants.iterrows():
        name = row["station_name"]
        n.generators_t.p_max_pu.loc[:, name] = eaf[name].astype(float).clip(0.0, 1.0).values

    return plants, eaf


def write_audit(audit_out: Path, plants: pd.DataFrame, eaf: pd.DataFrame, source_workbook: str) -> None:
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for _, p in plants.iterrows():
        rows.append({
            "record_type": "generator",
            "gen_name": p["station_name"],
            "bus": "",                       # filled by caller if needed
            "station_key": p["station_name"],
            "fallback_used": False,
            "mean_p_max_pu": float(eaf[p["station_name"]].mean()),
        })
    df = pd.DataFrame(rows)
    df["source_workbook"] = source_workbook
    df["sheet"] = "outage_profiles+annual_availability"
    df["scenario"] = "BASE+EAF_48"
    df["outage_types"] = "planned+unplanned"
    df["station_to_bus_mapping_rule"] = "kdtree_nearest_cluster_bus_geocoord"
    df["any_fallback_used"] = False
    df["unmatched_mw"] = 0.0
    df["coal_generators_overlaid"] = int(len(plants))
    df["n_snapshots"] = int(len(eaf))
    df["mean_fleet_availability"] = float(eaf.mean().mean())
    df["non_coal_p_max_pu_changed"] = False
    df["disaggregation_active"] = True
    df.to_csv(audit_out, index=False)
    logger.info("Wrote 13g audit (%d rows) to %s", len(df), audit_out)


def main(network_in, network_out, plants_csv, eaf_csv, buses_csv, audit_out, backup):
    if backup is not None:
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(network_in, backup)
        logger.info("Backed up %s -> %s", network_in, backup)

    n = pypsa.Network(str(network_in))
    non_coal_before = n.generators_t.p_max_pu.reindex(
        columns=n.generators.index[n.generators.carrier != "coal"]
    ).copy()

    plants, eaf = attach_za_coal_plants(n, plants_csv, eaf_csv, buses_csv)

    non_coal_after = n.generators_t.p_max_pu.reindex(columns=non_coal_before.columns)
    if not non_coal_before.equals(non_coal_after):
        raise SystemExit("GATE FAIL: non-coal generators_t.p_max_pu changed")

    if (n.generators.carrier == "coal").sum() != 15:
        raise SystemExit(f"GATE FAIL: coal generator count != 15")

    network_out.parent.mkdir(parents=True, exist_ok=True)
    n.export_to_netcdf(str(network_out))
    write_audit(audit_out, plants, eaf, str(plants_csv))
    return 0


if __name__ == "__main__":
    if "snakemake" in globals():
        sm = globals()["snakemake"]
        log_path = Path(sm.log[0]); log_path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(log_path), mode="w")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logging.getLogger().addHandler(fh)
        sys.exit(main(
            network_in=Path(sm.input.network_in),
            network_out=Path(sm.output.network_out),
            plants_csv=Path(sm.input.plants_csv),
            eaf_csv=Path(sm.input.eaf_csv),
            buses_csv=Path(sm.input.buses_csv),
            audit_out=Path(sm.output.audit),
            backup=Path(sm.output.backup),
        ))
    else:
        import argparse
        ap = argparse.ArgumentParser()
        ap.add_argument("--network-in", required=True)
        ap.add_argument("--network-out", required=True)
        ap.add_argument("--plants-csv", required=True)
        ap.add_argument("--eaf-csv", required=True)
        ap.add_argument("--buses-csv", required=True)
        ap.add_argument("--audit", required=True)
        ap.add_argument("--backup")
        a = ap.parse_args()
        sys.exit(main(
            network_in=Path(a.network_in),
            network_out=Path(a.network_out),
            plants_csv=Path(a.plants_csv),
            eaf_csv=Path(a.eaf_csv),
            buses_csv=Path(a.buses_csv),
            audit_out=Path(a.audit),
            backup=Path(a.backup) if a.backup else None,
        ))
```

---

### Step 5 — Wire the toggle in Snakefile

Edit `Snakefile` only at `rule apply_za_coal_eaf` (see Config Toggle Spec above). No other Snakemake rules change. `ruleorder: apply_za_coal_eaf > prepare_network` stays.

**No edits to `add_electricity.py`. No edits to `simplify_network.py` or `cluster_network.py`. No `exclude_carriers` change.**

---

### Step 6 — Run the pipeline

```bash
cd /Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth

# Dry run: keep scope on the already-local validation chain.
conda run -n pypsa-earth snakemake \
  --configfile configs/za/za_2023_fixed_validation.yaml \
  --cores 4 --ignore-incomplete --dryrun \
  --allowed-rules apply_za_coal_eaf solve_network_eaf solve_network_eaf_opc solve_network_eaf_opc_cap \
  --forcerun apply_za_coal_eaf solve_network_eaf solve_network_eaf_opc solve_network_eaf_opc_cap \
  "results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF.nc" \
  "results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC.nc" \
  "results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc"

# Full run.
conda run -n pypsa-earth snakemake \
  --configfile configs/za/za_2023_fixed_validation.yaml \
  --cores 4 --ignore-incomplete \
  --allowed-rules apply_za_coal_eaf solve_network_eaf solve_network_eaf_opc solve_network_eaf_opc_cap \
  --forcerun apply_za_coal_eaf solve_network_eaf solve_network_eaf_opc solve_network_eaf_opc_cap \
  "results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF.nc" \
  "results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC.nc" \
  "results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc"
```

Expected rule chain for this scoped run: **`apply_za_coal_eaf`** (now bound to 13g script) → `solve_network_eaf` / `solve_network_eaf_opc` / `solve_network_eaf_opc_cap`.

Do not use broad `--forceall` for this local calibration pass. In the 2026-05-15 refresh, `--forceall` entered `retrieve_databundle_light.py` and stalled on upstream data retrieval. If a full source rebuild is truly needed, run it as a separate reproducibility task.

---

## Acceptance Gates

```python
import pypsa
import pandas as pd

n = pypsa.Network(
    "results/za_2023_fixed_validation/networks/"
    "elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc"
)

coal_gens = n.generators[n.generators.carrier == "coal"]
coal_dispatch_h = n.generators_t.p[coal_gens.index].sum(axis=1)
coal_twh = coal_dispatch_h.sum() / 1e6

esk = pd.read_csv(
    "data/za_validation/eskom_2023_hourly_clean.csv",
    parse_dates=["time"], index_col="time"
)
coal_col = [c for c in esk.columns if "coal" in c.lower() and "sasol" not in c.lower()]

print(f"Coal generator count:  {len(coal_gens)} (pass: 15)")
print(f"Total load (TWh):      {n.loads_t.p_set.sum().sum()/1e6:.3f} (pass: mode-aware; ≥225.70 only when 13f enabled)")
print(f"Coal generation (TWh): {coal_twh:.2f}  (Eskom: 165.6 TWh, pass: Δ ≤ +8%)")
delta = (coal_twh - 165.627) / 165.627 * 100
print(f"Coal delta:            {delta:+.1f}%")

if coal_col:
    r = coal_dispatch_h.corr(esk[coal_col[0]])
    print(f"Coal Pearson r:        {r:.4f} (pass: ≥ 0.40 and above refreshed pre-13g comparator)")

# Toggle behaviour gate — verify the right script ran
audit = pd.read_csv("data/za_audit/za_coal_eaf_audit.csv")
disagg_active = "disaggregation_active" in audit.columns and bool(audit["disaggregation_active"].iloc[0])
print(f"13g disaggregation_active flag in audit: {disagg_active} (pass: True)")
assert disagg_active, "apply_za_coal_eaf ran the Module 12 script, not the 13g replacement"

# Verify hourly p_max_pu is per-plant (not all identical)
pmax = n.generators_t.p_max_pu[coal_gens.index]
assert pmax.shape == (len(n.snapshots), 15), f"unexpected p_max_pu shape {pmax.shape}"
assert pmax.std(axis=0).gt(0).all(), "Some plants have flat p_max_pu — EAF series not applied"
```

**Pass criteria (disaggregation only, before UC):**

| Check | Pass | Fail action |
|---|---|---|
| Coal generator count | 15 | Verify 13g script ran (audit flag); check `attach_za_coal_plants` n.mremove + n.add path |
| Total load | Mode-aware: ≥ 225.70 TWh when 13f enabled; lower pre-13f demand allowed when testing 13g-only | If 13f-enabled mode is below 225.70 TWh, Module 13f did not propagate. If 13g-only is lower, that is expected. |
| Coal generation Δ% | ≤ +8% vs Eskom 165.6 TWh | Check marginal costs / EAF normalization |
| Coal Pearson r | ≥ 0.40 and above refreshed pre-13g EAF/CAP comparator | Verify `generators_t.p_max_pu` has non-flat values; check seasonal pattern |
| Coal Pearson r floor | Must exceed refreshed pre-13g EAF/CAP value | If unchanged, disaggregation did not affect dispatch shape |
| Audit `disaggregation_active` | True | Wrong script bound — fix Snakefile toggle |
| `apply_za_coal_eaf` skipped or correct | `disaggregation_active = True` in audit when toggle on; original schema only when toggle off | EAF overlap not resolved correctly |

For module isolation, record the pass/fail result separately for 13g-only and 13f+13g. If coal Pearson r ≥ 0.40 in the accepted 13f+13g calibration path, mark module complete and proceed to Module 13h (UC). If < 0.40 despite 15 generators, investigate `generators_t.p_max_pu` — time-varying EAF is the primary mechanism at this stage.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Coal generator count < 15 after solve | 13g script did not run; original `apply_coal_eaf.py` overwrote | Check audit CSV has `disaggregation_active=True`; verify Snakefile toggle binding |
| `generators_t.p_max_pu` flat (all ~0.48) | p_max_pu assigned as static, not time-varying | Must use `n.generators_t.p_max_pu.loc[:, name] = series.values` **after** `n.add()` |
| `ValueError: za_coal_eaf… does not cover snapshots` | EAF CSV does not use exact 2023 hourly timestamps | Regenerate with `pd.date_range("2023-01-01", periods=8760, freq="h")` |
| Solve fails infeasible | unlikely without p_min_pu; check load_shedding enabled | Confirm `committable=False` — no MSL in 13g |
| `KeyError: bus 'XYZ' not in n.buses` | Bus assignment built against different cluster topology | Rebuild Step 3 against current `elec_s_34_ec_lc1_NoCO2-1H.nc` |
| `KeyError: station_name` mismatch | Case mismatch between plant_csv and assignment_csv | Use consistent casing (`Arnot`, not `arnot`) |
| Snakemake skips `apply_za_coal_eaf` | Cached output exists | `snakemake --forcerun apply_za_coal_eaf …` or delete `…-EAF.nc` |
| `No bus-level weekly availability profiles could be built` before 13g | `data/custom_powerplants.csv` has blank coal `bus` values after a forced fleet rebuild | Rerun `build_za_grid_spatial`; then retry the scenario layer |
| Broad forced rebuild enters `retrieve_databundle_light.py` | `--forceall` reaches upstream retrieval rules | Stop; use the scoped `--allowed-rules` scenario-layer command above unless doing a full reproducibility rebuild |
| Two workbooks disagree on BASE outage rows | `Coal_Flexibilisation/.../plant_availability.xlsx` vs `Benchmark_2023/.../plant_availability.xlsx` differ | Document canonical 2023 source; reconcile before re-running |

---

## Files Created or Modified

| File | Repo | Action |
|---|---|---|
| `scripts/build_za_coal_plants.py` | Earth | Created — builds CSVs |
| `scripts/za_fleet/build_za_coal_plants_network.py` | Earth | Created — toggle-on replacement script for `apply_za_coal_eaf` rule |
| `data/za_validation/za_coal_plants_2023.csv` | Earth | Created — 15-plant specs (includes UC columns for Module 13h) |
| `data/za_validation/za_coal_eaf_hourly_2023.csv` | Earth | Created — 8760 × 15 hourly p_max_pu |
| `data/za_validation/za_coal_bus_assignment.csv` | Earth | Created — plant → bus mapping (built against `elec_s_34_ec_lc1_NoCO2-1H.nc`) |
| `Snakefile` | Earth | Modified — `apply_za_coal_eaf` rule's `script:` binding made config-conditional; 3 conditional inputs added |
| `configs/za/za_2023_fixed_validation.yaml` | Earth | Modified — `za_coal_disaggregation:` block added |
| `scripts/za_fleet/apply_coal_eaf.py` | Earth | **Unmodified** — runs unchanged when toggle off |
| `scripts/add_electricity.py` | Earth | **Unmodified** — no hook added here |
| `data/za_audit/za_coal_eaf_audit.csv` | Earth | Schema extended: adds `disaggregation_active` boolean; existing columns preserved |
| `networks/za_2023_fixed_validation/elec_s_34_ec_lc1_NoCO2-1H-EAF.nc` | Earth | Rebuilt by 13g script (same filename) |
| `results/.../elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc` | Earth | Re-solved |

---

## Hard Constraints

- Read RSA source files only — do **not** modify RSA repo
- Do **not** include `Sasol_coal` — outside Eskom MLR perimeter
- Do **not** set `committable=True` — that is Module 13h
- Do **not** set `p_min_pu` — that is Module 13h
- Do **not** default `za_coal_disaggregation.uc.enable` to true — 13g must remain runnable as the no-UC control
- Do **not** add `exclude_carriers: [coal]` to cluster_options — not needed under this design and would change Module 12 baseline if toggle off
- Do **not** modify `apply_coal_eaf.py` — backward-compat fallback must stay intact
- The Snakefile toggle must default to backward-compatible behavior when `za_coal_disaggregation` key is absent or `enable: false`

---

## Open Items For Implementing Agent To Verify Before Coding

1. **Workbook path reconciliation.** Confirm `Benchmark_2023/sub_scenarios/plant_availability.xlsx` and `Coal_Flexibilisation/sub_scenarios/plant_availability.xlsx` have identical BASE planned+unplanned rows for 2023. If not, pick the canonical source for 13g and document.
2. **`elec_s_34_ec_lc1_NoCO2-1H.nc` existence at Step 3.** Step 3 reads the prepared but pre-EAF network. Current local baseline exists and was refreshed on 2026-05-15. If missing, produce it explicitly before 13g; do not use broad `--forceall` unless intentionally rebuilding raw resources.
3. **Notebook check on Pearson r decomposition.** Inspect `notebooks/za_validation/12_dispatch_calibration/dispatch_calibration_validation.ipynb` for whether RSA's 0.585 includes UC effects. If yes, the 0.40 13g gate is reasonable. If RSA's 0.585 is EAF+merit-order only, 13g should aim higher and 13h delivers smaller marginal gain. Adjust 13h gate downward only if notebook contradicts.
4. **Confirm `eskom_2023_hourly_clean.csv` coal column name.** Pearson r computation in the gate uses the first column matching `coal` and not `sasol`. If columns are named `coal_eskom`, `coal_dispatch`, etc., make sure exactly one matches.
