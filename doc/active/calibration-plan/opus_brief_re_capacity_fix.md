# Opus Brief: Fix RE Over-Capacity (Fleet Duplication Bug)

**Date:** 2026-05-12  
**Module context:** Pre-Module-12 fix — must be applied before dispatch calibration begins  
**Working directory:** repo root of `pypsa-earth`

---

## Background

Module 11 smoke builds (July 2023) showed solar and wind dispatching far above Eskom
actuals. Investigation against the Eskom hourly data (which includes `Wind Installed
Capacity` and `PV Installed Capacity` columns) revealed the root cause is a **fleet
construction duplication bug** in `scripts/za_fleet/reconciliation.py`:

| Carrier | Model p_nom | Eskom actual (Jul 2023) | Factor |
|---|---|---|---|
| Wind | 6,890 MW | 3,443 MW | ~2× |
| Solar PV | ~10,033 MW | 2,287 MW | ~4.4× |
| CSP | 500 MW | 500 MW | ✓ correct |

**Why 2× wind:** `build_reconciliation_rows()` emits one row per wind farm from
`pypsa_rsa_fixed_technologies_2023_candidates.csv` (source tag `RSA_FIXED_TECHNOLOGIES`)
AND another row for the same farm from `reipppp_wind_2023_candidates.csv` (source tag
`REIPPPP`). `make_unique_names()` gives the second row a `_2` suffix so both pass into
`custom_powerplants.csv` and from there into the network unchanged.

**Why ~4× solar:** Same duplication of REIPPPP solar plants, plus 4,439 MW of
`Existing distributed solar PV` aggregates (DateIn=2023, source=RSA_FIXED_TECHNOLOGIES).
These distributed PV rows must be removed entirely — they represent rooftop/embedded
generation that reduces Eskom's metered demand at the distribution level. The model
load is `RSA Contracted Demand`, which is already net of embedded solar (confirmed via
the Eskom identity `RSA Contracted Demand ≈ Residual Demand + Total RE`, where
`Total RE` is REIPPPP-contracted grid-connected RE only). Adding them as PyPSA
generators is a double-count.

**Eskom installed capacity is the ground truth:**

```
Wind Installed Capacity  (Jul 2023): 3,442.6 MW  — constant all year
PV Installed Capacity    (Jul 2023): 2,287.1 MW  — constant from Apr onward
CSP Installed Capacity   (Jul 2023):   500.0 MW  ✓
```

REIPPPP wind total (operational): 3,507 MW ≈ Eskom 3,443 MW ✓  
REIPPPP solar PV total (operational): 2,297 MW ≈ Eskom 2,287 MW ✓  
The tiny gaps are within expected rounding/timing tolerance.

---

## Root cause: two loops emit the same physical plants

File: `scripts/za_fleet/reconciliation.py`, function `build_reconciliation_rows()`  
Lines 138–261.

The function has three loops:

1. **Loop 1 — RSA_FIXED_TECHNOLOGIES** (lines 139–193): iterates over all 2023-active
   rows from `pypsa_rsa_fixed_technologies_2023_candidates.csv`. This includes every
   wind and solar PV plant because those appear in the BASE scenario.
   - Wind: maps `rsa_carrier="wind"` → `v1_carrier="onwind"` → emits row
   - Solar PV: maps `rsa_carrier="solar_pv"` → `v1_carrier="solar"` → emits row
   - Solar CSP: maps `rsa_carrier="solar_csp"` → `v1_carrier="csp"` → emits row
   - Distributed solar PV: same `solar_pv` carrier, name contains "Existing distributed solar PV"

2. **Loop 2 — REIPPPP wind** (lines 196–225): emits all 34 wind farms from
   `reipppp_wind_2023_candidates.csv` where `included_2023 == True`. **Same physical
   plants as Loop 1 wind rows.**

3. **Loop 3 — REIPPPP solar PV** (lines 228–261): emits 45 PV plants from
   `reipppp_solar_2023_candidates.csv` where `included_2023 == True` and `Type != CSP`.
   **Same physical plants as Loop 1 solar rows.** CSP is intentionally skipped in Loop 3
   because CSP storage metadata only exists in the RSA source.

`make_unique_names()` (lines 266–282) disambiguates by appending `_2`, `_3`, etc. per
`(canonical_name, carrier)` group. Both rows become distinct names and both survive into
`custom_powerplants.csv`.

No deduplication exists downstream (`build_powerplants.py` uses `custom_powerplants: replace`
mode, `add_electricity.py` does not filter by `projectID`).

---

## The fix: one condition in Loop 1

In `scripts/za_fleet/reconciliation.py`, inside Loop 1 (RSA loop), after the existing
`v1_carrier` lookup and `hydro_import` skip, add:

```python
# Skip onwind and solar — REIPPPP is the authoritative source (loops 2 and 3).
# Keeping RSA rows would duplicate every wind/solar plant (~2× capacity error).
# This also drops the `Existing distributed solar PV` aggregates (4,439 MW,
# DateIn=2023) which must not be PyPSA generators because Eskom's
# RSA Contracted Demand is already net of embedded/distributed generation.
if v1_carrier in ("onwind", "solar"):
    continue
```

Insert this block **after line 142** (the existing `hydro_import` skip):

```python
        v1_carrier = RSA_TO_V1.get(rsa_carrier)
        if v1_carrier is None or v1_carrier == "hydro_import":
            continue
        # ← INSERT HERE
        if v1_carrier in ("onwind", "solar"):
            continue
```

**CSP (`v1_carrier="csp"`) is NOT skipped** — it is the only RE carrier that must stay
in Loop 1 because Loop 3 already skips CSP (`rtype == "CSP": continue`).

---

## Expected capacity after fix

| Carrier | Before fix | After fix | Eskom actual | Delta |
|---|---|---|---|---|
| onwind | 6,890 MW | **3,507 MW** | 3,443 MW | +2% (within tolerance) |
| solar PV | ~10,033 MW | **~2,297 MW** | 2,287 MW | +0.4% ✓ |
| csp | 500 MW | 500 MW | 500 MW | ✓ |
| coal/nuclear/OCGT/hydro/PHS | unchanged | unchanged | — | — |

Note: Loeriesfontein Orange (75 MW, COD=2023/12/31) is in REIPPPP with
`included_2023=True`. It stays in the model. Its December commissioning means it
contributes effectively zero annual generation — negligible for calibration.

---

## Pipeline rebuild

The change propagates through the full Snakemake DAG from `custom_powerplants.csv`
onward. Rebuild sequence (Snakemake handles order automatically):

```bash
# Step 1 — regenerate fleet
snakemake --rerun-triggers mtime \
    data/custom_powerplants.csv \
    data/za_audit/za_powerplant_reconciliation.csv \
    -j1 --configfile configs/za/za_2023_fixed_validation.yaml

# Step 2 — rebuild network through clustering
snakemake --rerun-triggers mtime \
    networks/za_2023_fixed_validation/elec_s_34.nc \
    -j4 --configfile configs/za/za_2023_fixed_validation.yaml

# Step 3 — ZA hooks re-apply automatically via Snakemake markers
#   (apply_za_custom_lines → Module 09b corridors)
#   (apply_za_local_carriers → Module 11 carriers, cost patches, CSP retag)

# Step 4 — prepare and solve Stage 1 + Stage 2 smoke
snakemake --rerun-triggers mtime \
    results/za_2023_fixed_validation/networks/elec_s_34_ec_lcopt_Co2L-1H.nc \
    -j4 --configfile configs/za/za_2023_fixed_validation.yaml
```

Or in one shot:
```bash
snakemake --rerun-triggers mtime \
    results/za_2023_fixed_validation/networks/elec_s_34_ec_lcopt_Co2L-1H.nc \
    -j4 --configfile configs/za/za_2023_fixed_validation.yaml
```

### Intermediate files that regenerate automatically

| File | Rebuilt by rule |
|---|---|
| `data/custom_powerplants.csv` | `build_za_fleet_reconciliation` |
| `data/za_audit/za_powerplant_reconciliation.csv` | `build_za_fleet_reconciliation` |
| `resources/za_2023_fixed_validation/powerplants.csv` | `build_powerplants` |
| `networks/za_2023_fixed_validation/elec.nc` | `add_electricity` |
| `networks/za_2023_fixed_validation/elec_s_34.nc` | `cluster_network` |
| `data/za_audit/za_ppm_vs_rsa_fleet_comparison.csv` | `build_za_earth_rsa_diagnostic` |

### ZA hook interaction

`apply_za_local_carriers.py` calls `retag_csp_from_solar()`, which reads
`custom_powerplants.csv` for rows with `Fueltype=Solar AND Technology=CSP`.
After the fix, CSP plants still come from RSA_FIXED_TECHNOLOGIES (`v1_carrier="csp"`,
not skipped) and still have `Fueltype=Solar, Technology=CSP` in the output. The CSP
retag step continues to work unchanged.

---

## Verification

### 1. Check custom_powerplants.csv totals

```python
import pandas as pd
ppm = pd.read_csv("data/custom_powerplants.csv")

print("=== Capacity by Fueltype ===")
print(ppm.groupby("Fueltype")["Capacity"].sum().sort_values(ascending=False))
# Expected:
#   Hard Coal  ~40,696 MW
#   Wind        ~3,507 MW   ← was 6,890
#   Solar (PV)  ~2,297 MW   ← was ~10,533 (incl. distributed + CSP)
#   Solar (CSP)   500 MW    ← unchanged (via Technology=CSP column)

print("\n=== No _2 duplicates for wind or solar PV ===")
wind_dups = ppm[(ppm["Fueltype"]=="Wind") & ppm["Name"].str.endswith("_2")]
solar_dups = ppm[(ppm["Fueltype"]=="Solar") & ppm["Name"].str.endswith("_2") & (ppm["Technology"]=="PV")]
print(f"Wind _2 rows: {len(wind_dups)}")   # Must be 0
print(f"Solar PV _2 rows: {len(solar_dups)}")  # Must be 0

print("\n=== No distributed PV rows ===")
dist = ppm[ppm["Name"].str.contains("distributed solar", case=False, na=False)]
print(f"Distributed PV rows: {len(dist)}")  # Must be 0

print("\n=== CSP intact ===")
csp = ppm[(ppm["Fueltype"]=="Solar") & (ppm["Technology"]=="CSP")]
print(f"CSP capacity: {csp['Capacity'].sum():.0f} MW")  # Must be ~500
```

### 2. Check network generator totals after rebuild

```python
import pypsa
n = pypsa.Network("networks/za_2023_fixed_validation/elec_s_34.nc")
print(n.generators.groupby("carrier")["p_nom"].sum().sort_values(ascending=False))
# Expected:
#   coal     ~40,696 MW
#   onwind    ~3,507 MW   ← was ~6,981
#   solar     ~2,297 MW   ← was ~10,033
#   csp         500 MW    ✓
#   nuclear   1,854 MW    ✓
```

### 3. Stage 2 smoke (July 2023) dispatch comparison

After re-solve, compare against Eskom July 2023 actuals:

| Carrier | Eskom actual | Pre-fix model | Post-fix target |
|---|---|---|---|
| Wind | 1,040 GWh | ~1,346 GWh | ~1,040–1,100 GWh |
| Solar PV | 325 GWh | ~1,133 GWh | ~300–370 GWh |
| CSP | 42 GWh | ~155 GWh (over) | ~42–80 GWh |
| Coal | 14,769 GWh | ~13,700 GWh | ↑ toward 14,769 GWh |
| OCGT diesel | 528 GWh | ~2,544 GWh | ↓ (coal EAF still needed) |
| Load shedding | ~1,491 GWh proxy | 6 GWh | ↑ (coal EAF fix needed for full effect) |

Note: OCGT over-dispatch and load shedding will only fully correct after both
this fix AND the coal EAF constraint (Module 12 Issue 2) are applied together.

---

## Files to modify

| File | Change |
|---|---|
| `scripts/za_fleet/reconciliation.py` | Add `if v1_carrier in ("onwind", "solar"): continue` in Loop 1 (RSA) |

All other files regenerate automatically through Snakemake.

---

## What NOT to change

- `reipppp_wind_2023_candidates.csv` — source of truth for wind fleet, keep as-is
- `reipppp_solar_2023_candidates.csv` — source of truth for PV fleet, keep as-is
- `apply_za_local_carriers.py` — CSP retag logic unaffected
- Cost overrides in `za_local_carrier_cost_rows.csv` — unaffected
- `za_2023_fixed_validation.yaml` config — no change needed

---

## After this fix: what's still needed for Module 12

1. ✅ Merit order: coal 40.56, nuclear 16.39 EUR/MWh (done in Module 11)
2. ✅ RE capacity: wind ~3,507 MW, solar ~2,297 MW ← **this fix**
3. ⬜ Coal EAF (~55%): apply monthly `p_max_pu` from Eskom 2023 data
4. ⬜ Nuclear p_max_pu=0.534: verify source (pypsa-rsa `plant_availability.xlsx` or Eskom AR)
5. ⬜ PHS/hydro zero dispatch: inspect storage unit config
6. ⬜ Uncalibrated baseline solve (build before applying Module 12 constraints)
