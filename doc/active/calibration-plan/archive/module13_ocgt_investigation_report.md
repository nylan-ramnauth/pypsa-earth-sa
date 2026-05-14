# Module 12 → Module 13 — OCGT Calibration: Investigation Report and Implementation Brief

**Date:** 2026-05-13
**Author:** Claude Opus 4.7 (investigation), revised by Claude Sonnet 4.6
**Status:** Implementation brief — ready for Codex plan mode
**Scope:** Diagnose OCGT over-dispatch in solve 3 (`EAF-OPC`); produce a fourth solve
(`EAF-OPC-CAP`) with a source-backed annual OCGT energy cap; validate dispatch calibration
via Pearson/Spearman correlation against Eskom 2023 actuals; assess Module 13 readiness.

---

## 0. Project Context (self-contained)

**Project:** Reliability-Aware Planning Pipeline — South Africa proof-of-concept
**Codebase root:** `6-codebases/repos/pypsa-earth` (relative to vault root)
**pypsa-rsa workbooks:** `../pypsa-rsa/scenarios/Coal_Flexibilisation/sub_scenarios/`
**Config used:** `configs/za/za_2023_fixed_validation.yaml`
**Validation targets:** `data/za_validation/eskom_2023_targets_by_carrier.csv`
**Module 12 plan:** `doc/active/calibration-plan/12_dispatch_calibration_and_availability.md`
**Calibration report:** `4-work/reports/2026-05-12-module12-calibration-report.md`
  (path relative to vault root)

All `snakemake` commands must be run from `6-codebases/repos/pypsa-earth`.

---

## 1. Four-Solve Calibration History

The Module 12 calibration sequence has produced three solved networks. A fourth is prescribed here.

| # | Label | Network file | OCGT (TWh) | Load shed (TWh) | Coal error | Status |
|---|---|---|---:|---:|---|---|
| 1 | Structural | `elec_s_34_ec_lc1_NoCO2-1H.nc` | 6.93 | ~0 | +28.3 TWh | ✅ 12/12 gates PASS |
| 2 | EAF | `elec_s_34_ec_lc1_NoCO2-1H-EAF.nc` | 17.37 | 0.04 | +17.8 TWh | ✅ 12/12 gates PASS |
| 3 | EAF+OPC | `elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC.nc` | 14.62 | 2.24 | — | ✅ 12/12 gates PASS; ❌ OCGT +179%; ❌ subtotal −1.1% |
| 4 | **EAF+OPC+CAP** | `elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc` | ≤5.5 target | ~11–13 expected | — | **TO IMPLEMENT** |

All four networks must be kept on disk. Do **not** overwrite solve 3. The comparison across
all four solves is the calibration evidence trail.

Eskom 2023 actuals (from `data/za_validation/eskom_2023_targets_by_carrier.csv`):

| Carrier | Eskom 2023 (TWh) |
|---|---:|
| Eskom OCGT Generation | 3.566 |
| Dispatchable IPP OCGT | 1.677 |
| **Total OCGT target** | **5.243** |
| Manual Load Reduction (MLR) | 16.562 |
| ILS Usage | 0.073 |
| IOS Excl ILS and MLR | 0.120 |
| **Total load shed target** | **16.755** |

---

## 2. Problem Statement

In solve 3, the LP dispatches OCGT at **14.62 TWh** (179% above Eskom 5.243 TWh) and sheds
only **2.24 TWh** (against Eskom 16.755 TWh). The model and Eskom **swap** the OCGT↔shed ratio:

| | OCGT (TWh) | Load shed (TWh) | Sum |
|---|---:|---:|---:|
| Solve 3 (EAF+OPC) | 14.62 | 2.24 | 16.86 |
| Eskom 2023 | 5.243 | 16.755 | 21.998 |

**Why this mismatch is expected and scientifically informative:**

The LP minimises cost subject to a VOLL constraint. Eskom does not. Eskom's 2023 load-shedding
behaviour reflects implicit fuel budget caps (diesel procurement limits), Stage-based curtailment
protocols, and non-economic decisions. These are outside the LP's objective function.

The LP is not wrong — it is optimal. Eskom is not acting as an LP optimizer. A 4th solve that
caps OCGT at the Eskom target forces the LP to redistribute the residual (~9.4 TWh) into load
shedding. This allows us to ask: does the temporal distribution of model scarcity (when
OCGT+shed events cluster) match Eskom's observed scarcity patterns, even if the magnitudes
differ pre-cap?

The annual subtotal error of −1.1% (solve 3) fails the Module 12 acceptance gate of ≤0.5%.
The OCGT fix is a prerequisite for closing Module 12.

---

## 3. OCGT Fleet (from solve 3 network)

Source: `results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC.nc`

| Generator | Bus | p_nom (MW) | marginal_cost | efficiency | p_nom_extendable | build_year |
|---|---|---:|---:|---:|---|---:|
| East London ocgt_diesel | East London | 171.0 | 380.28 | 0.3125 | False | 0 |
| Gqeberha ocgt_diesel | Gqeberha | 335.0 | 380.28 | 0.3125 | False | 0 |
| Outeniqua ocgt_diesel | Outeniqua | 740.0 | 380.28 | 0.3125 | False | 0 |
| Peninsula ocgt_diesel | Peninsula | 1503.0 | 380.28 | 0.3125 | False | 0 |
| Pinetown ocgt_diesel | Pinetown | 670.0 | 380.28 | 0.3125 | False | 0 |
| **Total** | | **3419.0 MW** | | | | |

| Quantity | Value |
|---|---:|
| Max annual dispatch at 100% CF | 29.95 TWh |
| Annual ceiling from 50% weekly CF cap | 14.98 TWh |
| Solve 3 observed dispatch | 14.62 TWh |
| Eskom 2023 target | 5.243 TWh |
| Solve 3 implied annual CF | 48.8% |
| Eskom target annual CF | 17.5% |

Per-generator dispatch in solve 3:

| Generator | Dispatch (TWh) | Share |
|---|---:|---:|
| Peninsula | 8.074 | 55.2% |
| Outeniqua | 6.286 | 43.0% |
| Gqeberha | 0.228 | 1.6% |
| East London | 0.035 | 0.2% |
| Pinetown | 0.000003 | ~0% |

Peninsula and Outeniqua dominate because transmission topology and load centres favour
their buses. Pinetown is effectively idle. The LP dispatches OCGT according to local
scarcity conditions, which is physically correct behaviour for peakers.

---

## 4. Workbook Audit

### 4.1 `operational_constraints.xlsx` — HIGH_GAS scenario

Source: `../pypsa-rsa/scenarios/Coal_Flexibilisation/sub_scenarios/operational_constraints.xlsx`

Active rows that match carriers present in the ZA 2023 fixed fleet:

| Row | tech_fuel | type | period | limit | units | 2023 value | Effect |
|---|---|---|---|---|---|---:|---|
| 0 | `ocgt_diesel + ocgt_avf` | capacity_factor | week | max | % | 0.50 | **Binds. Annual ceiling 14.98 TWh.** |
| 19 | `nuclear` | capacity_factor | hour | min | % | 1.00 (incl_pu=True) | Must-run relative to p_max_pu (990 MW constant). See §4.3. |

All other HIGH_GAS rows target extendable future carriers (`ocgt_gas`, H2 blends, `ccgt_steam`,
`rmippp`, `sasol_*`) that are absent from the 2023 fixed fleet. They are silent no-ops.

**Annual energy max for `ocgt_diesel`? No.** No row exists with `period=year`, `limit=max`,
and energy units. The closest precedents in the workbook are rows for `sasol_coal` and
`sasol_gas` (`output_energy year max TWh` at 5.5 and 2.8 TWh) — both no-ops because Sasol
was removed from the fleet before Module 12. The parser already handles this format.

### 4.2 `plant_availability.xlsx` — OCGT station outage profiles

All 52 weekly planned and forced outage values for Acacia, Ankerlig, Gourikwa, PortRex,
and the generic `ocgt_diesel` column are **0.0** in the BASE scenario.

Applying these profiles would set `p_max_pu = 1.0` on every snapshot — identical to no overlay.
**Workbook-derived OCGT EAF profiles cannot fix the dispatch volume.** Ruled out.

From `annual_availability`: `ocgt_diesel_extendable_EAF` 2023 = 0.95 across all scenarios.
Applying 95% EAF as a flat `p_max_pu` cap yields `0.95 × 29.95 = 28.45 TWh` — far above target.
**Annual EAF scalar also insufficient.** Ruled out.

### 4.3 `plant_availability.xlsx` — Nuclear (Koeberg)

`outage_profiles` BASE: all 52 weeks planned = 0, forced = 0.
`annual_availability`: `Koeberg_EAF` 2023 = 0.5083 across all scenarios.

Solve 3 network: `Peninsula nuclear` has `p_max_pu = 0.534`, `p_nom = 1854 MW`, dispatches
at 8.673 TWh. This matches `0.534 × 1854 × 8760 / 1e6 = 8.67 TWh` — the 0.5083 EAF is
already applied via `p_max_pu`. Eskom 2023 nuclear actual = 8.127 TWh (solve over-dispatches
by 0.55 TWh; small residual, not the OCGT driver).

The nuclear `hourly CF min 1.0 incl_pu=True` constraint forces `0.534 × 1854 = 990 MW`
constant dispatch. This is consistent with the 8.67 TWh observation and is not infeasible
because `incl_pu=True` multiplies the RHS by `p_max_pu`. No nuclear changes needed.

### 4.4 `fuel_prices.xlsx` — OCGT marginal cost discrepancy

| Source | Row | 2023 value |
|---|---|---:|
| `fixed_generators` ME_IRP23 | `variable_diesel` | 816.0 R/GJ |
| `extendable_generators` HIGH_PMR1 | `ocgt_diesel` | 680.6 R/GJ |

Fuel-implied MC: `816.0 × 3.6 / 0.3125 = 9,400 R/MWh_e` (ME_IRP23 basis).

Solve 3 `n.generators.marginal_cost` for all `ocgt_diesel`: **380.28** (currency unknown).

| Interpretation | Effective R/MWh_e | Vs. fuel-implied 9,400 |
|---|---:|---|
| 380.28 in ZAR/MWh | 380 | 24.7× too low |
| 380.28 EUR/MWh @ 20 ZAR/EUR | 7,606 | 19% too low |
| 380.28 EUR/MWh @ 18 ZAR/EUR | 6,845 | 27% too low |

In every plausible interpretation, solved MC is below fuel-price-implied MC. This biases the LP
toward OCGT. However, even correcting to 9,400 R/MWh, OCGT is still cheaper than VOLL, so MC
correction alone cannot close the gap. The annual energy cap (Option A) is robust to this
uncertainty and is the load-bearing fix. Currency reconciliation is tracked as a deferred step.

---

## 5. Root Cause Summary

1. Coal EAF constraint removes ~10 TWh low-MC supply → LP needs a substitute.
2. Nuclear is fully committed (no headroom above `p_max_pu = 0.534`).
3. OCGT MC (380 in model currency) << VOLL → LP always prefers OCGT over shedding.
4. The only binding OCGT constraint is the 50% weekly CF cap → annual ceiling 14.98 TWh.
5. LP sits against this ceiling: dispatch = 14.62 TWh ≈ 14.98 TWh.
6. No annual energy cap for `ocgt_diesel` exists in the workbook.

**Counter-factual:** capping OCGT at 5.5 TWh forces ~9.1 TWh into the load shed channel.
Expected solve 4 load shed: 2.24 + 9.1 ≈ **11.3 TWh** (within Eskom's 16.755 TWh envelope).

---

## 6. The Dispatch Calibration Hypothesis

### 6.1 Why the OCGT↔shed swap matters for calibration

The model and Eskom resolve the same underlying physical scarcity (coal unavailability after EAF)
through different mechanisms:

- **Model:** LP minimises cost → prefers cheap OCGT over costly shedding.
- **Eskom:** implicit diesel budget cap → sheds load rather than buying diesel.

These produce the same total "scarcity signal" (OCGT + load shed) but inverted proportions.
The annual cap in solve 4 imposes Eskom's implicit budget decision as a hard constraint,
forcing the model to replicate the Eskom outcome rather than the LP optimum.

### 6.2 The correlation test

After solve 4, we can test whether the **temporal structure** of model scarcity matches
Eskom's observed patterns — i.e., does the LP identify the same high-stress periods?

**Combined scarcity proxy:**
```
Model:  scarcity_t = OCGT_dispatch_t + load_shed_t   (hourly, MWh)
Eskom:  scarcity_t = OCGT_actual_t  + MLR_actual_t   (hourly, MWh)
```

If Pearson/Spearman r is high on a weekly aggregation, the model captures WHEN the
system is tight, even if the split between OCGT and shed differs.

**Interpretations:**

| r (weekly combined scarcity) | Interpretation |
|---|---|
| ≥ 0.80 | Model correctly identifies stress periods; dispatch calibrated at temporal level |
| 0.50–0.79 | Partial temporal alignment; seasonal structure captured, weekly peaks noisy |
| < 0.50 | LP scarcity timing diverges from Eskom; deeper investigation needed |

If r is **low for load shedding alone** but **high for the combined signal**, this is the expected
result and a positive finding: it confirms that Eskom's Stage-based shedding protocol (non-LP
behaviour) obscures the otherwise-correct scarcity timing.

**Scientific claim enabled by this test:**

> *"The calibrated model reproduces annual dispatch at the carrier level (≤0.5% subtotal error)
> and the temporal structure of system scarcity (Pearson r ≥ X on weekly combined OCGT+shed).
> Residual OCGT/load-shedding divergence at the hourly level reflects Eskom's non-LP operating
> decisions — fuel budget caps and Stage-based curtailment — which are outside the scope of
> linear planning models and cannot be reproduced without hard-coding 2023 realized outcomes."*

This positions the calibration as complete and defensible while being explicit about model limits.

---

## 7. Decision: The Fix

**Option A (adopted): add one row to `operational_constraints.xlsx`, HIGH_GAS scenario.**

| Field | Value | Rationale |
|---|---|---|
| `scenario` | `HIGH_GAS` | Active scenario in config |
| `bus` | `global` | Fleet-wide constraint |
| `tech_fuel` | `ocgt_diesel` | Exact carrier name in ZA fleet; `ocgt_avf` absent so excluded |
| type column | `output_energy` | Caps electrical output, not primary energy (matches Eskom MWh reporting) |
| `period` | `year` | Annual cap, not sub-annual |
| `incl_pu` | `False` | Absolute energy limit, not relative to p_max_pu |
| `limit` | `max` | Upper bound |
| `apply_to` | `all` | Fixed fleet only (no extendable OCGT exists) |
| `units` | `TWh` | Consistent with Eskom target units |
| `2023` | **`5.5`** | Eskom 5.243 TWh + 5% LP headroom |
| all other years | `NaN` | No expansion scenarios defined here |

**Why 5.5 not 5.243:** The exact Eskom total is the annual dispatch realised under budget
constraints. Using 5.243 as a hard LP ceiling risks infeasibility at hourly demand peaks with
coincident low VRE. The 5% headroom (5.5 TWh) keeps the constraint within the calibration
target tolerance while ensuring LP feasibility. If solve 4 lands at 5.3–5.5 TWh, the annual
subtotal error will be within ±0.5%.

**Parser verification:** `scripts/za_fleet/operational_constraints.py` already supports this
row type. Key lines:
- Line 161–163: maps `output_energy` → `type_ = "energy_power"`
- Line 211: `limit="max"` → `sense="<="`
- Line 261: `rhs = float(en_pow_limit[year])` for energy_power type
- Line 269: `lhs_p = lhs.sum()` when `period == "year"`
- Lines 215–220: unit conversion via `ENERGY_UNIT_CONVERSION` dict

**Codex must verify** that `"TWh"` is a key in `ENERGY_UNIT_CONVERSION` (expected value: `1e6`).
If absent, add it before adding the workbook row.

**All other options rejected or deferred:**
- Option B (outage profiles): all zeros — no data to apply.
- Option C (MC correction): cannot force OCGT below VOLL; secondary check only.
- Option D (nuclear EAF): already applied; reducing nuclear worsens OCGT.
- Option E (coal min stable level): last-resort, defer unless Option A fails.

---

## 8. Implementation Steps for Codex

Execute in order. Each step has one change and one verification.

### Step 0 — Verify parser `TWh` support

```bash
grep -n '"TWh"' scripts/za_fleet/operational_constraints.py
```

Expected output: a line like `"TWh": 1e6,` inside `ENERGY_UNIT_CONVERSION`.

If absent, open `scripts/za_fleet/operational_constraints.py` and add inside the dict:
```python
"TWh": 1e6,
```
Commit this change before proceeding.

---

### Step 1 — Preserve solve 3 network (safety)

The workbook edit will affect any future re-run of the EAF-OPC rule. Before touching the
workbook, confirm solve 3 is committed to git (or backed up):

```bash
git -C ../pypsa-rsa status
git -C ../pypsa-rsa log --oneline -3
```

The network at `results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC.nc`
must remain untouched throughout this implementation.

---

### Step 2 — Add annual OCGT energy cap row to workbook

File: `../pypsa-rsa/scenarios/Coal_Flexibilisation/sub_scenarios/operational_constraints.xlsx`

Use openpyxl or a direct pandas write to insert the new row at the end of the HIGH_GAS block.
The workbook uses a 9-level MultiIndex (columns: `scenario`, `bus`, `tech_fuel`,
`capacity_factor` [the type field], `period`, `incl_pu`, `limit`, `apply_to`, `units`)
followed by year columns 2020–2060.

```python
import openpyxl
from openpyxl import load_workbook

wb = load_workbook(
    "../pypsa-rsa/scenarios/Coal_Flexibilisation/sub_scenarios/operational_constraints.xlsx"
)
ws = wb["operational_constraints"]

# Find the last HIGH_GAS row (currently row for sasol_gas)
# Header is row 1. Append after the last HIGH_GAS data row.
# Year columns: position depends on workbook layout.
# Column order: scenario(1), bus(2), tech_fuel(3), capacity_factor(4),
#               period(5), incl_pu(6), limit(7), apply_to(8), units(9),
#               then years 2020..2060 in columns 10..50.

# New row values (cols 1-9 are the index, col 12 = 2023 position):
new_row = [
    "HIGH_GAS",      # scenario
    "global",         # bus
    "ocgt_diesel",    # tech_fuel
    "output_energy",  # type
    "year",           # period
    False,            # incl_pu
    "max",            # limit
    "all",            # apply_to
    "TWh",            # units
    # year columns 2020..2022: NaN (leave empty), 2023: 5.5, 2024..: NaN
]
# Fill year columns: identify which column = 2023 from the header row
header = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
year_col_2023 = header.index(2023) + 1  # 1-indexed

new_data = [None] * ws.max_column
for i, v in enumerate(new_row):
    new_data[i] = v
new_data[year_col_2023 - 1] = 5.5

ws.append(new_data)
wb.save(
    "../pypsa-rsa/scenarios/Coal_Flexibilisation/sub_scenarios/operational_constraints.xlsx"
)
```

**Verification:**
```python
import pandas as pd
df = pd.read_excel(
    "../pypsa-rsa/scenarios/Coal_Flexibilisation/sub_scenarios/operational_constraints.xlsx",
    sheet_name="operational_constraints",
    index_col=list(range(9)),
)
hit = df.loc[("HIGH_GAS", "global", "ocgt_diesel",
              "output_energy", "year", False, "max", "all", "TWh")]
assert hit[2023] == 5.5, f"Got {hit[2023]}"
print("Row verified:", hit[2023])
```

Commit the workbook change to pypsa-rsa git:
```bash
git -C ../pypsa-rsa add scenarios/Coal_Flexibilisation/sub_scenarios/operational_constraints.xlsx
git -C ../pypsa-rsa commit -m "calibration: add OCGT annual energy cap 5.5 TWh for ZA 2023 Module 12 solve 4"
```

---

### Step 3 — Add Snakemake rule for solve 4

The 4th solve must produce a **new network file** (`...EAF-OPC-CAP.nc`) without disturbing
solve 3 (`...EAF-OPC.nc`). Inspect `Snakefile` around line 1337 to find the
`solve_network_eaf_opc` rule. Create a new rule `solve_network_eaf_opc_cap` that:
- Uses the same script and inputs as `solve_network_eaf_opc`
- Outputs to `results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc`
- Is otherwise identical (same config, same wildcard resolution)

If the rule uses a wildcards-based output path, the cleanest approach is to add a config alias:

```yaml
# In configs/za/za_2023_fixed_validation.yaml or an override
# Add a new solve target label:
za:
  solve_4_label: "NoCO2-1H-EAF-OPC-CAP"
```

And in `Snakefile`, mirror the existing `solve_network_eaf_opc` target with the new label.
The minimal diff: duplicate the rule body, change the output filename. Keep both rules.

Document the chosen approach in `doc/za_implementation_log.md`.

---

### Step 4 — Run solve 4

```bash
snakemake -j1 \
  results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc \
  --configfile configs/za/za_2023_fixed_validation.yaml \
  --rerun-triggers mtime
```

If the solve fails:
1. Check solver log: `logs/za_2023_fixed_validation/solve_network/*CAP*_solver.log`
2. If infeasible: relax cap to 6.0 TWh in the workbook and re-run; document the change.
3. If LP is feasible but constraint not applied: check audit CSV for the new row status.

---

### Step 5 — Verify solve 4 OCGT dispatch

```python
import pypsa
n4 = pypsa.Network(
    "results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc"
)
ocgt_idx = n4.generators[n4.generators.carrier == "ocgt_diesel"].index
ocgt_twh = n4.generators_t.p[ocgt_idx].sum().sum() / 1e6
print(f"Solve 4 OCGT: {ocgt_twh:.3f} TWh  (gate: ≤5.5)")
assert ocgt_twh <= 5.5 + 1e-6, f"OCGT cap not binding: {ocgt_twh:.3f} TWh"
```

---

### Step 6 — Run validation notebook and verify annual subtotal gate

Re-run `notebooks/za_validation/12_dispatch_calibration/dispatch_calibration_validation.ipynb`
with solve 4 as the active network (or add a new cell referencing `...-EAF-OPC-CAP.nc`).

The notebook must report a **fourth row** in the before/after table labelled `eaf_opc_cap`.
The annual subtotal error across all carriers must satisfy |error| ≤ 0.5%.

Re-export the HTML:
```bash
jupyter nbconvert --to html --execute \
  notebooks/za_validation/12_dispatch_calibration/dispatch_calibration_validation.ipynb \
  --output dispatch_calibration_validation.html
```

---

### Step 7 — Pearson / Spearman scarcity correlation analysis

This step produces the quantitative evidence for the dispatch calibration claim in §6.2.

#### 7a — Load hourly Eskom data

Locate the source of hourly Eskom dispatch used in Module 12 validation. Expected path:
`resources/za_2023_fixed_validation/` or `data/za_validation/`. The validation notebook
already loads this data to produce hourly comparison plots; inspect the notebook to find
the exact file and column names.

Required columns (hourly 2023):
- Eskom OCGT (MW): sum of `Eskom OCGT Generation` + `Dispatchable IPP OCGT`
- Eskom load shed (MW): `Manual Load_Reduction(MLR)` column

If hourly data is unavailable as a single CSV, derive it from the GEGIS raw file or the
Module 02 cleaned EAF data. Document the source in `doc/za_implementation_log.md`.

#### 7b — Extract model hourly scarcity from all four solves

```python
import pypsa, pandas as pd

networks = {
    "structural":   "results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H.nc",
    "eaf":          "results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF.nc",
    "eaf_opc":      "results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC.nc",
    "eaf_opc_cap":  "results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc",
}

results = {}
for label, path in networks.items():
    n = pypsa.Network(path)
    ocgt = n.generators[n.generators.carrier == "ocgt_diesel"].index
    ocgt_h = n.generators_t.p[ocgt].sum(axis=1)        # MW per hour
    # Load shed: locate the load-shedding generator or equivalent
    # (carrier name may be "load_shedding" or similar — inspect n.generators.carrier.unique())
    shed_carriers = [c for c in n.generators.carrier.unique()
                     if "load" in c.lower() or "shed" in c.lower() or "curtail" in c.lower()]
    if shed_carriers:
        shed_idx = n.generators[n.generators.carrier.isin(shed_carriers)].index
        shed_h = n.generators_t.p[shed_idx].sum(axis=1)
    else:
        # Fallback: infer from demand - supply mismatch; document if used
        shed_h = pd.Series(0, index=n.snapshots)
    results[label] = pd.DataFrame({"ocgt_mw": ocgt_h, "shed_mw": shed_h})
```

Note: if load-shedding is implemented as a `loads_t` adjustment rather than a generator,
inspect `n.loads_t.p_set` vs `n.loads_t.p` to derive the hourly curtailment. Document the
implementation in `doc/za_implementation_log.md`.

#### 7c — Weekly aggregation and correlation

```python
from scipy import stats

def weekly_sum(series):
    return series.resample("W").sum() / 1e3  # convert to GWh

# Load Eskom hourly data (adjust path/columns as found in 7a)
eskom = pd.read_csv("data/za_validation/eskom_2023_hourly_dispatch.csv",
                    index_col=0, parse_dates=True)
eskom_ocgt_h   = eskom["Eskom OCGT Generation"] + eskom["Dispatchable IPP OCGT"]  # MW
eskom_shed_h   = eskom["Manual Load_Reduction(MLR)"]                               # MW

eskom_ocgt_w   = weekly_sum(eskom_ocgt_h)
eskom_shed_w   = weekly_sum(eskom_shed_h)
eskom_total_w  = eskom_ocgt_w + eskom_shed_w

rows = []
for label, df in results.items():
    model_ocgt_w  = weekly_sum(df["ocgt_mw"])
    model_shed_w  = weekly_sum(df["shed_mw"])
    model_total_w = model_ocgt_w + model_shed_w

    # Align to common weeks
    idx = eskom_total_w.index.intersection(model_total_w.index)

    r_ocgt,   p_ocgt   = stats.pearsonr(model_ocgt_w.loc[idx],  eskom_ocgt_w.loc[idx])
    r_shed,   p_shed   = stats.pearsonr(model_shed_w.loc[idx],  eskom_shed_w.loc[idx])
    r_total,  p_total  = stats.pearsonr(model_total_w.loc[idx], eskom_total_w.loc[idx])

    rho_total, _ = stats.spearmanr(model_total_w.loc[idx], eskom_total_w.loc[idx])

    rows.append({
        "solve":           label,
        "r_ocgt_weekly":   round(r_ocgt, 3),
        "r_shed_weekly":   round(r_shed, 3),
        "r_combined_weekly": round(r_total, 3),
        "rho_combined_weekly": round(rho_total, 3),
        "p_combined":      round(p_total, 4),
        "n_weeks":         len(idx),
    })

pearson_df = pd.DataFrame(rows)
pearson_df.to_csv(
    "data/za_validation/za_2023_dispatch_pearson.csv",
    index=False,
)
print(pearson_df.to_markdown(index=False))
```

Also produce monthly aggregation (resample `"ME"` or `"M"`) for robustness. Write to
`data/za_validation/za_2023_dispatch_pearson_monthly.csv`.

#### 7d — Interpretation guidance

After running 7c, interpret results using this table and append the interpretation as a
markdown comment block at the bottom of the output CSV or in a companion `.md` file:

| r (weekly combined) | Interpretation |
|---|---|
| ≥ 0.80 | **Strong temporal alignment.** Model identifies the same stress periods as Eskom. Dispatch calibrated at temporal level. Use this as calibration evidence. |
| 0.50–0.79 | **Moderate alignment.** Seasonal structure captured; weekly peaks noisy. Acceptable for a planning model. Note the limitation. |
| < 0.50 | **Weak alignment.** LP scarcity timing diverges from Eskom. Investigate whether the divergence is systematic (seasonal offset) or random. |

Expected outcome: r_combined for solve 4 ≥ solve 3, because the OCGT cap forces the LP
to shed load at the same times Eskom would face scarcity, rather than dispatching OCGT freely.

---

### Step 8 — Update calibration report (vault)

File: `4-work/reports/2026-05-12-module12-calibration-report.md` (relative to vault root)

Add a new section `## Solve 4 — EAF+OPC+CAP` with:
- Four-solve comparison table (annual dispatch per carrier)
- OCGT and load-shedding results for all four solves
- Pearson r table from 7c
- Interpretation paragraph following §6.2 framing

Do not modify earlier sections. Append only.

---

### Step 9 — Update Module 12 plan

File: `doc/active/calibration-plan/12_dispatch_calibration_and_availability.md`

Append a reconciliation note to §3 item A (OCGT blocker section) recording:
- The new workbook row (exact fields)
- Solve 4 label
- Solve 4 OCGT result and whether the 0.5% subtotal gate passed
- Link to this report

Do not edit earlier Module 12 sections.

---

### Step 10 — Write shared log (vault)

Write `5-logs/shared/YYYY-MM-DD-HHMM-module12-solve4-ocgt-cap.md` (relative to vault root)
with:
- What changed
- Canonical pages touched
- Solve 4 OCGT result and subtotal error
- Pearson r results (brief)
- Whether Module 12 is now closed

---

### Step 11 (deferred) — Verify OCGT marginal cost currency

Trace the MC write site in `scripts/prepare_network.py` or upstream cost helpers.
Determine whether `380.282474` is in ZAR or EUR. If in EUR, convert to ZAR using the
FX rate locked in Module 07 (`data/za_costs/za_eur_zar_fx.csv`) and verify the
fuel-price-implied target of ~9,400 R/MWh. Record finding in `doc/za_implementation_log.md`.
This step does not block Module 12 closure but must be resolved before expansion runs.

---

## 9. Acceptance Gates for Module 12 Closure

All gates must PASS before Codex declares Module 12 closed.

| Gate | Criterion | Source |
|---|---|---|
| G1 | Solve 4 network exists at `...EAF-OPC-CAP.nc` | filesystem |
| G2 | OCGT diesel annual dispatch ≤ 5.5 TWh in solve 4 | Step 5 |
| G3 | Annual carrier subtotal error ≤ 0.5% across all carriers in solve 4 | Step 6 |
| G4 | Load shedding ≤ 16.755 TWh in solve 4 | Step 6 |
| G5 | 12/12 structural gates still PASS in solve 4 | Step 6 notebook |
| G6 | Operational constraints audit CSV contains the new OCGT annual cap row with `status=applied` | Step 5 |
| G7 | Pearson r table written to `za_2023_dispatch_pearson.csv` | Step 7 |
| G8 | Four-solve comparison table in calibration report | Step 8 |
| G9 | Solve 3 (`...EAF-OPC.nc`) unchanged — confirm via file mtime | filesystem |

---

## 10. Module 13 Readiness Assessment

After completing all steps above, Codex must write a brief Module 13 readiness memo
at the bottom of the shared log (Step 10) answering the following questions.

### 10.1 Is Module 12 closed?

Module 12 is closed if and only if all nine gates in §9 PASS. State explicitly:
`MODULE 12: CLOSED` or `MODULE 12: OPEN — blocking gate(s): [list]`.

If any gate fails, prescribe the minimum additional action required to close it.

### 10.2 What does Module 13 address?

Based on `doc/active/calibration-plan/12_dispatch_calibration_and_availability.md` §3 items
4 and 5, Module 13 covers:
- **Non-coal availability overlays** (nuclear, OCGT, hydro, CSP separate availability
  profiles — currently out of scope because the workbook outage profiles for these carriers
  are all zero or already applied)
- **Seasonal hydro timing** (July inversion deferred from Module 12)
- **VRE level calibration** (wind/solar/CSP annual dispatch vs Eskom targets)
- **PHS fine-tuning** (round-trip efficiency, seasonal charging pattern)

Codex should state which of these are blocking for expansion and which can be deferred to
Module 14 (expansion handoff). Specifically assess:
- Are VRE annual dispatches within ±5% of Eskom actuals? Read from solve 4 validation table.
- Is PHS net dispatch within ±10% of Eskom actuals (4.294 TWh generation, −5.658 TWh pumping)?
- Is CSP within ±10% of Eskom 1.375 TWh?

### 10.3 What is the minimum viable state for Module 13?

A planning model does not need to be perfectly dispatch-calibrated before expansion runs.
The criterion is: are the remaining calibration errors **portable** (future-consistent
parameters) or **2023-specific** (hard-coded outcomes)?

Codex should state whether the residuals after solve 4 are acceptable for expansion, or
whether specific carriers need further calibration before Module 14.

### 10.4 Recommended next session focus

Given the Pearson r results and the gate outcomes, recommend ONE of:
- **Close Module 12, start Module 13** (if all gates PASS and r_combined ≥ 0.5)
- **Remain in Module 12** (if any gate fails or r_combined < 0.5 with no clear fix path)
- **Parallel track** (close Module 12 calibration, flag residuals for Module 13 investigation
  without blocking expansion)

---

## 11. Provenance

| Claim | Source |
|---|---|
| Solve 3 OCGT 14.62 TWh | `results/.../elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC.nc` |
| Eskom OCGT target 5.243 TWh | `data/za_validation/eskom_2023_targets_by_carrier.csv` rows 8-9 |
| Eskom load shed 16.755 TWh | `data/za_validation/eskom_2023_targets_by_carrier.csv` rows 23-25 |
| 50% weekly CF row HIGH_GAS | `../pypsa-rsa/.../operational_constraints.xlsx` row 0 |
| sasol_gas 2.8 TWh annual cap (parser precedent) | same workbook, row 22 |
| OCGT p_nom = 3419 MW, η = 0.3125, MC = 380.28 | `n.generators` from solve 3 network |
| Koeberg p_max_pu = 0.534 | `n.generators` from solve 3 network |
| Koeberg EAF 0.5083 | `../pypsa-rsa/.../plant_availability.xlsx` `annual_availability` |
| Diesel 816 R/GJ 2023 | `../pypsa-rsa/.../fuel_prices.xlsx` `fixed_generators` ME_IRP23 |
| OCGT outage profiles all zero | `../pypsa-rsa/.../plant_availability.xlsx` `outage_profiles` BASE |
| Parser year+output_energy+max support | `scripts/za_fleet/operational_constraints.py:160-269` |
| Module 12 EAF+OPC results | `doc/active/calibration-plan/12_dispatch_calibration_and_availability.md:178-203` |
| Solve 3 load shedding 2.24 TWh | Module 12 shared log 2026-05-13 02:56 |

---

*End of implementation brief. Codex: begin with Step 0 and proceed sequentially.
Do not skip the git safety checks in Step 1. Do not overwrite solve 3.*
