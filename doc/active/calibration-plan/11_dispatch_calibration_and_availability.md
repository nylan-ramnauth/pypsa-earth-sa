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
Sasol annual energy caps
hydro/PHS energy constraints
overgeneration slack only if infeasible overgeneration remains after renewable
  curtailment and PHS/hydro checks
linearized unit commitment (last-resort dispatch-only; not V1 unless Stage 3
  fails after earlier constraints)
reserve constraints (dispatch-validation only; no interaction with the
  reliability slack penalty owned by doc/active/reliability-plan/)
```

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
