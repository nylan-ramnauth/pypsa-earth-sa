# Pre-Module 12 — Hydro and Biomass Investigation

**Date:** 2026-05-12  
**Author:** Sonnet (investigation), to be actioned by Opus (Module 12)  
**Status:** Findings complete — decision and implementation deferred to Module 12

---

## Summary

Two carrier groups appeared absent from the solved network during Module 11 notebook analysis.
Investigation shows the situations are entirely different:

| Issue | Reality | Action required |
|---|---|---|
| "No hydro" | Hydro IS in network as StorageUnits; notebook plot only reads generators | Fix notebook plotting function |
| "No biomass" | Biomass plants excluded by config — root cause confirmed | Decision required (see §2) |

---

## 1. Hydro — StorageUnit versus Generator confusion

### 1.1 What is in the network

PyPSA-Earth treats `Technology=Reservoir` hydro plants as **StorageUnits with inflow**, not
Generators. This is correct behaviour (`add_electricity.py: attach_hydro`, line 1048).

The solved network `elec_s_34_ec.nc` contains five hydro StorageUnits:

| StorageUnit name | Carrier | p_nom (MW) | Max hours | Source plants |
|---|---|---|---|---|
| Hydra Central hydro | hydro | 600.00 | 3 366 | Gariep 360 MW + Vanderkloof 240 MW |
| Mthatha hydro | hydro | 65.00 | 3 366 | ColleyWobbles |
| Highveld South hydro | hydro | 4.22 | 3 366 | Stortemelk |
| Ladysmith hydro | hydro | 3.80 | 3 366 | Kruisvallei |
| Namaqualand hydro | hydro | 10.00 | 3 366 | Neusberg |
| **Total** | | **683.02 MW** | | |

All five are present in `profile_hydro.nc` (confirmed: plant indices [34,35,48,49,50,51] match).
No hydro plants were dropped for missing inflow data.

PHS (Drakensberg 1000 MW, Ingula 1324 MW, Palmiet 400 MW, Steenbras 180 MW) is also present
as StorageUnits with carrier `PHS` — these were already confirmed dispatching correctly.

### 1.2 Confirmed dispatch (earlier CO2-capped full-year diagnostic solve)

Hydro StorageUnit dispatch from the earlier `elec_s_34_ec_lcopt_Co2L-1H.nc`
diagnostic solve, July 2023:

| StorageUnit | July dispatch (MWh) |
|---|---|
| Hydra Central hydro | 90 286 |
| Mthatha hydro | 6 139 |
| Ladysmith hydro | 2 827 |
| Highveld South hydro | 2 885 |
| Namaqualand hydro | 804 |
| **Total July** | **~103 000 MWh = 103 GWh** |

Eskom reference: `Hydro Water Generation` column (glossary: conventional hydro, NOT PHS).
Opus must verify the July 2023 Eskom value from `data/za_audit/eskom_hourly_2023.csv` and
assess the quantitative match.

### 1.3 Root cause of "no hydro" observation

The Module 11 notebook function `model_carrier_mw(net, carriers)` reads:

```python
gens = net.generators[net.generators.carrier.isin(carriers)].index
return net.generators_t.p[gens].sum(axis=1)
```

Hydro reservoir plants are **StorageUnits**, not Generators → `net.generators_t.p` returns no
hydro rows → plot shows 0. This is a **notebook plotting bug**, not a network bug.

Similarly, `model_storage_mw(net, discharge_only=True)` sums ALL storage units (PHS + hydro +
battery) without carrier filtering, so the PHS panel also inadvertently includes hydro.

### 1.4 Actions for Module 12 (Opus)

**Required fixes in `module12_readiness_report.ipynb`:**

1. Replace the hydro generator lookup with StorageUnit discharge:

```python
def model_hydro_mw(net):
    su_hydro = net.storage_units[net.storage_units.carrier == 'hydro'].index
    if su_hydro.empty or net.storage_units_t.p.empty:
        return pd.Series(0.0, index=net.snapshots)
    return net.storage_units_t.p[su_hydro].sum(axis=1).clip(lower=0)
```

2. Fix the PHS panel to filter by carrier, not sum all storage:

```python
def model_phs_mw(net):
    su_phs = net.storage_units[net.storage_units.carrier == 'PHS'].index
    if su_phs.empty or net.storage_units_t.p.empty:
        return pd.Series(0.0, index=net.snapshots)
    return net.storage_units_t.p[su_phs].sum(axis=1).clip(lower=0)
```

3. Use these functions in the `panels` loop for the hydro and PHS carriers.

**Quantitative investigation (Opus decides):**

- Compare 103 GWh/July model vs Eskom `Hydro Water Generation` July 2023.
- Check `max_hours = 3 366` — this is `IRENA ZA total annual hydro energy (TWh) / total p_nom (GW)`,
  normalized across all plants at each bus. Very high value implies IRENA assigns ZA large
  annual hydro energy relative to the ~683 MW installed. Verify against:
  - IRENA 2023 ZA hydro generation (likely 3–4 TWh/yr)
  - `data/hydro_capacities.csv` ZA row
  - Eskom Orange River system annual generation
- If model hydro dispatch is significantly over/under, a multiplier adjustment in the hydro
  config or a manual `p_max_pu` override may be needed for the calibrated baseline.

---

## 2. Biomass — excluded by missing carrier in config

### 2.1 What is in powerplants.csv

Three Bioenergy plants reach `resources/za_2023_fixed_validation/powerplants.csv`:

| Index | Plant | Fueltype | Capacity (MW) | Bus (pre-cluster) | Notes |
|---|---|---|---|---|---|
| 52 | ENERGY Joburg Landfill Gas | Bioenergy | 7.56 | 0 | Landfill gas to electricity |
| 53 | Ngodwana Energy | Bioenergy | 25.00 | 135 | Wood-chip bioenergy IPP |
| 54 | Sappi | Bioenergy | 144.00 | 628 | Pulp mill co-gen |

Mondi (120 MW, from `za_powerplant_reconciliation.csv`) does **not** appear in powerplants.csv —
it has no lat/lon and is dropped by `build_powerplants` before bus assignment.

None appear in the solved network. Zero biomass generators or storage units exist.

### 2.2 Root cause: two compounding bugs

**Bug 1 — Not in `conventional_carriers`:**  
`za_2023_fixed_validation.yaml` sets:
```yaml
electricity:
  conventional_carriers: [coal, nuclear]
```
`attach_conventional_generators` filters: `ppl.query("carrier in @carriers")` where
`carriers = {coal, nuclear}`. Biomass plants (any carrier value) are excluded.

**Bug 2 — Case-sensitive carrier mapping:**  
`add_electricity.py` line 142 maps `"bioenergy" → "biomass"` (lowercase key).  
`powerplants.csv` Fueltype column value: `"Bioenergy"` (capital B).  
After `.rename(columns=str.lower)` renames column names (not values), and `.powerplant.to_pypsa_names()`
normalises PPM fuel names, the carrier column value for these plants becomes `"Bioenergy"`.  
The replacement `{"carrier": {"bioenergy": "biomass"}}` does NOT match `"Bioenergy"` (capital B).  
Result: carrier stays `"Bioenergy"` — further excluded even if Bug 1 were fixed.

Bug 1 is the dominant gate; Bug 2 is secondary but must also be fixed if biomass is to be included.

### 2.3 What `other_re` actually is — and why it is unsuitable for expansion

`apply_za_local_carriers.py` adds an exogenous `other_re` generator that replays Eskom's
`Other RE` hourly column as a fixed p_max_pu profile. Confirmed numbers from
`data/za_validation/eskom_2023_hourly_clean.csv` and the solved network:

| Metric | Value |
|---|---|
| Installed capacity (constant, from Eskom) | **50.58 MW** |
| Annual generation 2023 | **238 GWh** |
| July 2023 generation | **27 GWh** |
| Mean dispatch | 27.1 MW (54% of 50.58 MW) |
| Range | 1.3 – 44.2 MW |
| Share of total RSA demand | **0.105%** |
| Seasonal pattern | Peaks Jun–Aug (26–27 GWh/month), troughs Sep–Dec (9–11 GWh/month) |

The seasonal winter peak is consistent with small run-of-river hydro in the Western Cape
winter rainfall zone, not biomass (which would be flatter). This suggests `Other RE` is
dominated by small hydro and landfill gas, not the large biomass plants in `powerplants.csv`.

**What Eskom aggregates into this column:**

| Source | Likely MW | Notes |
|---|---|---|
| Landfill gas (Joburg, Durban municipal) | ~10–15 MW | IPP, Eskom-contracted |
| Small biomass/biogas IPPs | ~10–15 MW | Ngodwana-class |
| Small run-of-river hydro (<10 MW) | ~10–20 MW | Not separately metered |
| Bagasse/biomass co-gen selling surplus | ~5–10 MW | Sugar/pulp mills with grid connection |

**What is NOT in `Other RE`:**
- Sappi (144 MW) — captive pulp-mill co-gen, not dispatched by Eskom National Control
- Mondi (120 MW) — same; captive industrial
- Sasol coal/gas — separate captive industrial (already flagged for removal)

**The expansion incompatibility problem:**

The `other_re` generator is an exogenous accounting artefact. It has:
- Fixed `p_nom = 50.58 MW` (not expandable, not a real technology cost curve)
- Profile locked to Eskom's 2023 historical data
- No technology identity (mixed landfill gas + small hydro + biogas combined)
- No capital cost or efficiency — cannot participate in expansion optimization

For the V1 fixed-capacity calibration this is tolerable. But the project objective is to
hand off a calibrated network to Module 14 (capacity expansion). Carrying this artefact
forward would inject 238 GWh/yr of generation with zero cost and no real expansion pathway —
the optimizer could not decide whether to build more of it, retire it, or replace it.

The correct long-term treatment: replace with explicit technology rows (small hydro,
landfill gas, biomass) with real cost data and expansion potential. For the 2023 baseline,
the 0.105% supply gap from removing it is negligible.

### 2.4 Plant classification — double-count risk resolved

| Plant | MW | Likely inside Eskom `Other RE`? | Expansion-eligible? | Decision |
|---|---|---|---|---|
| Joburg Landfill Gas | 7.56 | Yes — small IPP, Eskom-contracted | No (finite resource) | Exclude |
| Ngodwana Energy | 25.00 | Yes — REIPPPP bioenergy, aggregated | Marginally | Exclude; already in other_re |
| Sappi | 144.00 | No — captive industrial | No (like Sasol) | Exclude (Sasol logic) |
| Mondi | 120.00 | No — captive industrial, no lat/lon | No | Exclude (dropped by build_powerplants already) |

### 2.5 Options for Opus

**Option A — Remove `other_re` artefact entirely (recommended)**

Remove the `other_re` generator from `apply_za_local_carriers.py`. Accept the 238 GWh/yr
supply gap (0.105% of demand). Do not add explicit biomass generators.

Rationale:
- The artefact is expansion-incompatible; removing it now avoids patching it later.
- 0.105% supply gap is within calibration noise — coal or OCGT fills it marginally.
- All biomass plants in `powerplants.csv` are either already inside `other_re` (double-count
  if added) or captive industrial (Sasol-class, exclude for same reasons).
- Clean separation: Eskom's `Other RE` generation is not modelled — it is flagged as a known
  omission in the Module 13 report with a quantified upper bound (238 GWh/yr, 27 GWh July).

Implementation: comment out or remove the `attach_other_re` call in `apply_za_local_carriers.py`.
No rebuild of fleet or powerplants required — only the hook changes.

**Option B — Keep `other_re` for V1 calibration, remove before Module 14**

Keep the exogenous generator through Module 13 to maintain supply balance accuracy.
Document removal as a pre-Module 14 task.

Pros: supply-demand balance exactly matches Eskom totals in V1.  
Cons: defers the artefact problem; risks it being inherited by the expansion model.

**Option C — Replace with explicit small-hydro and landfill-gas rows**

Add 2–3 small explicit generators (small hydro 15 MW, landfill gas 10 MW, biogas 5 MW)
with real cost data and expansion potential. Remove the exogenous artefact.

Pros: expansion-compatible fleet from the start.  
Cons: requires cost data sourcing and validation; overkill for V1 calibration.

### 2.6 Recommendation

**Option A — remove `other_re` now.** Rationale:
- 0.105% supply gap is calibration-negligible (27 GWh/July vs ~16,000 GWh system).
- Expansion incompatibility is a structural problem that compounds if left. Better to remove
  the artefact cleanly in V1 than to patch it before Module 14.
- Option C (explicit small generators) is the right long-run answer but requires data not
  yet in scope for Module 12.
- Flag 238 GWh/yr as known omission in Module 13 report. Assign a Module 14 task:
  add small hydro (~15 MW), landfill gas (~10 MW), biogas (~5 MW) as expansion candidates
  with REIPPPP cost data.

---

## 3. Required notebook fix (both issues)

The per-carrier panel loop in `module12_readiness_report.ipynb` (cell `284459e0`) currently uses
`model_carrier_mw(net, carriers)` for the hydro panel. This must be replaced with a StorageUnit
query. The PHS panel must also be fixed to filter by carrier rather than summing all storage units.

Minimum diff:

```python
# in the panels loop, replace the call for key == 'hydro' and key == 'phs':

if key == 'hydro':
    su_idx = n_demo.storage_units[n_demo.storage_units.carrier == 'hydro'].index
    model_mw = (n_demo.storage_units_t.p[su_idx].sum(axis=1).clip(lower=0)
                if not su_idx.empty and not n_demo.storage_units_t.p.empty
                else pd.Series(0.0, index=n_demo.snapshots))
elif key == 'phs':
    su_idx = n_demo.storage_units[n_demo.storage_units.carrier == 'PHS'].index
    model_mw = (n_demo.storage_units_t.p[su_idx].sum(axis=1).clip(lower=0)
                if not su_idx.empty and not n_demo.storage_units_t.p.empty
                else pd.Series(0.0, index=n_demo.snapshots))
else:
    model_mw = model_carrier_mw(n_demo, carrier_map[key])
```

Note: the demo solve uses `crossover: 0` (barrier-only), so the StorageUnit dispatch pattern
may still look flat or sub-optimal. Module 12 calibration evidence should use the canonical
`NoCO2-1H` structural baseline and EAF-calibrated outputs.

---

## 4. Checklist for Module 12 implementation

### Hydro
- [ ] Fix notebook: replace generator lookup with StorageUnit lookup for hydro and PHS panels
- [ ] Verify Eskom `Hydro Water Generation` July 2023 and compute model vs Eskom error
- [ ] Verify `max_hours = 3366` against IRENA ZA hydro total and `data/hydro_capacities.csv`
- [ ] If dispatch gap > 30%: investigate IRENA normalization multiplier in `renewable.hydro` config

### Biomass and `other_re` artefact
- [ ] Decision: Option A (remove `other_re`, exclude all biomass) confirmed or overridden
- [ ] If Option A (recommended):
  - [ ] Remove `attach_other_re` call in `apply_za_local_carriers.py` (or comment out)
  - [ ] No fleet rebuild needed — hook-only change, re-run from `add_extra_components` stage
  - [ ] Flag 238 GWh/yr omission in Module 13 validation report with quantified impact
  - [ ] Add Module 14 task: add small hydro (~15 MW), landfill gas (~10 MW), biogas (~5 MW) as explicit expansion candidates
- [ ] If Option B (keep `other_re` through V1):
  - [ ] Document removal as mandatory pre-Module 14 task in Module 14 plan
  - [ ] Do not add explicit biomass generators (double-count risk confirmed)
- [ ] All explicit biomass plants (Sappi, Mondi, Ngodwana, Joburg Landfill) remain excluded — no config changes needed
