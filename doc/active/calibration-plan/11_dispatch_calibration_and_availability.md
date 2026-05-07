# 11 Dispatch Calibration And Availability

## Goal

Solve the fixed 2023 network and add the minimum availability/outage/operational
constraints needed for an interpretable match to Eskom 2023 dispatch.

## Solve Target

Final validation solve uses Gurobi. HiGHS results are smoke/comparison only.
Use the Gurobi options locked in the `01` ZA overlay; do not override `Method`,
`Crossover`, `BarConvTol`, `Threads`, or `Seed` for the final solve.

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

## Calibration Order

1. Solve with basic fixed fleet and load shedding.
2. Compare annual generation, renewable output, load shedding, imports/exports.
3. Add aggregate thermal availability diagnostic or constraint from Eskom
   `PCLF`, `UCLF`, and `OCLF`.
4. Compare with PyPSA-RSA `plant_availability.xlsx` station EAF assumptions.
5. Move to station-level `p_max_pu` only if aggregate availability cannot
   explain the observed 2023 dispatch/load-shedding behavior.
6. Add operational constraints only when this module's interim calibration
   diagnostics show a concrete failure they address.

This module must produce its own interim before/after calibration report. The
final validation report in `12_validation_reporting_and_acceptance.md` is not
the first source of validation evidence.

Availability default:

```text
EAF = 1 - (Total PCLF + Total UCLF+OCLF)
```

`Total UCLF+OCLF` and `Total PCLF` are the exact Eskom columns repaired and
validated by module `02`.

Pre-flight must inspect `data/eaf_weekly.csv` and `data/nuclear_p_max_pu.csv`.
V1 default is to disable both because the cleaned Eskom EAF takes precedence;
if either file is retained, document the reason and the affected carriers in
the interim calibration report.

The first pass reports monthly carrier-level EAF diagnostics. A binding
carrier-level `p_max_pu = monthly_EAF` constraint may be enabled only when the
unconstrained solve fails Stage 3-relevant dispatch/load-shedding checks.
Station-level `p_max_pu` from `plant_availability.xlsx` is used only if the
aggregate EAF diagnostic cannot explain the observed 2023 dispatch behavior.

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
