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

### 1.2 Confirmed dispatch (Co2L full-year solve)

Hydro StorageUnit dispatch from `elec_s_34_ec_lcopt_Co2L-1H.nc`, July 2023:

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

### 2.3 Critical question: double-count risk with `other_re`

Module 05 carrier taxonomy states:

> "explicit generator only when present in 2023-active reconciliation; otherwise covered by `other_re`"

The `other_re` exogenous generator replays Eskom's `Other RE` hourly timeseries (34 buses,
total p_nom ≈ 50.6 MW distributed). The Eskom `Other RE` column (glossary definition) covers:
**small hydro (<10 MW?), landfill gas, biomass/biogas, bagasse/biomass co-generation**.

This creates a potential double-count if we add Ngodwana/Sappi/Joburg Landfill as explicit
generators while `other_re` already represents the Eskom-reported aggregate.

**Key distinction to resolve before including biomass:**

| Plant | Likely Eskom treatment |
|---|---|
| Joburg Landfill Gas (7.56 MW) | Almost certainly inside Eskom `Other RE` column |
| Ngodwana Energy (25 MW) | Likely REIPPPP bioenergy IPP → Eskom `Other RE` or separate REIPPPP row |
| Sappi (144 MW) | Pulp mill captive co-gen; unclear if dispatched by Eskom National Control or captive; NOT a REIPPPP project |

**Sasol analogy:** If Sappi is captive industrial (like Sasol), it should be excluded for the same
reason Sasol is recommended for removal — it is not dispatched by Eskom National Control and
its generation does not appear in any Eskom hourly column.

### 2.4 Options for Opus

**Option A — Exclude all biomass (default, recommended for V1 baseline)**

Leave biomass excluded from `conventional_carriers`. Accept that Ngodwana/Joburg Landfill are
already inside the `other_re` exogenous profile. Sappi and Mondi are treated as captive industrial
(similar to Sasol decision).

Pros: no double-count risk; consistent with Sasol exclusion logic; `other_re` already accounts
for bioenergy generation in aggregate.  
Cons: Sappi 144 MW may actually sell surplus to grid at some hours, and is genuinely dispatchable.

**Option B — Include Ngodwana only**

Add `biomass` to `conventional_carriers` in ZA config. Include only Ngodwana (25 MW, confirmed
REIPPPP bioenergy, separately metered). Exclude Sappi/Mondi (captive industrial) and Joburg
Landfill (inside other_re). Adjust `other_re` p_nom or profile to subtract Ngodwana generation.

Requires:
1. Add `biomass` to `conventional_carriers` in `za_2023_fixed_validation.yaml`
2. Fix carrier mapping: add a pre-processing step in `reconciliation.py` or `add_electricity.py`
   to normalise `Bioenergy → biomass` case-insensitively, OR add `"Bioenergy": "biomass"` key
   to `carrier_dict` in `add_electricity.py:142`
3. Add `biomass` cost row to `data/za_audit/za_local_carrier_cost_rows.csv`
4. Verify Ngodwana bus assignment is valid after 34-cluster aggregation
5. Audit Eskom `Other RE` series to confirm Ngodwana is NOT already included there

Pros: more explicit fleet; Ngodwana is a separately reported REIPPPP plant.  
Cons: audit burden; Ngodwana 25 MW is negligible at system scale.

**Option C — Defer to Module 13**

Leave biomass excluded in V1 baseline. Flag as known omission in the Module 13 validation report.
Add audit task to review Sappi/Ngodwana generation data before Module 14 expansion.

Pros: no risk to V1 calibration; biomass is small relative to calibration targets.  
Cons: known blind spot in fleet completeness.

### 2.5 Recommendation

**Option A for V1**: leave biomass excluded. Rationale:
- Total biomass capacity in scope = 176.56 MW (without Mondi) — <0.5% of system.
- Generation at realistic capacity factors: ~100–600 GWh/yr — small relative to calibration gaps
  (coal EAF, nuclear availability, PHS dispatch).
- Double-count risk with `other_re` is real and not easily disentangled without plant-level Eskom
  metering data.
- Consistent with Sasol exclusion (captive industrial logic for Sappi/Mondi).
- Flag in Module 13 report as known omission with quantified upper bound.

If Opus chooses Option B, start with Ngodwana only (25 MW) and resolve the double-count question
by checking the NERSA licence and Eskom REIPPPP reconciliation data first.

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
may still look flat or sub-optimal. The Co2L full-year solve is authoritative for calibration.

---

## 4. Checklist for Module 12 implementation

### Hydro
- [ ] Fix notebook: replace generator lookup with StorageUnit lookup for hydro and PHS panels
- [ ] Verify Eskom `Hydro Water Generation` July 2023 and compute model vs Eskom error
- [ ] Verify `max_hours = 3366` against IRENA ZA hydro total and `data/hydro_capacities.csv`
- [ ] If dispatch gap > 30%: investigate IRENA normalization multiplier in `renewable.hydro` config

### Biomass
- [ ] Confirm decision: Option A (exclude, V1 default) or Option B (include Ngodwana)
- [ ] If Option A: add explicit note in Module 13 validation report (omission flagged, quantified)
- [ ] If Option B:
  - [ ] Add `biomass` to `conventional_carriers` in `za_2023_fixed_validation.yaml`
  - [ ] Fix carrier case sensitivity: add `"Bioenergy": "biomass"` to `carrier_dict` in `add_electricity.py:142`
  - [ ] Add biomass cost row to `data/za_audit/za_local_carrier_cost_rows.csv`
  - [ ] Verify Ngodwana is NOT already counted in Eskom `Other RE` series
  - [ ] Verify Ngodwana bus assignment after 34-cluster (bus 135 pre-cluster → which Eskom area?)
  - [ ] Rebuild from `build_powerplants` stage if Option B chosen
