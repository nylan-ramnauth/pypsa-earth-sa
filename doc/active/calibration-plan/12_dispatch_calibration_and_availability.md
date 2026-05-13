# 11 Dispatch Calibration And Availability

## Goal

Solve the fixed 2023 network and add the minimum availability/outage/operational
constraints needed for an interpretable match to Eskom 2023 dispatch.

## Solve Target

All solves — including smoke runs and the final 8760 validation — use Gurobi per Module 01.
HiGHS is not used at any stage. Use the Gurobi options locked in the `01` ZA overlay; do not
override `method`, `crossover`, `BarConvTol`, `threads`, `OptimalityTol`, or `FeasibilityTol`
for the final solve.

The first solve should be intentionally simple:

```text
fixed existing fleet
2023 demand
2023 renewable profiles
load shedding variable enabled
imports/exports represented
no new capacity expansion
no future assets
```

## Pre-solve actions (carried over from Module 11 investigation)

These items must be resolved before the calibration sequence starts. They were identified
during Module 11 smoke analysis and the Fix A/B notebook (`module12_readiness_report.ipynb`).

Hydro and biomass carrier issues are documented separately in
`doc/active/calibration-plan/pre_12_hydro_and_biomass.md` — read that document before
starting the calibration sequence.

**Status (2026-05-13):**
- Biomass/`other_re`: ✅ Option A implemented — `other_re` removed from `apply_za_local_carriers.py`.
- Hydro notebook fix: ✅ Done — `dispatch_calibration_validation.ipynb` uses `storage_dispatch()`.
- Hydro structural multiplier: ✅ Done — `renewable.hydro.multiplier = 1.20`; annual residual −29.79% at 1 398.4 GWh vs Eskom 1 991.8 GWh. July inversion is structural to ERA5 winter runoff + cyclic-SOC LP and deferred to Module 13/14.

---

### Fix C — Remove the EU-default CO2 cap

**Root cause confirmed (notebook §5.1):** `electricity.co2limit` defaults to 77.5 Mt/yr (EU-2030
decarbonisation target). With `coal.co2_emissions = 1.010` (Module 11 value, tCO2/MWh_el) and
`coal.efficiency ≈ 0.356`, PyPSA's `primary_energy` constraint applies an effective emission rate
of `1.010 / 0.356 ≈ 2.84 tCO2/MWh_el`, capping annual coal at ~27 TWh — far below South Africa's
~150 TWh actual. This drove 76 % July load shedding in the earlier `Co2L-1H` diagnostic solve.

**Decision (owner: Opus/Module 12):** For the V1 calibration baseline, drop the CO2 cap entirely.
South Africa has no binding national CO2 cap equivalent to EU ETS in 2023. The carbon tax exists
but is not a dispatch-level hard constraint on electricity generation. CO2 policy scenarios are
deferred to Module 14 (expansion handoff).

Apply in `configs/za/za_2023_fixed_validation.yaml`:

```yaml
electricity:
  co2limit: null   # disable EU-default; no ZA 2023 binding dispatch-level cap
```

Alternatively, reinterpret `coal.co2_emissions` as tCO2/MWh_th (fuel basis, ~0.34) which is the
upstream PyPSA-Earth convention. Either approach is acceptable; the config override is simpler
and leaves the carrier attribute unchanged for Module 13 reporting.

The canonical Module 12 solve label is `NoCO2-1H`; do not use a `Co2L*` opts label for
the structural or calibrated 2023 baselines. Document the chosen approach and rationale in
`doc/za_implementation_log.md`.

---

### CSP dispatch — confirm it works without the CO2 cap; fix if zero

**Investigation finding (notebook §6.3, confirmed 2026-05-12):**

- CSP has 500 MW installed across 3 buses: Kalahari 100 MW, Kimberley 200 MW, Namaqualand 200 MW.
- `p_max_pu` is correctly time-varying from the atlite CSP profile (July mean ~14 %, max ~52 %).
- `p_min_pu = 0`, `marginal_cost = 0`. CSP is free and should always dispatch ahead of coal.
- **Earlier CO2-capped full-year diagnostic solve:** CSP July dispatch = **51.6 GWh** ✓ (correct behaviour).
- **NoCO2 demo solve (July only):** CSP dispatch = **0 GWh** ✗

**Superseded investigation hypothesis:** Earlier notes suspected a barrier-only
solver artifact (`crossover: 0`) because coal could meet demand unconstrained
while CSP sat at zero. That hypothesis is retained only as investigation
history; it is **not** the accepted root cause.

**Accepted root cause (confirmed in the `lc1_NoCO2-1H` correction):**
PyPSA-Earth's advanced-CSP representation routes the CSP solar-field Generator
through a CSP Store and Link before electricity reaches the parent AC bus.
`add_extra_components.py` created those Stores and Links with zero fixed
capacity and extendable flags. Because the Module 12 fixed-grid baseline has
empty `extendable_carriers`, the CSP Link/Store path stayed at zero capacity,
so positive CSP Generator nameplate could not produce electric output.

**Module 12 action (Opus decides):**

1. After applying Fix C, re-run the July smoke solve with the CO2 cap removed. Check whether CSP
   dispatches in the full pipeline (not the demo re-solve). The capped-solve evidence suggests CSP works
   correctly when the full Snakemake solve chain is used.
2. If CSP still shows 0 GWh in the unconstrained baseline, investigate:
   a. Whether `apply_za_local_carriers` correctly writes the CSP `p_max_pu` time series into the
      solved network (check `elec_s_34_ec_lcopt_*.nc` generators_t.p_max_pu for CSP columns).
   b. Whether each positive CSP Generator bus has a matching fixed positive
      CSP Link `p_nom` and Store `e_nom`. This is now the primary gate.
   c. Whether solver settings need diagnostic review only after the physical
      CSP Link/Store path is bus-complete. Do not treat crossover as the
      production fix for dead CSP output.
3. CSP must dispatch in the calibrated baseline. The Eskom 2023 anchor is **1.375 TWh annual**
   (42 GWh July). Zero CSP dispatch is not acceptable for the calibration baseline.

---

### Sasol — decision: remove from fleet or treat as must-run

**Investigation finding (notebook §6.3, confirmed 2026-05-12):**

Sasol entries in `custom_powerplants.csv`:

| Name | Fueltype | Technology | Capacity | Carrier |
|---|---|---|---|---|
| Secunda_coal | Hard Coal | Steam Turbine | 600 MW | (maps to coal — not sasol_coal) |
| Sasolburg_coal | Hard Coal | Steam Turbine | 128 MW | sasol_coal |
| Sasol_ice | Natural Gas | OCGT | 175 MW | sasol_gas |
| Sasol_ocgt | Natural Gas | OCGT | 250 MW | sasol_gas |

Observed dispatch in demo solve: `sasol_coal` = 95.2 GWh July (128 MW at ~100 % CF — must-run
behaviour). `sasol_gas` = 14.2 GWh July (occasional).

**Why Sasol should not be a free merit-order generator:**

- **Sasol coal (Sasolburg):** Captive industrial power serving Sasolburg chemical complex.
  Runs on process heat demand, not Eskom merit order. No Eskom hourly validation column.
  Eskom `Thermal Generation` = Eskom-owned coal stations only (glossary). Sasol does not appear.
- **Sasol gas (Secunda OCGTs):** Eskom glossary: `Dispatchable IPP OCGT` = "OCGT plant owned by
  an IPP and **dispatched by Eskom National Control**." Sasol gas turbines are self-dispatched for
  Secunda industrial demand, NOT dispatched by Eskom National Control. They do not belong in the
  `Eskom OCGT + Dispatchable IPP OCGT` comparison.
- **No hourly Eskom column** exists for Sasol generation. Cannot validate against actuals.
- **Spurious merit-order dispatch:** Treating Sasol as a free economic generator distorts coal
  and OCGT dispatch. At 100 % CF, `sasol_coal` displaces 95 GWh of Eskom coal — but this
  displacement is not in the Eskom data, making the coal calibration harder to interpret.

**Decision (2026-05-12, applied): Option A — Sasol removed entirely.**

`Sasolburg_coal` (128 MW), `Sasol_ice` (175 MW), and `Sasol_ocgt` (250 MW) rows were
removed from `custom_powerplants.csv`. The structural `lc1_NoCO2-1H` baseline was built
and solved without Sasol. Rationale: Sasol self-dispatches for industrial process demand;
its generation is embedded in RSA Contracted Demand, not dispatched by Eskom National
Control. No Eskom hourly validation column exists. If Sasol energy is needed for annual
carbon accounting, add as a fixed-dispatch accounting generator in Module 13.

---

## Calibration sequence

Availability is a validation requirement, not only an expansion concern. Without carrier-level EAF,
the 2023 dispatch is over-optimistic (model over-produces, under-sheds) relative to reality.

**Required calibration order:**

1. **Module 12 structural baseline — no availability** ✅ DONE (2026-05-12)
   Solved as `lc1_NoCO2-1H`. All 12 acceptance gates PASS. No Sasol, no `other_re`,
   corrected PHS duration, CSP 500 MW / 2850 MWh TES wired via `za_fix_csp_links_stores`,
   transmission expansion locked (`ll: c1`). Network at:
   `results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H.nc`.

2. **EAF-calibrated solve — station-level weekly coal EAF** ✅ DONE (2026-05-12)
   Applied `pypsa-rsa` `plant_availability.xlsx:outage_profiles` BASE scenario
   to coal generators only as hourly `generators_t.p_max_pu`. Split
   `custom_powerplants.csv` rows (`X`, `X_2`) share the same station profile and
   are capacity-weighted to bus level. Kelvin (160 MW) falls back to the matched
   coal fleet mean. The EAF solve is optimal at:
   `results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF.nc`.
   The notebook reports 12/12 PASS for `eaf_calibrated`; annual coal
   over-production improves from +28.3 TWh to +17.8 TWh.

3. **Diagnostic cross-check — residual mix errors** ⚠️ OPC IMPLEMENTED; OCGT RESIDUAL REMAINS (2026-05-13)

   One calibration blocker remains before Module 13:

   **A — OCGT LP substitution artifact.**
   When coal is constrained by EAF, OCGT dispatch jumps from 6.93 TWh to 17.37 TWh,
   far exceeding Eskom 2023 OCGT actuals = **5.24 TWh** (Eskom OCGT 3.566 +
   Dispatchable IPP OCGT 1.677, per `data/za_validation/eskom_2023_targets_by_carrier.csv`).
   The LP is using OCGT as a cheap scarcity substitute instead of shedding load.

   **Implemented overlay (2026-05-13):** ported
   `pypsa-rsa/scripts/custom_constraints.py::apply_operational_constraints` into
   `scripts/za_fleet/operational_constraints.py` and activated the HIGH_GAS
   `operational_constraints.xlsx` row in the new solve target
   `results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC.nc`.
   The audit confirms `ocgt_diesel + ocgt_avf` weekly CF max 50% and nuclear
   hourly CF min 100% are applied; `ccgt_steam`, `rmippp`, and `sasol_*` no-op
   because the carriers are absent from the Module 12 fixed fleet.

   **Actual result:** OCGT falls from 17.37 TWh to **14.62 TWh**, and load
   shedding rises from 0.04 TWh to **2.24 TWh**. This is an improvement but not
   closure: the source 50% weekly CF row implies an annual OCGT-diesel ceiling
   of `0.5 × 3.419 GW × 8760 h = 14.98 TWh`, so it cannot by itself force the
   Eskom 5.24 TWh envelope. Do not replace this with bespoke code without a new
   source-backed decision; Module 13 must either accept the documented residual
   or add a source-row change to the operational-constraints workbook.

   **B — Hydro dispatch gap. ✅ DONE (2026-05-13).**
   Model annual hydro = **1 398.4 GWh** vs Eskom **1 991.8 GWh**; residual
   **−29.79%** at `renewable.hydro.multiplier = 1.20` (Layer A IRENA-vs-Eskom
   scope × Layer B 1/0.9 efficiency). July inversion is structural to ERA5
   winter-peaked runoff + cyclic SOC and is deferred to Module 13/14.

4. **Non-coal availability overlays** — out of scope for the coal EAF PR.
   Nuclear, OCGT, hydro, and CSP availability overlays require separate
   source-backed implementation plans.

5. **Operational constraint additions** (fuel ramp rates, minimum up/down time) — optional,
   add only if step 2 fails and step 4 still fails. Document any additions in the log.

All solves use Gurobi per Module 01. No HiGHS.

This module must produce its own interim before/after calibration report. The
final validation report in `12_validation_reporting_and_acceptance.md` is not
the first source of validation evidence.

### Availability formula

```text
EAF = 1 - (Total PCLF + Total UCLF+OCLF)
```

`Total UCLF+OCLF` and `Total PCLF` are the exact Eskom columns repaired and
validated by module `02`.

Pre-flight must inspect `data/eaf_weekly.csv` and `data/nuclear_p_max_pu.csv`.
V1 default is to disable both because the cleaned Eskom EAF takes precedence;
if either file is retained, document the reason and the affected carriers in
the interim calibration report.

### pypsa-rsa `plant_availability.xlsx` schema

If station-level EAF fallback is needed, the implementing agent must:
1. Open `plant_availability.xlsx` at the pinned pypsa-rsa commit
2. Record the sheet name(s), column layout, station identifier column name, and EAF column name
3. Document the schema in `doc/za_implementation_log.md`
4. Write a parser that maps station names to `custom_powerplants.csv` `Name` values
   (station names may differ between sources — require a reconciliation table)

### Infeasibility triage

If the solver returns infeasible on any stage:

1. **Check Other RE:** Confirm `p_min_pu = 0` (not `p_min_pu = p_max_pu`). Fixed-dispatch
   Other RE at high-generation periods can exceed demand and cause infeasibility.
2. **Check load-shedding is enabled:** `solving.options.load_shedding: true` must be set.
   If enabled and solver is still infeasible, the problem is in constraints, not cost.
3. **Check demand coverage:** Confirm that total `p_nom * p_max_pu` of all generators at any
   hour exceeds the demand at that hour plus load-shedding generator capacity.
4. **Check transmission:** Confirm no isolated buses (buses with no connecting lines) exist.
5. **Reduce scope:** Re-run on the 7-day smoke period with `Threads=2` to isolate the failure hour.
6. Document the failure and resolution in `doc/za_implementation_log.md`.

## Optional Constraints, In Order

The OCGT cap and all single-line CF/energy constraints below are now sourced
from `operational_constraints.xlsx` via the ported applier. New entries should
be added as workbook rows under the active scenario, not as bespoke code.

```text
OCGT annual/weekly energy caps
coal minimum stable levels
nuclear must-run assumptions
hydro/PHS energy constraints
overgeneration slack only if infeasible overgeneration remains after renewable
  curtailment and PHS/hydro checks
linearized unit commitment (last-resort dispatch-only; not V1 unless Stage 3
  fails after earlier constraints)
reserve constraints (dispatch-validation only; no interaction with the
  reliability slack penalty owned by doc/active/reliability-plan/)
```

Note: Sasol annual energy caps are no longer listed here. Sasol fleet membership
is decided in the pre-solve actions above (Option A: remove; Option B: must-run).
Do not apply Sasol caps as an optional constraint on top of an unresolved fleet
membership question.

Each added constraint must have a source, a config switch, a report entry, and a
before/after validation comparison.

## Interim Calibration Outputs

```text
data/za_validation/za_2023_dispatch_calibration_before_after.csv
data/za_validation/za_2023_dispatch_calibration_constraints.csv
results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H.nc
doc/za_2023_dispatch_calibration_report.md
```

The path above locks the validation wildcards to `clusters: 34`, `ll: c1`, and
`opts: NoCO2-1H` for the structural baseline. Previous attempts used `ll: copt`,
which silently enabled line expansion (~+220 MW across 82/82 lines) and thereby
violated the fixed-grid requirement. The EAF-calibrated solve must use a
non-`Co2L` label derived from this `lc1` baseline label.

## Pre-Solve Fixes (Module 12 follow-up, 2026-05-13)

The `lc1_NoCO2-1H` baseline replaces the deprecated `lcopt_NoCO2-1H` baseline.
Three additional fixes apply before the solve is acceptable:

1. **CSP electric path.** `add_extra_components.py:177-215` adds extendable
   zero-capacity Stores + Links for advanced CSP, so with empty
   `extendable_carriers` the CSP electric output is dead. New rule
   `za_fix_csp_links_stores` (script `scripts/za_fleet/fix_csp_links_stores.py`)
   sets fixed `Link.p_nom = bus-level CSP nameplate` and
   `Store.e_nom = nameplate × capacity-weighted storage hours` from
   `data/za_audit/za_named_plant_inventory.csv`, then flips both to
   `*_extendable = False`. Audit at `resources/.../za_csp_fix_audit.csv`.
2. **PHS pumping sign.** The validation notebook now reports PHS pumping as
   positive consumption on both model side (`-storage_units_t.p.clip(upper=0)`)
   and Eskom side (`abs(Pumped Water SCO Pumping)`).
3. **Expansion gate.** Validation notebook (cell `module12-09`) and audit
   script (`scripts/build_za_fixed_network_audit.py`) check
   `*_extendable.sum() == 0` for Generators, StorageUnits, Stores, Links, and
   Lines. Per-component counts written to
   `data/za_audit/za_fixed_network_extendable_audit.csv`.

## Acceptance Gates

- Solved network output exists for the selected spatial level.
- Annual validation table is produced.
- Load shedding energy and hours are reported against `MLR + ILS + IOS`.
- Every calibration constraint is justified by a validation failure.
- Interim before/after calibration report is written before final acceptance.
- No expansion capacity appears in solved results (all 5 component classes).
- CSP Link `p_nom > 0` and CSP Store `e_nom > 0` at every bus with positive
  CSP Generator `p_nom`. Zero-capacity CSP buses are allowed.
- PHS pumping reported as positive consumption on both model and Eskom sides.

## Reconciliation Note — Solve 4 OCGT Annual Cap (2026-05-13)

The OCGT blocker in §3.A was tested with a fourth solve,
`lc1_NoCO2-1H-EAF-OPC-CAP`, after adding one source-workbook row to
`../pypsa-rsa/scenarios/Coal_Flexibilisation/sub_scenarios/operational_constraints.xlsx`
under `HIGH_GAS`:

| scenario | bus | tech_fuel | type | period | incl_pu | limit | apply_to | units | 2023 |
|---|---|---|---|---|---:|---|---|---|---:|
| HIGH_GAS | global | ocgt_diesel | output_energy | year | False | max | all | TWh | 5.5 |

The workbook formulas were converted to explicit values so pandas can read the
2023 columns without relying on Excel cached formula results. The source row is
committed in pypsa-rsa at `0831ce243f0badbba6f09b418c2b57774ea89a5f`, and this
config now pins that commit.

Solve 4 results:

| Metric | Result | Gate |
|---|---:|---|
| OCGT diesel annual dispatch | 5.500 TWh | PASS, <= 5.5 TWh |
| Load shedding | 10.748 TWh | PASS, <= Eskom 16.755 TWh |
| Annual carrier subtotal error | -1.31% | **FAIL**, threshold <= 0.5% |
| Weekly combined scarcity Pearson r | 0.729 | moderate temporal alignment |
| Monthly combined scarcity Pearson r | 0.854 | strong temporal alignment |

Conclusion: the OCGT LP-substitution artifact is fixed, but Module 12 remains
open because the annual subtotal gate still fails. The remaining blocker shifts
to portable non-OCGT calibration: PHS under-dispatch, VRE annual levels, and the
residual coal/load-shedding split. See
[[6-codebases/repos/pypsa-earth/doc/active/calibration-plan/module13_ocgt_investigation_report|Module 13 OCGT investigation report]]
and the appended Solve 4 section in
[[4-work/reports/2026-05-12-module12-calibration-report|Module 12 calibration report]].
