# Module 13g — Coal Disaggregation: 15-Plant Injection into PyPSA-Earth

**Target agent:** Claude Opus or Codex (standalone — no prior conversation context)
**Working directory (Earth):** `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth`
**Working directory (RSA inputs):** `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-rsa`
**Conda environment:** `pypsa-earth`
**Solver:** Gurobi (required for re-solve)
**Prerequisites:** Module 13f must be complete before running this module (Earth total load ≥ 225.70 TWh).

---

## Purpose

Replace PyPSA-Earth's single aggregated `coal` carrier with 15 named Eskom coal stations. Each plant receives its own `p_nom`, `marginal_cost`, and time-varying `p_max_pu(t)`, built from the same RSA input files as the `S_2023BM` benchmark. **No unit commitment in this module** — UC is added separately in Module 13h.

The disaggregation alone addresses two of the three structural gaps identified in Module 13e:
- Seasonal EAF variation (flat 0.48 → weekly outage profile normalized to 0.48)
- Plant-level merit order (single aggregated cost → 15 distinct marginal costs)

Expected improvement: coal Pearson r from 0.332 (current Earth) to ≥ 0.45 from disaggregation and seasonal availability alone. Module 13h adds UC to push toward RSA's 0.585.

This module takes the **same input files as RSA** — it does not extract from RSA's solved network.

---

## Context

### Why RSA coal beats Earth (Module 13e)

Three structural reasons, addressed in two stages:

| Feature | Current Earth | After 13g | After 13h |
|---|---|---|---|
| Temporal EAF variation | Flat 0.48 | Weekly profile, normalized to 0.48 | Same as 13g |
| Plant-level merit order | Single aggregated coal | 15 plants, individual marginal costs | Same as 13g |
| Linearised UC (MSL + ramp) | None | None | committable=True, p_min_pu=0.7 |

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

The UC config parameters (`override_coal_msl: 0.7`, `coal_ramp_rate_multiplier: 1.5`) are **recorded in the CSV but not wired into PyPSA in this module** — they are used in Module 13h.

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
- `low_group`: 27.93 R/GJ → dispatches cheapest (Medupi, Matimba, Duvha, Lethabo)
- `med_group`: 40.01 R/GJ → dispatches second (Arnot, Hendrina, Kendal, Majuba)
- `high_group`: 48.31 R/GJ → dispatches last (Camden, Grootvlei, Kelvin, Kriel, Kusile, Matla, Tutuka)

**Marginal cost formula (R/MWh, then convert to EUR/MWh):**
```
marginal_cost_R = heat_rate × fuel_price_R_per_GJ + variable_om_R_per_MWh
marginal_cost_EUR = marginal_cost_R / 20.0   # 1 EUR ≈ 20 ZAR, 2023 average
```

### How RSA builds hourly p_max_pu(t)

In EAF_48 + BASE, all 15 Eskom coal plants share the same annual EAF (0.48) and the same weekly outage profile. The temporal variation in `p_max_pu` comes entirely from the outage profile, not from plant-specific differences.

Algorithm:
1. Read `outage_profiles`, scenario `BASE`, types `planned` and `unplanned`. Keep only rows where `week` is a numeric integer (1–52); discard rows where `week` = `"average"`, `"std_dev_noise"`, etc.
2. For each week w: `avail_wk[w] = 1 − planned[w] − unplanned[w]` (use any plant column — they are all identical in BASE+EAF_48).
3. Normalize: `scale = 0.48 / mean(avail_wk)` → `avail_wk_scaled[w] = clip(avail_wk[w] × scale, 0, 1)`.
4. Expand to 8760 hours: for each hourly timestamp in 2023, look up its ISO week number (1–52); use `avail_wk_scaled[min(iso_week, 52)]` for that hour.
5. Result: Jan mean ≈ 0.452, Jul mean ≈ 0.530, annual mean = 0.480.

---

## Implementation Steps

### Step 1 — Create the preprocessing script

Create `scripts/build_za_coal_plants.py` in the Earth repo. Run it once; its outputs are stable data files committed to `data/za_validation/`.

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
- `p_min_pu` = 0.7 (from `override_coal_msl = 0.7` — overrides 0.65 in fixed_technologies) — stored but not used until 13h
- `ramp_limit_up_per_h` = `max_ramp_up (%/h)` × 1.5 / 100 (`coal_ramp_rate_multiplier = 1.5`) — stored but not used until 13h
- `ramp_limit_down_per_h` = `max_ramp_down (%/h)` × 1.5 / 100 — stored but not used until 13h
- `start_up_cost_eur` = `start_up_cost (R)` / 20.0 — stored but not used until 13h

**`data/za_validation/za_coal_eaf_hourly_2023.csv`** — 8760 rows × 15 columns (one per plant name):
- Index: `datetime` (hourly, `2023-01-01 00:00` to `2023-12-31 23:00`)
- Values: `p_max_pu` float, same for all 15 columns (uniform EAF_48 + BASE profile)

#### Parsing `outage_profiles` (important — messy sheet)

The `outage_profiles` sheet has extra non-data rows mixed in (`week` = `"average"`, `"std_dev_noise"`, etc.). Filter to numeric weeks only:

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

Use `Arnot` column (or any single plant column) for the weekly availability series — all plants are identical in BASE+EAF_48.

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
print(f"Jan mean EAF: {eaf.loc['2023-01'].mean().mean():.4f}  (expected ~0.452)")
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
| Jan mean EAF | 0.440–0.470 |
| Jul mean EAF | 0.510–0.545 |
| Total p_nom | ~43 419 MW |
| Cheapest marginal cost | Medupi or Matimba (low_group, lowest heat rate) |
| Most expensive | Grootvlei (high_group, 15.00 GJ/MWh) |

---

### Step 3 — Compute bus assignment

Each plant must be attached to the geographically nearest of the 34 cluster buses.

```python
import pypsa
import pandas as pd
from scipy.spatial import KDTree

# Load the current solved network (post-Module-13f)
n = pypsa.Network(
    "results/za_2023_fixed_validation/networks/"
    "elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc"
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

**Sanity check:** Matimba and Medupi (Limpopo, ~−23.4°lat) should map to northern cluster buses. Lethabo (Free State, ~−26.7°lat) and Kendal/Duvha/Kriel (Mpumalanga, ~−25.9 to −26.3°lat) to eastern/central buses.

Write `za_coal_bus_assignment.csv` as a static committed file — it does not change unless the clustering changes.

---

### Step 4 — Add attach_za_coal_plants to add_electricity.py

Add the function to `scripts/add_electricity.py`. Place it near the other `attach_*` functions (after `attach_load`, before or after `attach_conventional_generators`).

#### Function (disaggregation only — no UC)

```python
def attach_za_coal_plants(n, plants_csv, eaf_csv, bus_assignment_csv):
    """
    Replace aggregated coal carrier with 15 named Eskom stations.
    Wires p_nom, marginal_cost, and time-varying p_max_pu.
    Unit commitment parameters are NOT set here — see Module 13h.
    """
    import pandas as pd

    plants = pd.read_csv(plants_csv)
    eaf = pd.read_csv(eaf_csv, index_col=0, parse_dates=True)
    bus_assign = pd.read_csv(bus_assignment_csv).set_index("station_name")["bus"]

    # Reindex EAF to network snapshots
    eaf = eaf.reindex(n.snapshots)
    if eaf.isna().any().any():
        raise ValueError(
            "za_coal_eaf_hourly_2023.csv does not cover all network snapshots. "
            f"First missing: {eaf.index[eaf.isna().any(axis=1)][0]}"
        )

    # Remove existing aggregated coal generators
    existing_coal = n.generators[n.generators.carrier == "coal"].index
    if len(existing_coal) > 0:
        n.mremove("Generator", existing_coal)

    # Add per-plant generators
    for _, row in plants.iterrows():
        name = row["station_name"]
        bus = bus_assign.loc[name]

        n.add(
            "Generator",
            name,
            bus=bus,
            carrier="coal",
            p_nom=row["p_nom_mw"],
            marginal_cost=row["marginal_cost_eur_per_mwh"],
            efficiency=3.6 / row["avg_heat_rate_gj_per_mwh"],
            committable=False,   # UC added in Module 13h
        )

    # Set time-varying p_max_pu — must be done after n.add(), not inside it
    for _, row in plants.iterrows():
        name = row["station_name"]
        n.generators_t.p_max_pu[name] = eaf[name].values
```

#### Wire the call in add_electricity.py

Locate the main `__main__` block or the function that calls `attach_load`, `attach_conventional_generators`, etc. Add the conditional call:

```python
# ZA per-plant coal disaggregation (Module 13g)
za_coal_plants = snakemake.input.get("za_coal_plants", None)
za_coal_eaf    = snakemake.input.get("za_coal_eaf", None)
za_coal_buses  = snakemake.input.get("za_coal_buses", None)

if za_coal_plants and za_coal_eaf and za_coal_buses:
    logger.info("ZA coal disaggregation: replacing aggregated coal with 15 plants")
    attach_za_coal_plants(n, za_coal_plants, za_coal_eaf, za_coal_buses)
```

This call must happen **after** the normal conventional generator attachment (so the aggregated coal generators exist to be removed) but **before** any network consistency checks.

#### Wire the inputs in Snakefile

In `rule add_electricity:`, add three optional inputs that are only required for the ZA validation run. Use the run name check pattern already present in the Snakefile:

```python
# add_electricity inputs (add alongside existing inputs)
za_coal_plants=(
    "data/za_validation/za_coal_plants_2023.csv"
    if config.get("run", {}).get("name", "") == "za_2023_fixed_validation"
    else []
),
za_coal_eaf=(
    "data/za_validation/za_coal_eaf_hourly_2023.csv"
    if config.get("run", {}).get("name", "") == "za_2023_fixed_validation"
    else []
),
za_coal_buses=(
    "data/za_validation/za_coal_bus_assignment.csv"
    if config.get("run", {}).get("name", "") == "za_2023_fixed_validation"
    else []
),
```

---

### Step 5 — Protect per-plant coal from cluster aggregation

PyPSA-Earth's `cluster_network` step aggregates generators with the same carrier on the same bus by default. Since each cluster bus may receive multiple plants (e.g., Kendal and Duvha both in Mpumalanga cluster), this would merge them back to fewer generators, discarding the per-plant structure.

In `configs/za/za_2023_fixed_validation.yaml`, ensure `coal` is listed in `exclude_carriers` for both the `simplify_network` and `cluster_network` steps:

```yaml
cluster_options:
  simplify_network:
    p_threshold_drop_isolated: false    # from Module 13f
    p_threshold_merge_isolated: false   # from Module 13f
    exclude_carriers: [coal]            # NEW — prevent coal aggregation in simplify step
  cluster_network:
    exclude_carriers: [coal]            # NEW — prevent coal aggregation in cluster step
```

**Verify after clustering** that `n.generators[n.generators.carrier == "coal"]` still has 15 rows in `elec_s_34.nc`.

---

### Step 6 — Run the pipeline

```bash
cd /Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth

# Dry run
snakemake --configfile configs/za/za_2023_fixed_validation.yaml \
  --cores 4 --dryrun \
  "results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc"

# Full run
GRB_LICENSE_FILE=/Users/nylan/gurobi.lic \
snakemake --configfile configs/za/za_2023_fixed_validation.yaml \
  --cores 4 \
  "results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc"
```

Expected rule chain: `add_electricity` → `simplify_network` → `cluster_network` → `add_extra_components` → `prepare_network` → `solve_network`.

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
coal_dispatch_h = n.generators_t.p[coal_gens.index].sum(axis=1)   # MW
coal_twh = coal_dispatch_h.sum() / 1e6

# Load Eskom observed hourly coal (from notebook input CSV)
esk = pd.read_csv(
    "data/za_validation/eskom_2023_hourly_clean.csv",
    parse_dates=["time"], index_col="time"
)
coal_col = [c for c in esk.columns if "coal" in c.lower()
            and "sasol" not in c.lower()]

print(f"Coal generator count:  {len(coal_gens)} (pass: 15)")
print(f"Total load (TWh):      {n.loads_t.p_set.sum().sum()/1e6:.3f} (pass: ≥225.70)")
print(f"Coal generation (TWh): {coal_twh:.2f}  (Eskom: 165.6 TWh, pass: Δ ≤ +8%)")
delta = (coal_twh - 165.627) / 165.627 * 100
print(f"Coal delta:            {delta:+.1f}%")

if coal_col:
    r = coal_dispatch_h.corr(esk[coal_col[0]])
    print(f"Coal Pearson r:        {r:.4f} (pass: ≥ 0.45; was 0.332)")
```

**Pass criteria (disaggregation only, before UC):**

| Check | Pass | Fail action |
|---|---|---|
| Coal generator count | 15 | Check `exclude_carriers` protected from aggregation |
| Total load | ≥ 225.70 TWh | Module 13f fix not in effect |
| Coal generation Δ% | ≤ +8% vs Eskom 165.6 TWh | Check marginal costs / EAF normalization |
| Coal Pearson r | ≥ 0.45 | Verify `generators_t.p_max_pu` has non-flat values; check seasonal pattern |
| Coal Pearson r (was) | 0.332 | If still 0.332, disaggregation did not take effect |

If coal Pearson r is ≥ 0.45, mark this module complete and proceed to Module 13h (UC). If Pearson r is < 0.45 despite 15 generators being present, investigate `generators_t.p_max_pu` — the time-varying EAF is the primary mechanism at this stage.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Coal generator count < 15 after solve | Cluster aggregation merged plants | Confirm `exclude_carriers: [coal]` in both `simplify_network` and `cluster_network` blocks |
| `generators_t.p_max_pu` flat (all 0.48) | p_max_pu assigned as static, not time-varying | Must use `n.generators_t.p_max_pu[name] = series.values` **after** `n.add()` |
| `ValueError: za_coal_eaf… does not cover snapshots` | EAF CSV does not use exact 2023 hourly timestamps | Regenerate with `pd.date_range("2023-01-01", periods=8760, freq="h")` |
| Solve fails with infeasibility | p_min_pu not set but coal dispatch violates some constraint | Verify `committable=False` — no MSL applied in 13g |
| Snakemake does not trigger `add_electricity` | Input files pre-exist; Snakemake sees no change | `touch data/za_validation/za_coal_plants_2023.csv` or delete `networks/za_2023_fixed_validation/elec.nc` |
| `KeyError: station_name` in bus assignment | Plant name mismatch between CSV and assignment file | Check consistent casing (`Arnot` not `arnot`) across all three CSV files |

---

## Files Created or Modified

| File | Repo | Action |
|---|---|---|
| `scripts/build_za_coal_plants.py` | Earth | Created |
| `data/za_validation/za_coal_plants_2023.csv` | Earth | Created — 15-plant specs (includes UC columns for Module 13h) |
| `data/za_validation/za_coal_eaf_hourly_2023.csv` | Earth | Created — 8760 × 15 hourly p_max_pu |
| `data/za_validation/za_coal_bus_assignment.csv` | Earth | Created — plant → bus mapping |
| `scripts/add_electricity.py` | Earth | Modified — `attach_za_coal_plants` added; conditional call wired |
| `Snakefile` | Earth | Modified — 3 optional inputs added to `rule add_electricity` |
| `configs/za/za_2023_fixed_validation.yaml` | Earth | Modified — `exclude_carriers: [coal]` added to both cluster steps |
| `networks/za_2023_fixed_validation/elec.nc` | Earth | Rebuilt |
| `results/.../elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc` | Earth | Re-solved |

---

## Hard Constraints

- Read RSA source files only — do **not** modify anything in the RSA repo
- Do **not** include `Sasol_coal` — Sasol Synfuels is outside Eskom MLR perimeter
- Do **not** set `committable=True` in this module — that is Module 13h
- Do **not** set `p_min_pu` in this module — that is Module 13h
- If `exclude_carriers` aggregation protection is not confirmed to work, **stop and report** before running the solve — the entire value of this module depends on preserving 15 generators through clustering
- The Snakefile change must be conditional on run name — non-ZA runs must not require ZA coal CSVs
