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
starting the calibration sequence. The hydro issue requires a notebook fix; the biomass
issue requires a config decision (default: exclude for V1, see §2.4 of that document).

---

### Fix C — Remove the EU-default CO2 cap

**Root cause confirmed (notebook §5.1):** `electricity.co2limit` defaults to 77.5 Mt/yr (EU-2030
decarbonisation target). With `coal.co2_emissions = 1.010` (Module 11 value, tCO2/MWh_el) and
`coal.efficiency ≈ 0.356`, PyPSA's `primary_energy` constraint applies an effective emission rate
of `1.010 / 0.356 ≈ 2.84 tCO2/MWh_el`, capping annual coal at ~27 TWh — far below South Africa's
~150 TWh actual. This drove 76 % July load shedding in the Co2L-1H stage2 solve.

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

Document the chosen approach and rationale in `doc/za_implementation_log.md`.

---

### CSP dispatch — confirm it works without the CO2 cap; fix if zero

**Investigation finding (notebook §6.3, confirmed 2026-05-12):**

- CSP has 500 MW installed across 3 buses: Kalahari 100 MW, Kimberley 200 MW, Namaqualand 200 MW.
- `p_max_pu` is correctly time-varying from the atlite CSP profile (July mean ~14 %, max ~52 %).
- `p_min_pu = 0`, `marginal_cost = 0`. CSP is free and should always dispatch ahead of coal.
- **Co2L full-year stage2 solve:** CSP July dispatch = **51.6 GWh** ✓ (correct behaviour).
- **NoCO2 demo solve (July only):** CSP dispatch = **0 GWh** ✗

**Root cause of demo zero:** The demo solve uses `crossover: 0` (pure barrier, no crossover step).
Gurobi's interior-point method does not need to land on a vertex of the feasible region. When coal
can meet all demand unconstrained, the barrier solution can sit at CSP = 0 and still satisfy KKT
conditions within tolerance — the solver does not push to the true optimum where CSP displaces
coal. This is a **solver artifact of the barrier-only setting**, not a model bug.

**Module 12 action (Opus decides):**

1. After applying Fix C, re-run the July smoke solve with the CO2 cap removed. Check whether CSP
   dispatches in the full pipeline (not the demo re-solve). The Co2L evidence suggests CSP works
   correctly when the full Snakemake solve chain is used.
2. If CSP still shows 0 GWh in the unconstrained baseline, investigate:
   a. Whether `apply_za_local_carriers` correctly writes the CSP `p_max_pu` time series into the
      solved network (check `elec_s_34_ec_lcopt_*.nc` generators_t.p_max_pu for CSP columns).
   b. Whether enabling crossover (`crossover: -1` in solver options) resolves the degeneracy.
      Note: crossover is expensive on large LPs — use only for diagnostic purposes, not production.
   c. Whether adding a tiny positive marginal cost to CSP (e.g., `1e-3 EUR/MWh`) breaks the
      degeneracy without materially affecting dispatch. Document if applied.
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

**Module 12 decision (Opus):** Choose one of:

**Option A — Remove Sasol entirely from `custom_powerplants.csv`:**
- Remove `Sasolburg_coal`, `Sasol_ice`, `Sasol_ocgt` rows.
- Rebuild fleet from `build_za_fleet_reconciliation` → full pipeline rebuild required.
- Recommended: Sasol's self-dispatch is embedded in RSA Contracted Demand as a contracted IPP;
  its generation is part of the demand side accounting, not a PyPSA dispatchable unit.

**Option B — Convert Sasol coal to must-run (`p_min_pu = p_max_pu = 1.0`):**
- Prevents Sasol from distorting the merit order while keeping it in the energy balance.
- Apply via `apply_za_local_carriers` hook as a targeted `p_min_pu` override.
- Downside: 128 MW must-run coal at a bus not co-located with Eskom coal stations may cause
  transmission artefacts.

**Recommendation:** Option A. Sasolburg is small (128 MW), and there is no Eskom hourly column
to validate against. Removing it simplifies the calibration and avoids the must-run approximation.
If Sasol's energy matters for annual carbon accounting, it can be added as a fixed-dispatch
`other_re`-style accounting generator in Module 13.

Document the chosen option and rebuild in `doc/za_implementation_log.md`.

---

## Calibration sequence

Availability is a validation requirement, not only an expansion concern. Without carrier-level EAF,
the 2023 dispatch is over-optimistic (model over-produces, under-sheds) relative to reality.

**Required calibration order:**

1. **Smoke solve — no availability** (from Module 10 smoke stages)
   Purpose: verify network builds and solves. Not a calibration output.

2. **Baseline solve — with aggregate carrier-level monthly EAF** ← this is the true baseline
   Apply monthly EAF from Eskom data as `p_max_pu` per carrier (coal, nuclear, OCGT, etc.).
   Formula: `p_max_pu[t] = monthly_EAF[carrier][month(t)]`.
   Source: Eskom 2023 monthly EAF by carrier or by station (aggregate to carrier if needed).
   This solve is the primary calibration starting point. All before/after deltas are measured
   from it, not from the no-availability smoke solve.

3. **Diagnostic cross-check — pypsa-rsa station-level EAF**
   Compare the aggregate-EAF solve against pypsa-rsa's `plant_availability.xlsx` station-level
   EAF values. This is a diagnostic, not a mandatory calibration step.

4. **Upgrade to station-level EAF** (only if step 2 fails Stage 3 validation gates)
   If the aggregate carrier-level EAF cannot reproduce 2023 dispatch within tolerance, upgrade
   to station-level `p_max_pu` per generator row using pypsa-rsa's `plant_availability.xlsx`.

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
results/za_2023_fixed/networks/elec_s_34_ec_lc1_Co2L0.nc
doc/za_2023_dispatch_calibration_report.md
```

The path above locks the validation wildcards to `clusters: 34`, `ll: c1`, and
`opts: Co2L0` for the thesis handoff run. Smoke runs may use different concrete
wildcards, but they must record the exact solved-network path.

## Acceptance Gates

- Solved network output exists for the selected spatial level.
- Annual validation table is produced.
- Load shedding energy and hours are reported against `MLR + ILS + IOS`.
- Every calibration constraint is justified by a validation failure.
- Interim before/after calibration report is written before final acceptance.
- No expansion capacity appears in solved results.
