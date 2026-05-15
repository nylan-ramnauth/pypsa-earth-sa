# Module 13h — Coal Linearised Unit Commitment

**Target agent:** Claude Opus or Codex (standalone — no prior conversation context)
**Working directory:** `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth`
**Conda environment:** `pypsa-earth`
**Solver:** Gurobi (required — UC formulation significantly increases solve complexity)
**Prerequisites:** Module 13g must be complete and accepted (coal Pearson r ≥ 0.45, 15 generators present in solved network).

---

## Purpose

Add linearised unit commitment (UC) to the 15 named coal generators injected in Module 13g. UC adds minimum stable level (MSL), ramp limits, and startup costs per plant, matching the parameters from PyPSA-RSA's `S_2023BM` configuration.

Expected improvement: coal Pearson r from ≥ 0.45 (post-13g, disaggregation only) toward RSA's 0.585.

The UC parameters come from two RSA sources:
- `fixed_technologies.xlsx` (VAR_HR): per-plant ramp limits, min stable level, min up/down time, startup cost
- `S_2023BM` scenario config overrides: `override_coal_msl = 0.7`, `coal_ramp_rate_multiplier = 1.5`

All UC parameter values were already computed and stored in `data/za_validation/za_coal_plants_2023.csv` during Module 13g preprocessing. This module only wires them into PyPSA — no new data extraction required.

---

## Context

### UC parameters already in za_coal_plants_2023.csv

These columns were written in Module 13g but not used until now:

| CSV column | Source | Value / formula |
|---|---|---|
| `p_min_pu` | S_2023BM `override_coal_msl` | 0.7 (uniform for all plants) |
| `ramp_limit_up_per_h` | VAR_HR `max_ramp_up (%/h)` × 1.5 / 100 | per-plant, e.g. Medupi ≈ 0.896/h |
| `ramp_limit_down_per_h` | VAR_HR `max_ramp_down (%/h)` × 1.5 / 100 | per-plant (symmetric) |
| `min_up_time_h` | VAR_HR `min_up_time (h)` | 24 h for all Eskom coal |
| `min_down_time_h` | VAR_HR `min_down_time (h)` | 8 h for all Eskom coal |
| `start_up_cost_eur` | VAR_HR `start_up_cost (R)` / 20.0 | 25 000 EUR per plant (500 000 ZAR / 20) |

> **Verify these values before running.** Load `data/za_validation/za_coal_plants_2023.csv` and confirm the columns are present and non-null for all 15 plants.

### What linearised UC does in PyPSA

When `committable=True` on a generator, PyPSA adds a binary commitment variable `status_t` (0/1) per snapshot. The LP relaxation (linearised UC) replaces the binary with a continuous variable in [0,1]. Constraints added:
- `p ≥ p_min_pu × p_nom × status` (minimum stable level)
- `p ≤ p_max_pu × p_nom × status` (maximum output, already time-varying from 13g)
- `status[t] − status[t−1] ≤ status[t−min_up_time..t]` (min up time)
- `status[t−1] − status[t] ≤ (1 − status[t−min_down_time..t])` (min down time)
- Ramp limits: `p[t] − p[t−1] ≤ ramp_limit_up × p_nom`
- Start-up cost added to objective when `status[t] − status[t−1] > 0`

**Solver tractability:** Coal-only linearised UC on 15 plants × 8760 hours is well within Gurobi's LP capacity. No integer branch-and-bound — this is a continuous relaxation. Solve time expected to increase by 2–4× versus the non-UC run.

---

## Implementation Steps

### Step 1 — Verify prerequisites

Confirm Module 13g is accepted:

```python
import pypsa, pandas as pd

n = pypsa.Network(
    "results/za_2023_fixed_validation/networks/"
    "elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc"
)

coal_gens = n.generators[n.generators.carrier == "coal"]
print(f"Coal generators: {len(coal_gens)}  (must be 15 to proceed)")

# Check time-varying p_max_pu exists
coal_pmax_cols = [c for c in n.generators_t.p_max_pu.columns if c in coal_gens.index]
print(f"Coal p_max_pu columns: {len(coal_pmax_cols)}  (must be 15)")

# Check UC params exist in CSV
plants = pd.read_csv("data/za_validation/za_coal_plants_2023.csv")
uc_cols = ["p_min_pu", "ramp_limit_up_per_h", "ramp_limit_down_per_h",
           "min_up_time_h", "min_down_time_h", "start_up_cost_eur"]
missing = [c for c in uc_cols if c not in plants.columns or plants[c].isna().any()]
print(f"Missing UC columns: {missing}  (must be empty list)")
```

**Do not proceed if:**
- Coal generator count < 15
- Any UC column is missing or null in `za_coal_plants_2023.csv`

---

### Step 2 — Add add_za_coal_uc to add_electricity.py

Add a second function `add_za_coal_uc` to `scripts/add_electricity.py`, placed directly after `attach_za_coal_plants`.

```python
def add_za_coal_uc(n, plants_csv):
    """
    Set linearised unit commitment parameters on the 15 per-plant coal generators
    already attached by attach_za_coal_plants (Module 13g).

    Parameters
    ----------
    n : pypsa.Network
        Network that already contains 15 coal generators from attach_za_coal_plants.
    plants_csv : str
        Path to data/za_validation/za_coal_plants_2023.csv (contains UC columns).
    """
    import pandas as pd

    plants = pd.read_csv(plants_csv).set_index("station_name")

    coal_gens = n.generators[n.generators.carrier == "coal"].index
    if len(coal_gens) == 0:
        raise ValueError(
            "No coal generators found. Module 13g must run before Module 13h."
        )

    for name in coal_gens:
        # Generator names may have a bus suffix after clustering, e.g. "Arnot 1 2"
        # Match by original plant name prefix
        plant_key = next(
            (k for k in plants.index if name.startswith(k)), None
        )
        if plant_key is None:
            raise ValueError(
                f"Cannot find UC parameters for generator '{name}'. "
                f"Available plant keys: {list(plants.index)}"
            )
        row = plants.loc[plant_key]

        n.generators.loc[name, "committable"]       = True
        n.generators.loc[name, "p_min_pu"]          = float(row["p_min_pu"])
        n.generators.loc[name, "ramp_limit_up"]     = float(row["ramp_limit_up_per_h"])
        n.generators.loc[name, "ramp_limit_down"]   = float(row["ramp_limit_down_per_h"])
        n.generators.loc[name, "min_up_time"]       = int(row["min_up_time_h"])
        n.generators.loc[name, "min_down_time"]     = int(row["min_down_time_h"])
        n.generators.loc[name, "start_up_cost"]     = float(row["start_up_cost_eur"])

    logger.info(
        f"UC parameters applied to {len(coal_gens)} coal generators "
        f"(p_min_pu=0.7, ramp_limit from VAR_HR × 1.5)"
    )
```

> **Name-matching note:** After `cluster_network`, generator names may gain bus suffixes (e.g., `"Arnot 1 2"` → bus 2). The `startswith` match above handles this. If plant names in the CSV differ from generator names in any other way, adjust the matching logic accordingly and document the difference.

---

### Step 3 — Wire the call in add_electricity.py

In the same conditional block added for Module 13g, extend the call:

```python
# ZA per-plant coal disaggregation (Module 13g)
za_coal_plants = snakemake.input.get("za_coal_plants", None)
za_coal_eaf    = snakemake.input.get("za_coal_eaf", None)
za_coal_buses  = snakemake.input.get("za_coal_buses", None)

if za_coal_plants and za_coal_eaf and za_coal_buses:
    logger.info("ZA coal disaggregation: replacing aggregated coal with 15 plants")
    attach_za_coal_plants(n, za_coal_plants, za_coal_eaf, za_coal_buses)

# ZA coal UC (Module 13h) — applied after disaggregation
za_coal_uc = snakemake.config.get("za_coal_uc", False)
if za_coal_plants and za_coal_uc:
    logger.info("ZA coal UC: applying linearised unit commitment to coal plants")
    add_za_coal_uc(n, za_coal_plants)
```

The `za_coal_uc` flag is controlled by the ZA validation config, not the Snakefile. This allows toggling UC on/off without changing the pipeline structure.

---

### Step 4 — Add the UC flag to the ZA validation config

In `configs/za/za_2023_fixed_validation.yaml`, add:

```yaml
za_coal_uc: true
```

This single line enables UC for the ZA validation run. Setting it to `false` reverts to the Module-13g-only (disaggregation, no UC) behaviour for comparison.

---

### Step 5 — Run the pipeline

Only `add_electricity` and downstream rules need to re-run (same files, new config flag):

```bash
cd /Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth

# Touch config to trigger rebuild
touch configs/za/za_2023_fixed_validation.yaml

# Dry run
snakemake --configfile configs/za/za_2023_fixed_validation.yaml \
  --cores 4 --dryrun \
  "results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc"

# Full run (expect 2–4× longer solve than non-UC)
GRB_LICENSE_FILE=/Users/nylan/gurobi.lic \
snakemake --configfile configs/za/za_2023_fixed_validation.yaml \
  --cores 4 \
  "results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc"
```

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

# UC verification
print("=== UC parameter check ===")
print(f"committable: {coal_gens['committable'].all()}  (must be True)")
print(f"p_min_pu range: {coal_gens['p_min_pu'].min():.2f}–{coal_gens['p_min_pu'].max():.2f}  (must be 0.7)")
print(f"ramp_limit_up range: {coal_gens['ramp_limit_up'].min():.3f}–{coal_gens['ramp_limit_up'].max():.3f}")

# Dispatch metrics
print("\n=== Dispatch metrics ===")
load = n.loads_t.p_set.sum().sum() / 1e6
print(f"Total load (TWh):      {load:.3f}  (pass: ≥225.70)")
print(f"Coal generation (TWh): {coal_twh:.2f}  (Eskom: 165.6 TWh, pass: Δ ≤ +8%)")
delta = (coal_twh - 165.627) / 165.627 * 100
print(f"Coal delta:            {delta:+.1f}%")

# Pearson r
esk = pd.read_csv(
    "data/za_validation/eskom_2023_hourly_clean.csv",
    parse_dates=["time"], index_col="time"
)
coal_col = [c for c in esk.columns if "coal" in c.lower() and "sasol" not in c.lower()]
if coal_col:
    r = coal_dispatch_h.reindex(esk.index).corr(esk[coal_col[0]])
    print(f"Coal Pearson r:        {r:.4f}  (target ≥0.55; RSA reference: 0.585)")

# MSL check — no generator should be dispatching between 0 and p_min_pu × p_nom
dispatching = n.generators_t.p[coal_gens.index]
for g in coal_gens.index:
    pmin = coal_gens.loc[g, "p_nom"] * 0.7
    between = dispatching[g][(dispatching[g] > 1.0) & (dispatching[g] < pmin * 0.95)]
    if len(between) > 0:
        print(f"WARNING: {g} has {len(between)} hours between 0 and MSL — "
              f"UC relaxation may have allowed sub-MSL dispatch")
```

**Pass criteria:**

| Check | Pass | Fail action |
|---|---|---|
| `committable` on all coal | True | UC call not reached; check config flag and conditional |
| `p_min_pu` = 0.7 | All coal generators | Check `add_za_coal_uc` name-matching logic |
| Coal generation Δ% | ≤ +8% | MSL forces higher output than needed — check load shedding; consider if p_min_pu is too high |
| Coal Pearson r | ≥ 0.55 | Primary target; if 0.50–0.55, document and proceed — gap may require plant-specific EAF (post-13h) |
| Coal Pearson r (floor) | ≥ 0.45 | Must exceed 13g result; if not, UC is hurting — check MSL forcing wrong plants |
| Sub-MSL dispatch warning | Zero hours (ideally) | Acceptable if < 50 hours total (numerical artifact); flag if > 200 hours |
| Solve completion | Gurobi optimal or near-optimal | If MIP gap > 1%, check if `committable=True` triggered integer formulation (should be LP with relaxation) |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Coal Pearson r does not improve vs 13g | UC params not applied (name mismatch) | Print `coal_gens['committable']` — if False, fix name matching in `add_za_coal_uc` |
| Coal generation delta jumps to > +15% | MSL forces plants on when load is low | Check if load shedding cost is competitive with UC startup cost; reduce `p_min_pu` trial to 0.5 to diagnose |
| Gurobi solving MIP instead of LP | `committable=True` triggering integer formulation | Verify PyPSA version uses `linearised_unit_commitment` (LP relaxation) not strict binary UC; check `n.lopf` or `n.optimize` call in `solve_network.py` |
| Solve takes > 8× longer than 13g | Integer formulation triggered | Same as above — must be LP relaxation |
| `ValueError: Cannot find UC parameters` | Generator name has bus suffix not matching plant key | Add logging to print generator name and plant keys; adjust startswith matching |
| Sub-MSL violations > 200 hours | PyPSA LP relaxation allowing fractional commitment | Expected for linearised UC; adjust `min_up_time` to 0 for cleaner relaxation if needed |

---

## Files Modified

| File | Action |
|---|---|
| `scripts/add_electricity.py` | Modified — `add_za_coal_uc` function added; conditional call wired |
| `configs/za/za_2023_fixed_validation.yaml` | Modified — `za_coal_uc: true` added |
| `results/.../elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc` | Re-solved |

No new data files — all UC parameters read from `za_coal_plants_2023.csv` created in Module 13g.

---

## Hard Constraints

- Do **not** set `committable=True` on nuclear, OCGT, or any other carrier — coal only
- Do **not** use strict binary (MIP) UC — linearised (LP relaxation) only; verify this is what PyPSA's `optimize` call uses for the ZA run
- Do **not** modify `za_coal_plants_2023.csv` — it was written in 13g and is read here as-is
- If Pearson r after UC is lower than after 13g (disaggregation-only), **stop and document** — do not accept a regression; the module must show net improvement over 13g

---

## Notes for Future Refinement (out of scope for 13h)

1. **Plant-specific EAF**: The largest remaining gap versus RSA is that EAF_48 assigns uniform 0.48 to all plants. Eskom's data portal (`unit_capability_factors`) publishes monthly UCLF/PCLF/OCLF per station back to 2018. Replacing the uniform profile with per-station monthly data is expected to push coal Pearson r from ~0.55 toward ~0.65–0.70, and is the primary candidate for a Module 13i.

2. **Strict binary UC**: Linearised UC is a relaxation. If a strict binary formulation is ever warranted (e.g., for policy dispatch analysis), Gurobi handles it but solve time increases to hours. Not needed for calibration validation.
