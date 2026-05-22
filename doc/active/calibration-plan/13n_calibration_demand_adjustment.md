# Module 13n — Calibration Demand Adjustment

**Status:** Implemented 2026-05-18 — solved with validation caveat  
**Depends on:** Module 13m accepted baseline network (already on disk — do not delete)  
**Blocking:** Nothing — Module 14 VRE scaling remains the next calibration step  

---

## What this module does

The model currently uses RSA Contracted Demand as its load input. For calibration
this is wrong: RSA Contracted Demand includes generation sources the model does not
represent, so the optimizer compensates with OCGT over-dispatch and excess load
shedding — not because the generators are inaccurate, but because the demand target
includes energy the model was never given the means to produce.

This module produces a corrected demand CSV that strips out the three unmodelled
sources. Switching to it requires one line in the run config. No PyPSA-Earth
workflow code is modified.

For **capacity expansion** runs (2030–2050), demand comes from GEGNIS projections
via a separate config path and is unaffected by this module.

---

## The three unmodelled sources removed

| Source | CY2023 annual | Column(s) in `eskom_2023_hourly_clean.csv` |
|---|---|---|
| Net imports (Imports − Exports) | −408 GWh | `International Imports`, `International Exports` |
| Other RE (biomass, small hydro, RoR) | +238 GWh | `Other RE` |
| Unattributed dispatchable residual | +5,144 GWh | `Dispatchable Generation` minus all named subcategories (see formula) |

**Net demand reduction: −4,974 GWh (−2.2%). Calibration demand: 220,901 GWh.**  
Minimum hourly value: +17,511 MW (no negative values — adjustment is
physically coherent throughout CY2023).

The unattributed residual is **not a modellable generator** — its hourly
profile is negative for 27% of the year (min −2,528 MW). It is likely GT
(gas turbine) stations and non-dispatchable conventional IPPs that appear in
Eskom's aggregate `Dispatchable Generation` column but have no named subcategory
column. Subtracting it from demand is the correct treatment.

---

## Implementation — demand file and config

### Step 1 — produce the calibrated demand CSV

Create `scripts/build_za_calibration_demand.py` with the following content
and run it once from the repo root:

```python
"""Produce the Module 13n calibration-adjusted Africa.csv demand file.

Reads:  data/za_validation/eskom_2023_hourly_clean.csv
Writes: data/ssp2-2.6/2030/era5_2023_calibrated/Africa.csv

See doc/active/calibration-plan/13n_calibration_demand_adjustment.md.
Run once: python scripts/build_za_calibration_demand.py
"""
from pathlib import Path
import pandas as pd

ESKOM_HOURLY = Path("data/za_validation/eskom_2023_hourly_clean.csv")
OUTPUT       = Path("data/ssp2-2.6/2030/era5_2023_calibrated/Africa.csv")

df = pd.read_csv(ESKOM_HOURLY, index_col=0, parse_dates=True)

unattributed = (
    df["Dispatchable Generation"]
    - df["Thermal Generation"]
    - df["Nuclear Generation"]
    - df["Eskom Gas Generation"]
    - df["Eskom OCGT Generation"]
    - df["Hydro Water Generation"]
    - df["Pumped Water Generation"]
    - df["Dispatchable IPP OCGT"]
)

demand = (
    df["RSA Contracted Demand"]
    - df["International Imports"]
    + df["International Exports"]
    - df["Other RE"]
    - unattributed
)

assert demand.min() > 0, f"Negative demand: min={demand.min():.1f} MW"
annual_gwh = demand.sum() / 1e3
assert abs(annual_gwh - 220901) < 2, f"Annual total off: {annual_gwh:.0f} GWh"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
out = pd.DataFrame({
    "region_code":        "ZA",
    "time":               df.index.strftime("%Y-%m-%d %H:%M:%S"),
    "region_name":        "South Africa",
    "Electricity demand": demand.values,
})
out.to_csv(OUTPUT, index=False, sep=";", float_format="%.9f")
print(f"Written: {OUTPUT}  ({annual_gwh:,.0f} GWh)")
```

**Run:**
```bash
python scripts/build_za_calibration_demand.py
```

**Expected output:**
```
Written: data/ssp2-2.6/2030/era5_2023_calibrated/Africa.csv  (220,901 GWh)
```

---

### Step 2 — change one line in the run config

File: `configs/za/za_2023_fixed_validation.yaml`

Find the existing line:
```yaml
  weather_year: 2023_custom
```

Change it to:
```yaml
  weather_year: 2023_calibrated
```

PyPSA-Earth constructs the demand path as
`data/{ssp}/{prediction_year}/era5_{weather_year}/Africa.csv`, which
now resolves to the calibrated file. No other config changes.

---

## Network to solve

Re-solve **one network only**:

```
results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-UC-OPC-LOW-GAS-OFFICIAL-FLEET.nc
```

This is the Module 13m accepted baseline (LOW-GAS, official Eskom 2023 coal
fleet, no Sasol, no OCGT cap). It already exists on disk from Module 13m.
After the `weather_year` config change it must be rebuilt with the new demand.
Do **not** rely on Snakemake detecting the config-only path change from
timestamps alone; force `build_demand_profiles` so
`resources/za_2023_fixed_validation/demand_profiles.csv` cannot remain stale.

**Before re-solving, copy the existing Module 13m baseline** so it is
preserved for before/after comparison:

```bash
cp results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-UC-OPC-LOW-GAS-OFFICIAL-FLEET.nc \
   results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-UC-OPC-LOW-GAS-OFFICIAL-FLEET-PRE-13N.nc
```

**Preferred solve command** (run from repo root with the `pypsa-earth` conda env):

```bash
snakemake \
  --configfile configs/za/za_2023_fixed_validation.yaml \
  --forcerun build_demand_profiles \
  results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-UC-OPC-LOW-GAS-OFFICIAL-FLEET.nc \
  --cores 20 --rerun-incomplete
```

Always include the ZA configfile; otherwise the default config is loaded and
`pypsa_rsa_root` is missing. The forced `build_demand_profiles` rerun makes the
weather-year path switch explicit.

In the current Snakefile, the labelled `...LOW-GAS-OFFICIAL-FLEET.nc` target is
buildable only through the generic `prepare_network`/`solve_network` wildcard
path. The correct Module 13i rule is therefore the unlabelled LOW-GAS target:

```bash
snakemake \
  --configfile configs/za/za_2023_fixed_validation.yaml \
  --forcerun build_demand_profiles \
  results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-UC-OPC-LOW-GAS.nc \
  --cores 20 --rerun-incomplete
```

Before copying that result to the `...OFFICIAL-FLEET.nc` filename, verify that
`configs/za/za_2023_fixed_validation.yaml` has:

```yaml
za_2023_fleet_calibration:
  coal_fleet:
    mode: calibrated_2023
```

Only then is the `OFFICIAL-FLEET` label truthful, because `calibrated_2023`
aliases the Eskom nominal 2023 fleet.

**Implemented command refinement (2026-05-18):** the full Snakemake DAG tried to
rebuild missing upstream bundle files (`profile_onwind.nc` and raw bundle
inputs). To avoid unrelated data retrieval, implementation used:

1. forced `build_demand_profiles` with `--allowed-rules build_demand_profiles`;
2. a backed-up EAF input network, patched by row-wise scaling its 34 load series
   from old national demand to calibrated national demand;
3. forced `solve_network_eaf_opc` with `--allowed-rules solve_network_eaf_opc`;
4. verified `coal_fleet.mode: calibrated_2023`;
5. copied the unlabelled solved network to the labelled
   `...LOW-GAS-OFFICIAL-FLEET.nc` path consumed by notebooks.

Additional preserved input backup:

```text
networks/za_2023_fixed_validation/elec_s_34_ec_lc1_NoCO2-1H-EAF-PRE-13N.nc
```

**Observed solve outcome:** status `ok / optimal`; network load `220,901.625`
GWh; coal `163,923.987` GWh; OCGT diesel `14,861.508` GWh; load shedding
`20,752.747` GWh. Load shedding is materially lower than the pre-13n value of
`25,722` GWh.

---

## Notebooks to re-execute after the solve

Re-execute both notebooks using the `pypsa-earth` kernel. They read the
network by its fixed path and will automatically pick up the new solve.

### Notebook 1 — energy balance validity

```
notebooks/za_validation/13_energy_balance_validity/energy_balance_validity.ipynb
```

```bash
jupyter nbconvert --to notebook --execute --inplace \
  --ExecutePreprocessor.kernel_name=pypsa-earth \
  --ExecutePreprocessor.timeout=300 \
  notebooks/za_validation/13_energy_balance_validity/energy_balance_validity.ipynb
```

**What to check in the output:**
- `demand_boundary_residual` in Section 3 should be checked explicitly. The
  2026-05-18 run reports `-2,726` GWh, not the planned near-zero value, because
  the existing notebook still treats the unattributed dispatchable residual as a
  missing supply source in its gap decomposition.
- Load shedding error in the scorecard should drop from +54% toward
  the range expected after Module 14 VRE scaling
- Coal annual volume and Pearson r should be essentially unchanged
- Energy balance should still close

### Notebook 2 — dispatch calibration

```
notebooks/za_validation/12_dispatch_calibration/dispatch_calibration_validation.ipynb
```

```bash
jupyter nbconvert --to notebook --execute --inplace \
  --ExecutePreprocessor.kernel_name=pypsa-earth \
  --ExecutePreprocessor.timeout=600 \
  notebooks/za_validation/12_dispatch_calibration/dispatch_calibration_validation.ipynb
```

**What to check:**
- The `LOW-GAS-OFFICIAL-FLEET` row in the dispatch summary table now reflects
  the calibrated-demand solve (lower OCGT and load shedding than Module 13m)
- Other scenario rows are unaffected (they read different network files)
- No error cells

---

## Validation checks

| Check | Expected | How to verify |
|---|---|---|
| Calibrated CSV exists | `data/ssp2-2.6/2030/era5_2023_calibrated/Africa.csv` | `ls` |
| CSV annual total | 220,901 GWh ± 2 GWh | Script assertion |
| CSV minimum value | ≥ 17,500 MW | Script assertion |
| Solve status | `ok / optimal` | Solver log |
| Network load annual sum | ≈ 220,901 GWh | PyPSA `n.loads_t.p_set.sum().sum() / 1e3` |
| Notebooks execute | 0 error cells | nbconvert output |

2026-05-18 validation: both notebooks executed with 0 error outputs. The energy
balance notebook reported a `-2.7 TWh` residual caveat; dispatch notebook picked
up the calibrated official-fleet network.

---

## What does NOT need to change

- No PyPSA-Earth workflow scripts
- No Snakefile rules
- No other config keys
- No validation notebook source logic (they auto-load the network by path; the
  notebooks were re-executed in place)

---

## Reverting to baseline

To restore the pre-13n state:

```bash
# restore config
# change weather_year back to: 2023_custom

# restore network (if needed for comparison)
cp results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-UC-OPC-LOW-GAS-OFFICIAL-FLEET-PRE-13N.nc \
   results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-UC-OPC-LOW-GAS-OFFICIAL-FLEET.nc
```

---

## Thesis / paper justification

> *"For calibration against CY2023 Eskom operational data, the hourly demand
> profile is adjusted to represent only the generation sources present in the
> model. Three terms are subtracted from RSA Contracted Demand at each hour:
> (i) international net imports (Imports − Exports; annual net = −408 GWh),
> reflecting the model's single-country system boundary with no cross-border
> transmission links; (ii) Other Renewables generation (238 GWh), a category
> comprising biomass, small hydro, and run-of-river IPPs not represented in
> the network; and (iii) a 5,144 GWh unattributed dispatchable residual — the
> difference between Eskom's aggregate Dispatchable Generation column and the
> sum of all named subcategory columns in the hourly CSV, consistent with
> generation from plant types (gas turbines and non-dispatchable conventional
> IPPs) not individually tracked in the Eskom Data Portal. The resulting
> calibration demand is 220,901 GWh (−2.2% of RSA Contracted Demand; minimum
> hourly value +17,511 MW). This adjustment ensures that residual load shedding
> in the model reflects dispatch accuracy rather than data coverage gaps. An
> unexplained −853 GWh annual residual persists in the Eskom hourly energy
> balance after this adjustment; its origin is not confirmed and it is not
> corrected. Capacity expansion scenarios use independently projected demand
> and are not affected by this calibration adjustment."*
