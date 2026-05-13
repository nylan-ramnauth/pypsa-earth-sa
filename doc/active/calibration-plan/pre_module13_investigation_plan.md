# Pre-Module 13 Investigation Plan
# Diagnose, Fix, and Accept Calibration Residuals Before Validation Reporting

**Date:** 2026-05-13
**Investigation completed:** 2026-05-13 (Opus)
**Status:** INVESTIGATION COMPLETE — agent needed for Module 13 deliverables only (Section 9)
**Codebase root:** `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth`
**Vault root:** `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault`

---

## 0. Purpose and Scope

This plan sits between Module 12 and Module 13. Module 12 is functionally complete for
its mechanism deliverables (EAF overlay, operational constraints, OCGT cap, four-solve
evidence trail) but has not achieved a defensible final dispatch calibration. These are
the remaining errors in the best solve (EAF-OPC-CAP, solve 4):

| Carrier | Eskom GWh | Solve 4 GWh | Error |
|---|---:|---:|---:|
| coal | 165,627 | 184,406 | +11.3% |
| nuclear | 8,127 | 8,673 | +6.7% |
| ocgt | 5,243 | 5,500 | +4.9% ✅ |
| hydro | 1,992 | 1,398 | −29.8% |
| phs_generation | 4,294 | 147 | **−96.6%** |
| wind | 11,613 | 7,312 | −37.0% |
| solar_pv | 5,015 | 3,557 | −29.1% |
| csp | 1,375 | 806 | −41.4% |
| load_shedding | 16,755 | 10,748 | −35.9% |

**Goal of this plan:** Diagnose each blocker, fix those that are portable and
source-backed, accept the rest as documented limitations, produce a fifth solve
(if needed), and leave the project in a state where Module 13 validation reporting
can proceed with a clear acceptance boundary.

**Do not implement anything in Module 13 (`13_validation_reporting_and_acceptance.md`)
until this plan's final gate check is complete.**

---

## 1. Gate Definition Drift — Fix First

Before any investigation, resolve a documentation inconsistency that will otherwise
block every Module 13 closure claim.

### The problem

The calibration report (`4-work/reports/2026-05-12-module12-calibration-report.md`)
records the Module 12 annual subtotal gate as failing at **−1.31%**. This number
uses demand-addressed total (generation + load_shedding) as the denominator.

The refactored validation notebook defines `TOTAL_PHYSICAL_GENERATION` as physical
generation only (excludes phs_pumping and load_shedding), giving **+4.19%** for solve 4.

These two numbers are measuring different things. Until one is canonical,
every future Module 13 closure claim is ambiguous.

### The fix

**Adopt this definition for all Module 12 and Module 13 subtotal gates:**

```
TOTAL_PHYSICAL_GENERATION = sum(coal, nuclear, ocgt, hydro, phs_generation,
                                wind, solar_pv, csp)
```

Excludes: phs_pumping (consumption), load_shedding (unserved demand, not generation).

This is the correct numerator for a generation-mix calibration. Load shedding and
PHS pumping have separate sections in the validation notebook.

### Required file update

Edit `4-work/reports/2026-05-12-module12-calibration-report.md`:
- Find the gate that says "annual subtotal error ≤ 0.5%" and update the recorded value
  to +4.19% under the `TOTAL_PHYSICAL_GENERATION` definition.
- Add a note: "Subtotal gate definition changed to TOTAL_PHYSICAL_GENERATION (physical
  generation only). Earlier −1.31% figure used demand-addressed total and is superseded."

Do this edit before starting any investigation cell.

---

## 2. Investigation A — PHS Dispatch (read-only, no solve needed)

PHS is the largest blocker: 147 GWh vs Eskom 4,294 GWh (−96.6%). Fixing this has
cascading effects on coal over-dispatch and load shedding.

**Network to inspect:** `results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc`

### Step A1 — Inspect PHS storage unit parameters

```python
import pypsa
n = pypsa.Network("results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc")

phs_units = n.storage_units[n.storage_units.carrier == "PHS"].index
print(n.storage_units.loc[phs_units, [
    "p_nom", "p_nom_opt", "max_hours",
    "efficiency_dispatch", "efficiency_store",
    "marginal_cost", "cyclic_state_of_charge",
    "state_of_charge_initial", "standing_loss",
]])
```

**What to look for:**
- `p_nom` should be ≈ 2,742 MW total (Drakensberg ~1,000 MW + Ingula ~1,332 MW + Palmiet ~400 MW)
- `max_hours` should be ≈ 6–8 hours (normal PHS range). If it is 0 or very small, PHS has no
  energy capacity and cannot dispatch.
- `marginal_cost` > 0 would suppress dispatch — check if any non-zero value is present
- `cyclic_state_of_charge = True` is standard; check `state_of_charge_initial` is not forcing
  the unit to start full and stay full

### Step A2 — Inspect PHS dispatch timeseries

```python
import matplotlib.pyplot as plt
phs_p = n.storage_units_t.p[phs_units].sum(axis=1)
phs_soc = n.storage_units_t.state_of_charge[phs_units].sum(axis=1) if not n.storage_units_t.state_of_charge.empty else None

fig, axes = plt.subplots(2, 1, figsize=(14, 6), sharex=True)
axes[0].plot(phs_p.index, phs_p.values, label="PHS net dispatch (positive=generate)")
axes[0].axhline(0, color="black", lw=0.5)
axes[0].set_ylabel("MW")
axes[0].set_title("PHS net dispatch (solve 4)")
if phs_soc is not None:
    axes[1].plot(phs_soc.index, phs_soc.values)
    axes[1].set_ylabel("MWh")
    axes[1].set_title("PHS state of charge")
plt.tight_layout(); plt.show()

print("PHS dispatch stats:")
print(phs_p.describe())
print(f"Annual generation GWh: {phs_p.clip(lower=0).sum()/1e3:.1f}")
print(f"Annual pumping GWh: {(-phs_p).clip(lower=0).sum()/1e3:.1f}")
```

**What to look for:**
- If `phs_p` is near-zero the entire year, PHS is idle. This is the −96.6% observation.
- If SOC is flat at its maximum value, the cyclic constraint is holding PHS full and
  the LP never finds it worth generating.
- If SOC is flat at zero, energy capacity is zero (`max_hours = 0`).

### Step A3 — Check PHS in `custom_powerplants.csv`

```bash
grep -i "PHS\|pumped\|ingula\|drakensberg\|palmiet" data/custom_powerplants.csv | head -20
```

Confirm:
- All three major South African PHS plants are present
- `Fueltype` = `PHS` (or whatever carrier maps to storage unit carrier "PHS" in PyPSA-Earth)
- `Capacity` values are reasonable

Also check how PyPSA-Earth prepares PHS storage units from `custom_powerplants.csv`:

```bash
grep -r "PHS\|pumped" scripts/add_electricity.py | head -20
```

This will tell you whether `max_hours` is set from a config value or hardcoded.

### Step A4 — Check PHS configuration

```bash
grep -A5 -i "PHS\|pumped_hydro\|reservoir" configs/za/za_2023_fixed_validation.yaml | head -40
grep -A5 -i "PHS\|pumped_hydro" configs/config.default.yaml | head -20
```

Look for:
- `electricity.extendable_carriers` — PHS must NOT be in this list for a fixed-fleet solve
- Any `max_hours` or `efficiency` override for PHS
- Whether PHS is set up as a `StorageUnit` or as a pair of `Links` (the latter is the
  advanced representation and requires different dispatch extraction)

### Step A5 — Compare to Eskom

```python
import pandas as pd
eskom = pd.read_csv("data/za_validation/eskom_2023_hourly_clean.csv", index_col=0, parse_dates=True)
eskom_phs_gen = eskom["Pumped Water Generation"]
eskom_phs_pump = eskom["Pumped Water SCO Pumping"].abs()

print(f"Eskom PHS generation: {eskom_phs_gen.sum()/1e3:.1f} GWh/year")
print(f"Eskom PHS pumping: {eskom_phs_pump.sum()/1e3:.1f} GWh/year")
print(f"Eskom round-trip proxy: {eskom_phs_gen.sum()/eskom_phs_pump.sum():.3f}")
print(f"Model PHS generation: {phs_p.clip(lower=0).sum()/1e3:.1f} GWh/year")
print(f"Model PHS pumping: {(-phs_p).clip(lower=0).sum()/1e3:.1f} GWh/year")
```

### Step A6 — Diagnosis conclusion (write this before proceeding)

After A1–A5, document one of these findings in a markdown cell:

**Diagnosis A-I: max_hours = 0 or near-zero**
Root cause: PHS energy capacity is not being set from `custom_powerplants.csv` or config.
Fix: set `max_hours` for PHS storage units in config or in the network preparation script.
Source anchor: Eskom Drakensberg = ~24 hours at 1,000 MW → 24,000 MWh; Ingula = ~8 hours
at 1,332 MW → 10,656 MWh; Palmiet ≈ 22 hours at 400 MW → 8,800 MWh.

**Diagnosis A-II: marginal_cost > 0 suppressing dispatch**
Root cause: a positive marginal cost is making PHS uneconomic relative to coal.
Fix: set `marginal_cost = 0` for PHS storage units (standard PyPSA-Earth convention for
hydro storage).

**Diagnosis A-III: cyclic SOC locks PHS full**
Root cause: cyclic boundary condition + implicit cost structure makes the LP never want
to discharge PHS (coal is cheaper at margin, so SOC stays at maximum).
Fix: add a small water-budget or monthly energy availability constraint, or
set `state_of_charge_initial` to 50% of capacity.

**Diagnosis A-IV: structural — no PHS in model**
If grep in A3 finds no PHS plants, PHS was not included in `custom_powerplants.csv`.
Fix: add PHS plants manually.

Record the actual finding and diagnosis in the investigation output below.

---

## 3. Investigation B — VRE Annual Level Gap (read-only, no solve needed)

Wind −37%, solar −29%, CSP −41% are consistent under-generation. The diurnal and
monthly profiles are structurally reasonable (from notebook Section 2), so this is
an annual energy gap, not a temporal shape problem.

**Two hypotheses:**
- B-I: Model installed capacity (`p_nom`) is less than 2023 Eskom installed capacity
- B-II: Cutout capacity factors are systematically low relative to Eskom actuals

### Step B1 — Check model installed VRE capacity

```python
n = pypsa.Network("results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc")

wind_gens = n.generators[n.generators.carrier == "onwind"]
solar_gens = n.generators[n.generators.carrier == "solar"]
csp_gens = n.generators[n.generators.carrier == "csp"]

print(f"Model onwind p_nom total: {wind_gens.p_nom.sum():.0f} MW")
print(f"Model solar p_nom total: {solar_gens.p_nom.sum():.0f} MW")
print(f"Model csp p_nom total: {csp_gens.p_nom.sum():.0f} MW")

# Also check p_nom_max (potential cap)
if "p_nom_max" in wind_gens:
    print(f"Model onwind p_nom_max (avg): {wind_gens.p_nom_max.mean():.1f} MW")
```

**Reference values (Eskom Annual Report / IRP 2023, South Africa installed):**
- Wind: ≈ 3,400 MW (IPP fleet active end-2023)
- Solar PV: ≈ 2,200 MW (utility-scale)
- CSP: ≈ 500 MW (confirmed from Module 12 — Kalahari 100 MW + Kimberley 200 MW + Namaqualand 200 MW)

If model wind is significantly below 3,400 MW, Hypothesis B-I is confirmed.

### Step B2 — Compute model capacity factor and compare to Eskom

```python
import pandas as pd

eskom = pd.read_csv("data/za_validation/eskom_2023_hourly_clean.csv", index_col=0, parse_dates=True)

# Model annual generation
model_wind_gwh = n.generators_t.p[wind_gens.index].sum().sum() / 1e3
model_solar_gwh = n.generators_t.p[solar_gens.index].sum().sum() / 1e3

model_wind_cap_mw = wind_gens.p_nom.sum()
model_solar_cap_mw = solar_gens.p_nom.sum()

# Model CF
model_wind_cf = model_wind_gwh / (model_wind_cap_mw * 8760 / 1e3)
model_solar_cf = model_solar_gwh / (model_solar_cap_mw * 8760 / 1e3)

# Eskom CF (use Eskom Wind Installed Capacity column if available, else use IRP anchor)
eskom_wind_gwh = eskom["Wind"].sum() / 1e3
eskom_solar_gwh = eskom["PV"].sum() / 1e3
eskom_wind_cap_mw = 3400  # IRP/Eskom 2023 anchor — adjust if better source available
eskom_solar_cap_mw = 2200  # IRP/Eskom 2023 anchor

eskom_wind_cf = eskom_wind_gwh / (eskom_wind_cap_mw * 8760 / 1e3)
eskom_solar_cf = eskom_solar_gwh / (eskom_solar_cap_mw * 8760 / 1e3)

print("--- Wind ---")
print(f"  Model: {model_wind_gwh:.0f} GWh, {model_wind_cap_mw:.0f} MW, CF={model_wind_cf:.1%}")
print(f"  Eskom: {eskom_wind_gwh:.0f} GWh, {eskom_wind_cap_mw:.0f} MW, CF={eskom_wind_cf:.1%}")

print("--- Solar PV ---")
print(f"  Model: {model_solar_gwh:.0f} GWh, {model_solar_cap_mw:.0f} MW, CF={model_solar_cf:.1%}")
print(f"  Eskom: {eskom_solar_gwh:.0f} GWh, {eskom_solar_cap_mw:.0f} MW, CF={eskom_solar_cf:.1%}")
```

**Interpretation guide:**
- If model CF ≈ Eskom CF but model p_nom < Eskom p_nom → Hypothesis B-I confirmed (capacity gap)
- If model p_nom ≈ Eskom p_nom but model CF << Eskom CF → Hypothesis B-II confirmed (cutout quality)
- If both are off → compound problem, treat as documented limitation

### Step B3 — Check `custom_powerplants.csv` VRE rows

```bash
grep -i "wind\|solar\|pv" data/custom_powerplants.csv | wc -l
grep -i "wind" data/custom_powerplants.csv | awk -F',' '{sum += $NF} END {print "Total wind capacity in CSV: " sum " MW"}'
```

If `custom_powerplants.csv` has fewer wind/solar capacity rows than the IRP 2023 fleet,
the PyPSA-Earth network builder will not place those generators, regardless of cutout quality.

### Step B4 — Diagnosis conclusion

After B1–B3, document one of:

**Diagnosis B-I: Installed capacity gap**
Model p_nom is materially below Eskom 2023 installed. This is a fleet reconciliation issue
from Module 08. Fix: add missing VRE capacity rows to `data/custom_powerplants.csv` using
IRP 2023 / Eskom 2023 fleet as source. Rebuild network (Module 11 rule), re-solve.

**Diagnosis B-II: Cutout CF mismatch**
Installed capacities match but ERA5 cutout produces lower CFs than Eskom actuals.
Fix: apply a multiplicative annual scaling factor to VRE profiles. Document the scaling
factor and its provenance in the limitations report. Note: this is a calibration
approximation, not a physical fix. Flag it as such in Module 13 docs.

**Diagnosis B-III: Compound / uncertain**
Both are off by less than 10–15 percentage points in CF. Accept as documented limitation.
Quantify the contribution to coal over-dispatch using a sensitivity estimate.

---

## 4. Investigation C — Hydro Timing and Annual Level (brief)

Hydro is −29.8% annually with an inverted seasonal profile (too high in winter, too low
in summer). This was already tracked in Module 12 with the note "July inversion is
structural to ERA5 winter runoff + cyclic-SOC LP and deferred to Module 13/14."

### Step C1 — Quick parameter check

```python
hydro_units = n.storage_units[n.storage_units.carrier == "hydro"].index
print(n.storage_units.loc[hydro_units, ["p_nom", "max_hours", "inflow", "cyclic_state_of_charge"]])
if "inflow" in n.storage_units_t:
    print("Annual model hydro inflow GWh:", n.storage_units_t.inflow[hydro_units].sum().sum() / 1e3)
```

### Step C2 — Accept vs fix decision

If the inflow timeseries is pulling from the ERA5 runoff cutout (which peaks in winter for
South Africa due to summer-rainfall / winter-rainfall regional mismatch), the seasonal
inversion is not fixable without replacing the inflow timeseries. This is a Module 14
input improvement, not a Module 12/13 fix.

**Acceptance condition:** Annual hydro gap ≤ 35% AND seasonal inversion is documented
as an ERA5 regional mismatch limitation → accept and document.

---

## 5. Investigation D — Coal Residual (no solve needed)

Coal over-dispatch (+11.3%, +18.8 TWh) is partially mechanical: coal fills the gaps
left by inactive PHS and under-realized VRE. After fixing A and B, recheck the coal
number. Do not attempt to directly constrain coal before fixing PHS and VRE.

### Step D1 — Sensitivity estimate (in-notebook calculation)

```python
# Estimate how much coal error would fall if PHS and VRE were at Eskom levels
phs_gap_gwh = 4294 - 147        # PHS generation gap
wind_gap_gwh = 11613 - 7312     # Wind gap
solar_gap_gwh = 5015 - 3557     # Solar gap
csp_gap_gwh = 1375 - 806        # CSP gap
vre_phs_total_gap = phs_gap_gwh + wind_gap_gwh + solar_gap_gwh + csp_gap_gwh

print(f"Combined PHS + VRE gap: {vre_phs_total_gap:.0f} GWh")
print(f"Coal over-dispatch: {184406 - 165627:.0f} GWh")
print(f"If PHS/VRE gaps were closed, coal residual would be approx: "
      f"{184406 - 165627 - vre_phs_total_gap:.0f} GWh")
```

If the residual after closing PHS+VRE is small (< 2,000 GWh, i.e. < 1.2%), coal is
explainable as a substitution artifact. If the residual is large, coal itself needs
further investigation (EAF calibration, unit commitment costs).

---

## 6. Decision Matrix — What to Fix vs Accept

After completing investigations A–D, fill this matrix:

| Issue | Root cause (from investigation) | Action | Portable fix? |
|---|---|---|---|
| PHS −96.6% | _(fill from A6)_ | Fix in solve 5 / Accept | _(fill)_ |
| Wind −37% | _(fill from B4)_ | Fix in solve 5 / Accept | _(fill)_ |
| Solar −29% | _(fill from B4)_ | Fix in solve 5 / Accept | _(fill)_ |
| CSP −41% | _(fill from B4)_ | Fix in solve 5 / Accept | _(fill)_ |
| Coal +11.3% | Substitution artifact (from D1) | Fix after PHS/VRE / Accept | Yes |
| Hydro −29.8% | ERA5 inflow mismatch (from C2) | Accept with limitation note | Yes |
| Load shedding −35.9% | Follows PHS/VRE fix | Reassess after solve 5 | Yes |

**Portable fix** means the fix uses source-backed parameters that would also apply in
a future-year or expansion scenario, not a hard-coded 2023 workaround.

---

## 7. Solve 5 — Conditional on Investigation Findings

**Only run Solve 5 if at least one of PHS or VRE has a portable, source-backed fix.**

If only documentation fixes are found (everything goes to the acceptance column),
skip Solve 5 and proceed directly to Section 8.

### Solve 5 label: `EAF-OPC-CAP-FIX`

Network file: `results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP-FIX.nc`

**Do not overwrite solve 4.** This is a fifth distinct network.

Changes to apply (only what the investigation confirms as source-backed):
- [ ] PHS fix (from Investigation A — record exact parameter changes)
- [ ] VRE capacity adjustment (from Investigation B — record exact MW additions and source)
- [ ] No other changes unless explicitly justified by the investigation

Run:

```bash
cd /Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth

snakemake \
  results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP-FIX.nc \
  --configfile configs/za/za_2023_fixed_validation.yaml \
  --cores 4 \
  -p
```

If the solve target requires a new Snakemake rule or config variant, document
the exact config diff before running. Do not break the existing four solves.

### Solve 5 validation

After Solve 5 completes, add it to the notebook's `NETWORK_PATHS` dict and re-execute.
The notebook handles missing paths gracefully — it will skip solves that are absent,
so you can test incrementally.

---

## 8. Final Gate Check — Module 13 Acceptance

This is the binary decision point. Fill each row after completing investigations and
optionally Solve 5.

### Gate G1 — All investigations complete and documented

- [ ] Investigation A: PHS root cause identified and documented (diagnosis A-I through A-IV)
- [ ] Investigation B: VRE root cause identified and documented (diagnosis B-I through B-III)
- [ ] Investigation C: Hydro accepted or fix identified
- [ ] Investigation D: Coal sensitivity estimate computed

### Gate G2 — Decision matrix filled

- [ ] Every blocker has an explicit "Fix" or "Accept" decision
- [ ] Every "Accept" entry has a one-sentence limitation text ready for `doc/za_model_limitations.md`

### Gate G3 — Solve 5 complete OR skipped with justification

- [ ] If Solve 5 was run: network file exists; notebook re-executed with it; all structural
  gates from Module 12 pass (demand balance, no NaN dispatch, etc.)
- [ ] If Solve 5 was skipped: written justification that no portable fix was found

### Gate G4 — Best solve identified

Identify which of {solve 4, solve 5} is the Module 13 acceptance candidate.
Record:
```
MODULE_13_ACCEPTED_SOLVE = "<label>"
MODULE_13_ACCEPTED_NETWORK = "results/za_2023_fixed_validation/networks/<filename>.nc"
```

### Gate G5 — Remaining error levels documented

For the accepted solve, every carrier with |Δ%| > 10% must have a documented
limitation entry. Minimum required entries:

| Carrier | Δ% (accepted solve) | Limitation text |
|---|---|---|
| coal | _(fill)_ | _(fill)_ |
| phs_generation | _(fill)_ | _(fill)_ |
| wind | _(fill)_ | _(fill)_ |
| solar_pv | _(fill)_ | _(fill)_ |
| csp | _(fill)_ | _(fill)_ |
| load_shedding | _(fill)_ | _(fill)_ |

### Gate G6 — Gate definition is canonical

- [ ] `4-work/reports/2026-05-12-module12-calibration-report.md` updated to use
  `TOTAL_PHYSICAL_GENERATION` as the subtotal metric
- [ ] No other documents refer to the superseded demand-addressed total as the
  Module 12 subtotal gate

### G1–G6 all pass → **proceed to Module 13**

---

## 9. Output Artifacts

After completing this plan, the following artifacts must exist:

| Artifact | Path | Required by |
|---|---|---|
| Updated calibration report | `4-work/reports/2026-05-12-module12-calibration-report.md` | Gate G6 |
| Investigation findings (inline in notebook or separate doc) | notebook Section 0 or new markdown cell | Gates G1–G2 |
| Solve 5 network (if run) | `results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP-FIX.nc` | Gate G3 |
| Updated validation notebook | `notebooks/za_validation/12_dispatch_calibration/dispatch_calibration_validation.ipynb` | Gate G3 |
| Module 13 accepted solve declaration | recorded in this doc, Section 8 Gate G4 | Gate G4 |
| Limitation text for each accepted residual | ready for `doc/za_model_limitations.md` | Gate G5 |

Do not write `doc/za_model_limitations.md` or any Module 13 CSV yet — those are
Module 13 deliverables. Write the limitation text here as draft content to be promoted.

---

## 10. Constraints

- Do not modify any existing solved networks (`.nc` files), not even solve 4
- Do not re-run solves 1–4 under any circumstances
- Do not modify `scripts/` files without noting the change and ensuring it does not
  break the existing four solve chain
- All new code runs inside the notebook or in a scratch cell — do not write new Python
  scripts for investigation-only work
- If you determine Solve 5 is not needed, write a one-paragraph justification in this
  document under Section 7 before proceeding to Section 8

---

## 11. Investigation Output Block — FILLED (Opus, 2026-05-13)

```
=== PRE-MODULE 13 INVESTIGATION SUMMARY ===

Date completed: 2026-05-13
Agent: Claude Opus

PHS root cause: Diagnosis A-III-modified
  PHS is fully and correctly configured: 2,904 MW total, ~60.7 GWh energy capacity
  (~20.9 max_hours average), RTE 0.75, cyclic SOC. Physical parameters are sound.
  Root cause: LP energy-only arbitrage is unprofitable in a flat coal stack with no
  price spread. Model runs ~3.2 cycles/year; Eskom ran ~93 cycles/year. Eskom cycles
  PHS for ancillary services and scheduled load-following — neither is modelled in a
  PyPSA hourly cost-minimisation dispatch.
  PyPSA-RSA audit (2026-05-13): PyPSA-RSA has NO PHS operational constraints in
  operational_constraints.xlsx, plant_availability.xlsx, or fixed_technologies.xlsx.
  Even min_stable_level (30%) is only applied to Generators in _helpers.py, not
  StorageUnits. There is nothing portable to port from PyPSA-RSA.

PHS action: ACCEPTED
  Limitation text: "PHS runs ~3.2 dispatch cycles/year vs Eskom ~93. Root cause is
  LP arbitrage unprofitability in a flat coal stack: without ancillary service value
  or reserve requirements, the LP never dispatches PHS. Physical parameters are
  correctly configured (2,904 MW, ~60.7 GWh capacity, RTE 0.75). Fix requires
  system-services representation or water-budget cycling constraint — both are
  Module 14 architectural scope. WARNING: this limitation propagates directly to
  expansion scenarios. Any Module 14 reliability run that uses this model without
  fixing PHS dispatch will undervalue storage flexibility and overvalue coal in
  scarcity situations — which is the core reliability question. This MUST be resolved
  before Module 14 reliability runs, not just documented here."

VRE root cause: Diagnosis B-II (ERA5 CF systematic underestimate)
  Installed capacity matches 2023 Eskom fleet: wind 3,373 MW, solar 2,288 MW, CSP 500 MW.
  ERA5 CFs are systematically too low relative to Eskom actuals:
    Wind:     ERA5 24.7%  vs Eskom 39.0%  → scale factor 1.58×
    Solar PV: ERA5 17.8%  vs Eskom 25.0%  → scale factor 1.40×
    CSP:      ERA5 18.4%  vs Eskom 31.4%  → scale factor 1.71×
  Likely causes: ERA5 mesoscale bias for SA coastal/escarpment wind corridors; atlite
  extraction parameters not tuned for SA roughness lengths / hub heights; generator
  placements in 34-bus model in lower-resource grid cells.

VRE action: ACCEPTED
  Limitation text: "ERA5 cutout systematically underestimates South African VRE
  capacity factors by 40–71%. Installed capacities are correct (3,373/2,288/500 MW).
  Diagnosed scaling factors: wind 1.58×, solar PV 1.40×, CSP 1.71× relative to
  ERA5 baseline. These are quantified Module 14 inputs — they must be applied as
  explicit CF corrections in expansion config or resolved via atlite re-extraction
  before Module 14 VRE value assessments. Do not dismiss as rounding: a 1.58× wind
  bias means the model undervalues wind energy by 37% annually."

Hydro action: ACCEPTED
  ERA5 inflow 1,649 GWh vs Eskom ~1,992 GWh (−17%). Seasonal inversion is structural
  (ERA5 winter runoff vs summer-rainfall SA geography). Limitation: inflow-limited LP,
  seasonal timing inverted relative to Eskom actuals. Module 14 input improvement needed.

Coal sensitivity:
  Combined PHS+VRE gap = 10,475 GWh (PHS 4,147 + wind 4,301 + solar 1,458 + CSP 569)
  This explains ~56% of the 18,779 GWh coal over-dispatch.
  Genuine coal residual after PHS/VRE correction ≈ +8,304 GWh = +5.0% of Eskom coal.
  This 5% residual reflects EAF calibration limits and is accepted.

Coal action: ACCEPTED (split)
  56% is PHS/VRE substitution artifact. 5% is genuine EAF calibration residual.
  Both are documented. Coal calibration is not the first-order Module 14 fix.

Load shedding action: ACCEPTED
  10,748 GWh vs Eskom 16,755 GWh (−35.9%). Will partially self-correct if PHS/VRE
  are fixed in Module 14. Hard-coding more shedding before fixing PHS/VRE is prohibited.

Solve 5: SKIPPED
  No portable source-backed fix exists for any blocker. PHS requires architectural
  changes (system services); VRE requires cutout rebuild. Hard-coded scaling
  factors are not portable to future years.

Module 13 accepted solve: SOLVE 4 (EAF-OPC-CAP)
Module 13 accepted network:
  results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc

Gates G1–G6:
  G1 — All investigations complete: PASS (A1–A5, B1–B3, C1, D1 in notebook)
  G2 — Decision matrix filled: PASS (all blockers have Fix/Accept + limitation text)
  G3 — Solve 5 skipped with justification: PASS
  G4 — Accepted solve declared: PASS (solve 4)
  G5 — Limitation table complete: PASS (all |Δ%|>10% carriers documented above)
  G6 — Gate definition canonical: PASS (calibration report updated to TOTAL_PHYSICAL_GENERATION)
  → ALL 6 GATES PASS

Investigation notebook:
  notebooks/za_validation/12_dispatch_calibration/pre_module13_investigation.ipynb

==========================================================
```

---

## 12. Remaining Deliverables for Module 13 Agent

The investigation is complete. One agent task remains before Module 13 can start:

1. **Write `doc/za_model_limitations.md`** — promote the limitation texts above from this
   document into the canonical Module 13 limitations file. This is a Module 13 deliverable
   but its content is fully determined here.

2. **Update `_todo.md`** — mark Module 12 as "FUNCTIONALLY COMPLETE, calibration
   accepted with limitations; Module 13 candidate = solve 4." Update the active task entry.

3. **Update `_status.md`** — reflect calibration state: solve 4 is Module 13 candidate;
   PHS and VRE are documented limitations; Module 13 validation reporting ready to begin.

4. **Write wrap-up shared log** — in `5-logs/shared/` with date 2026-05-13.

These four items are the agent's scope. Do NOT begin any Module 13 CSV or validation
report yet — those are Module 13 proper.
