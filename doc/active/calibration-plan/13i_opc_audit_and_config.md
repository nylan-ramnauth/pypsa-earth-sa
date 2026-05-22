# Module 13i Handoff - OPC Audit and Configurable Implementation

**Target agent:** Codex xhigh or equivalent standalone implementation agent  
**Working directory (Earth):** `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth`  
**Working directory (RSA reference, read-only):** `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-rsa`  
**Conda environment:** `pypsa-earth`  
**Solver:** Gurobi  
**Formulation:** LP relaxation / linearised UC only, not MILP

## Summary

Module 13h is accepted for coal dispatch calibration. The current `EAF-UC` case gets coal close to Eskom on the coal diagnostic, but it exposes a scarcity-composition problem:

- coal dispatch is good
- OCGT dispatch is too high
- load shedding is too low

Module 13i audits the operational-constraints workbook behavior and implements or corrects the equivalent PyPSA-Earth behavior as a configurable module.

This module is about OPC semantics only. Do not implement or change the annual OCGT / scarcity cap here; that is Module 13j.

Critical grounding from the local benchmark audit: the project-local `S_2023BM` row selects `operational_limits = NO_MIN_GAS`, not `HIGH_GAS`. Therefore the default 2023 OPC scenario should use `NO_MIN_GAS`. `LOW_GAS` and `HIGH_GAS` may be exposed as sensitivity scenarios, but they must not be presented as the selected 2023 baseline setting.

## Implementation Result — 2026-05-16

Module 13i was implemented and accepted with limitation.

- `za_operational_constraints` is now an explicit root-level config block with `enable`, `scenario`, and `model_year`.
- The default 2023 scenario is `NO_MIN_GAS`; OPC is independent from Module 13j CAP.
- `scripts/za_fleet/operational_constraints.py` now reads the Benchmark 2023 operational-constraints workbook by explicit scenario and model year, applies matching Generator constraints, preserves marginal costs, and writes per-row/per-generator audit records.
- Corrected boundary: all `output_energy` / `year` / `max` rows are audit-only in Module 13i with reason `skipped_delegated_to_module_13j`. Module 13j owns explicit annual per-carrier generation caps, including the Eskom 2023 OCGT target `ocgt_diesel: 5.243`.
- Snakemake exposes three labelled OPC solves: `EAF-UC-OPC-NO-MIN-GAS`, `EAF-UC-OPC-LOW-GAS`, and `EAF-UC-OPC-HIGH-GAS`.
- The dispatch calibration notebook was updated and rerun with all three OPC cases.

Accepted baseline classification:

- `EAF-UC-OPC-NO-MIN-GAS` is the workbook-grounded 2023 calibrated baseline.
- It preserves the accepted Module 13h coal behavior: coal `171.962 TWh`, coal hourly Pearson r `0.598`, July coal MAE `1,339 MW`, July coal bias `+1,183 MW`.
- It does not fix scarcity composition because, in the current Earth carrier set, the active `NO_MIN_GAS` non-cap rows only match `nuclear`; `ccgt_steam` and `rmippp` are absent, while the annual Sasol cap rows are delegated to Module 13j.
- `LOW_GAS` and `HIGH_GAS` solved optimal and are retained only as sensitivity/counterfactual cases. With annual cap rows delegated, both apply nuclear plus the weekly OCGT max-CF row and both dispatch OCGT `14.934 TWh` with load shedding `17.499 TWh`.

## Objective

The objective is to build the main calibrated 2023 baseline against Eskom actual operations.

For this baseline, follow the selected project-local `S_2023BM` setup as closely as possible, while Module 13k separately audits which inputs are truly sourced to 2023 observations:

- 2023 actual demand and validation year
- Module 13f demand alignment
- Module 13g.2 coal fleet disaggregation
- Module 13h coal linearised UC
- `rsa_eaf_projected` / `EAF_48` coal availability
- `operational_limits = NO_MIN_GAS`

The target baseline scenario name is:

- `EAF-UC-OPC-NO-MIN-GAS`

This is the candidate to report as the most defensible 2023 calibrated baseline if it solves cleanly and preserves the Module 13h coal improvement. Do not include `LOW_GAS`, `HIGH_GAS`, or an OCGT annual cap in the primary baseline unless the project explicitly decides to use a sensitivity or counterfactual operational constraint.

## Current Grounding

Accepted Module 13h `EAF-UC` metrics:

- coal: `171.962 TWh`
- OCGT: `27.441 TWh`
- load shedding: `6.051 TWh`
- coal hourly Pearson r: `0.598`
- July coal MAE: `1,339 MW`
- July coal bias: `+1,183 MW`

Eskom reference values from the validation notebook:

- coal: `165.627 TWh`
- OCGT: `5.243 TWh`
- load shedding: `16.755 TWh`

Interpretation:

- Coal is calibrated well enough for Module 13h acceptance.
- The remaining issue is scarcity composition.
- OPC must be audited before further tuning.
- The selected project-local 2023 baseline operational-limits scenario is `NO_MIN_GAS`.
- `LOW_GAS` and `HIGH_GAS` are different workbook scenarios and should be treated as sensitivity cases, not the main 2023 baseline setting.

## 2023 OPC Grounding

From the project-local file `scenarios/Benchmark_2023/scenarios_to_run.xlsx`, scenario `S_2023BM`:

```text
simulation_years = list(range(2023,2024))
operational_limits = NO_MIN_GAS
unit_committment = True
override_coal_msl = 0.7
coal_ramp_rate_multiplier = 1.5
```

From `scenarios/Benchmark_2023/sub_scenarios/operational_constraints.xlsx`, sheet `operational_constraints`, the active 2023 `NO_MIN_GAS` rows are:

| Carrier/resource | Constraint | Period | Apply to | Unit | 2023 value |
|---|---|---|---|---|---:|
| `ccgt_steam` | minimum capacity factor | month | all | `%` | `0.3` |
| `nuclear` | minimum capacity factor | hour | all | `%` | `1.0` |
| `rmippp` | minimum capacity factor | month | fixed | `%` | `0.5` |
| `sasol_coal` | maximum output energy | year | fixed | `TWh` | `5.5` |
| `sasol_gas` | maximum output energy | year | fixed | `TWh` | `2.8` |

The active 2023 `NO_MIN_GAS` rows do not include an annual `ocgt_diesel` cap.

`LOW_GAS` differs. Its 2023 rows include the same broad nuclear/Sasol/CCGT-style constraints, but also include:

| Carrier/resource | Constraint | Period | Apply to | Unit | 2023 value |
|---|---|---|---|---|---:|
| `ocgt_diesel + ocgt_avf` | maximum capacity factor | week | all | `%` | `0.5` |

`HIGH_GAS` contains the same weekly gas-sensitivity row plus an annual cap row. In Module 13i, only the weekly row is applied; the annual cap row is audited and delegated to Module 13j:

| Carrier/resource | Constraint | Period | Apply to | Unit | 2023 value | Module 13i handling |
|---|---|---|---|---|---:|---|
| `ocgt_diesel + ocgt_avf` | maximum capacity factor | week | all | `%` | `0.5` | applied |
| `ocgt_diesel` | maximum output energy | year | all | `TWh` | `5.5` | audit-only; delegated to Module 13j |

Therefore, for the main 2023 calibration baseline, use `NO_MIN_GAS` as the default scenario. Use `LOW_GAS` and `HIGH_GAS` as labelled OPC sensitivity/audit cases. Under the corrected 13i boundary, `HIGH_GAS` should match `LOW_GAS` in dispatch because its explicit annual generation cap is not applied until Module 13j. Do not label either sensitivity as the selected 2023 baseline setting.

Do not prioritize these scenarios for the clean 2023 baseline unless the user explicitly asks:

- `NO_GAS`
- `HIGH_GAS_D`
- `LOW_GAS_D`
- `DLY_LOW_GAS_D`
- `P1_FUEL_SWITCH`
- `P1_FUEL_SWITCH_DISPATCH`
- `ignore`

For 2023 in the current Earth model, `NO_GAS` / `*_GAS_D` appear unlikely to add useful information beyond `NO_MIN_GAS` because the gas/Sasol/CCGT/RMIPPP carriers mostly do not exist. `P1_FUEL_SWITCH*` are broader policy/future-style stress cases and should be deferred unless needed for expansion-scenario design.

## Scope

Preserve Module 13h behavior unless an OPC interaction bug is found.

Do not change:

- coal plant `p_nom` sources
- coal bus mapping
- Hendrina split logic
- `rsa_eaf_projected` availability semantics
- coal UC `p_min_pu`, ramp, startup/shutdown, or linearized UC behavior
- final validation notebook / HTML / report exports

Do not tune blindly. First establish what the selected workbook rows actually do in PyPSA-Earth.

## Main Questions

1. What do the operational-constraints workbook rows actually mean in the local benchmark setup?
2. Can PyPSA-Earth reproduce the selected `NO_MIN_GAS` operational-limit rows for model year 2023?
3. Does PyPSA-Earth currently reproduce `NO_MIN_GAS`, or did earlier `EAF-OPC` behavior accidentally use `LOW_GAS` / `HIGH_GAS` / OCGT-cap semantics?
4. Is OPC only applied to gas / OCGT, or does the selected scenario also affect nuclear, RMIPPP, Sasol coal/gas, CCGT steam, reserves, imports, storage, hydro, or other resources?
5. Can the selected operational-limits scenario be configured explicitly?
6. Can sensitivity scenarios `LOW_GAS` and `HIGH_GAS` be run using the same implementation without changing code?
7. Can OPC be enabled independently from the OCGT / scarcity cap?
8. Can OPC be applied on top of Module 13h coal UC without damaging coal dispatch?

## Source Workbook Audit Tasks

In `6-codebases/repos/pypsa-rsa`, search for:

- `OPC`
- `OCGT`
- `gas`
- `diesel`
- `peaker`
- `load shedding`
- `load_shedding`
- `marginal_cost`
- `scarcity`
- `reserve`
- `constraint`
- `annual`

Identify whether the source implementation changes or constrains:

- OCGT marginal costs
- load-shedding marginal costs
- diesel / gas peaker treatment
- reserve or adequacy constraints
- imports / exports
- hydro / storage behavior
- coal costs or coal commitment behavior
- only costs, only constraints, or both

Specifically compare `NO_MIN_GAS`, `LOW_GAS`, and `HIGH_GAS`, but treat `NO_MIN_GAS` as the default 2023 baseline target.

Record exact source files and line references.

## PyPSA-Earth Audit Tasks

In `6-codebases/repos/pypsa-earth`, locate the current OPC-related implementation used by previous plotted scenarios:

- `EAF-OPC`
- `EAF-OPC-CAP`

Check:

- whether OPC is hard-coded or configurable
- whether it only affects gas / OCGT
- whether it changes marginal costs or adds constraints
- whether it reproduces `NO_MIN_GAS` by default
- whether any previous OPC case used `LOW_GAS` or `HIGH_GAS` assumptions
- whether it applies before or after coal UC attachment
- whether it works with `linearized_unit_commitment=True`
- whether it accidentally affects coal, load shedding, or non-target generators
- whether previous OPC behavior is still valid after Module 13h

## Required Config Design

Add a minimal explicit config block in `configs/za/za_2023_fixed_validation.yaml`.

The public config surface should contain only the choices needed to run the same model with different operational-limit scenarios:

```yaml
za_operational_constraints:
  enable: false
  # scenario options for 2023 calibration:
  # Source table: scenarios/Benchmark_2023/sub_scenarios/operational_constraints.xlsx
  # Packaged Earth copy after Module 13l: data/za_reference/pypsa_rsa_benchmark_2023/sub_scenarios/operational_constraints.xlsx
  # NO_MIN_GAS = selected 2023 baseline setting; no direct OCGT cap in the current Earth model
  # LOW_GAS = sensitivity; adds weekly OCGT max-capacity-factor limits
  # HIGH_GAS = sensitivity; annual max output rows are audited here and delegated to Module 13j
  # This is the canonical selector for config-driven OPC solves. The labelled
  # Snakemake comparison outputs `...-OPC-{NO-MIN-GAS,LOW-GAS,HIGH-GAS}.nc`
  # override only this field from the wildcard so the filename and audit scenario
  # cannot drift from each other.
  scenario: NO_MIN_GAS
  # Selects the year-specific values from the operational-constraints table.
  # For 2023 this is a historical calibration selector; for 2030+ it is a scenario-assumption selector.
  model_year: 2023
```

Do not expose implementation details such as `mode`, `source`, `workbook`, `selected_rows`, `audit`, `fail_on_missing_rows`, or marginal-cost override fields in the normal calibration config unless the audit proves they are necessary. The intended user workflow is simple:

```yaml
za_operational_constraints:
  enable: true
  scenario: NO_MIN_GAS
  model_year: 2023
```

To run sensitivities, keep the model fixed and swap only `scenario`:

```yaml
za_operational_constraints:
  enable: true
  scenario: LOW_GAS
  model_year: 2023
```

```yaml
za_operational_constraints:
  enable: true
  scenario: HIGH_GAS
  model_year: 2023
```

The implementation should use internal defaults:

- operational-constraints source: the packaged Earth copy at `data/za_reference/pypsa_rsa_benchmark_2023/sub_scenarios/operational_constraints.xlsx` after Module 13l, or the current local RSA reference path only until packaging is complete
- selected rows: all rows matching `scenario` and `model_year`
- `model_year` must actively select the year-specific values from the source table; changing it from `2023` to `2030` should change constraints when the source table has different 2030 values
- audit: always write the audit table when OPC is enabled
- fail behavior: fail if the requested scenario/year is absent or if selected rows cannot be interpreted
- marginal-cost overrides: disabled unless an audited source requires them

Requirements:

- `za_operational_constraints.enable: false` must preserve current Module 13h behavior exactly.
- The selected operational-limits scenario must be explicit in config.
- The default 2023 baseline scenario must be `NO_MIN_GAS`.
- `LOW_GAS` and `HIGH_GAS` must require only an explicit `scenario` change and should be treated as sensitivity/counterfactual unless the user intentionally changes the benchmark target.
- OPC must be independently toggleable from Module 13j CAP.
- OPC must not require CAP to be enabled.
- The implementation must support all selected operational-limit rows, not only gas/OCGT.
- Any marginal-cost overrides must come from audited RSA-derived data, not hard-coded constants.
- The implementation must write an audit table showing which workbook rows were selected, which generators/resources were affected, and why.

Suggested audit output:

- `data/za_validation/za_opc_audit.csv`

Suggested audit fields:

- `operational_limits_scenario`
- `model_year`
- `workbook_row_id`
- `component`
- `name`
- `carrier`
- `bus`
- `p_nom`
- `constraint_type`
- `period`
- `limit`
- `apply_to`
- `units`
- `rhs_value`
- `old_marginal_cost`
- `new_marginal_cost`
- `affected_by_opc`
- `reason`
- `source`

## Implementation Boundary

Prefer a small ZA-specific helper path rather than changing generic PyPSA-Earth behavior.

Likely files to inspect or modify:

- `scripts/solve_network.py`
- existing ZA operational-constraint helper scripts, if present
- `configs/za/za_2023_fixed_validation.yaml`
- `Snakefile`, only if a new explicit rule or output is required

Do not edit unless clearly required:

- `scripts/add_electricity.py`
- `scripts/za_fleet/apply_coal_eaf.py`
- Module 13g.2 coal disaggregation logic
- Module 13h coal UC logic

## Validation Modes

Run at least two modes:

### 1. Baseline

Scenario name:

- `EAF-UC`

Settings:

- coal disaggregation enabled
- `availability_mode: rsa_eaf_projected`
- coal UC enabled
- OPC disabled
- CAP disabled

Expected approximate baseline:

- coal: `171.962 TWh`
- OCGT: `27.441 TWh`
- load shedding: `6.051 TWh`
- coal hourly Pearson r: `0.598`

### 2. OPC-Only Diagnostic

Scenario name:

- `EAF-UC-OPC-NO-MIN-GAS`

Settings:

- coal disaggregation enabled
- `availability_mode: rsa_eaf_projected`
- coal UC enabled
- OPC enabled
- `za_operational_constraints.scenario: NO_MIN_GAS`
- CAP disabled

Interpretation:

- primary 2023 calibrated baseline candidate
- selected 2023 baseline operational-limits scenario
- most defensible baseline before moving to expansion modelling

Recommended sensitivity ladder after the baseline run:

#### Sensitivity 1: LOW_GAS

- `EAF-UC-OPC-LOW-GAS`
- `za_operational_constraints.scenario: LOW_GAS`

Interpretation:

- first OCGT sensitivity
- adds weekly max CF `0.5` for `ocgt_diesel + ocgt_avf`
- does not add the annual 5.5 TWh `ocgt_diesel` cap
- useful as an intermediate case: limits OCGT intensity without imposing an annual fuel/energy budget

#### Sensitivity 2: HIGH_GAS

- `EAF-UC-OPC-HIGH-GAS`
- `za_operational_constraints.scenario: HIGH_GAS`

Interpretation:

- adds weekly max CF `0.5` for `ocgt_diesel + ocgt_avf`
- audits, but does not apply, annual max output rows such as `ocgt_diesel <= 5.5 TWh/year`
- expected to match `LOW_GAS` dispatch under Module 13i; the explicit annual cap is Module 13j's responsibility

Do not label `LOW_GAS` or `HIGH_GAS` as the selected 2023 baseline setting.

Report:

- solve status
- coal TWh
- OCGT TWh
- load shedding TWh
- OCGT + load shedding TWh
- coal hourly Pearson r
- coal weekly Pearson r
- July coal MAE
- July coal bias
- whether Gurobi remains LP-only
- whether this should replace `EAF-UC` as the final 2023 calibrated baseline

## Required Checks

For any OPC-enabled solve:

- coal UC remains active
- all coal rows remain committable
- non-coal rows are not accidentally made committable
- `linearized_unit_commitment=True` is still used
- Gurobi log has no MIP / branch-and-bound / MIP gap output
- total load is unchanged
- OPC audit table is populated
- OPC selected scenario is recorded in the audit
- default baseline run uses `NO_MIN_GAS`
- sensitivity runs explicitly record `LOW_GAS` or `HIGH_GAS`
- affected-resource set matches the selected operational-limits rows or deviations are explicitly documented

## Acceptance Criteria

Accept Module 13i if:

- OPC behavior follows the selected `NO_MIN_GAS` workbook rows when configured with `scenario: NO_MIN_GAS`, or differences are explicitly documented and justified.
- OPC is fully configurable through `configs/za/za_2023_fixed_validation.yaml`.
- OPC scenario selection is explicit and defaults to `NO_MIN_GAS` for the 2023 baseline.
- OPC is independently toggleable from Module 13j CAP.
- OPC disabled reproduces Module 13h behavior.
- OPC enabled does not damage accepted coal UC behavior.
- The affected generator/resource set is audited.
- Xhigh has checked whether the source implementation includes resources beyond gas/OCGT.
- Any `LOW_GAS` or `HIGH_GAS` run is clearly labelled sensitivity/counterfactual, not the selected 2023 baseline setting.
- `EAF-UC-OPC-NO-MIN-GAS` is clearly classified as accepted baseline, accepted-with-limitation, or rejected/blocking based on validation metrics.

Reject or diagnose if:

- OPC is just an arbitrary tuning layer without workbook grounding.
- OPC silently uses `LOW_GAS` or `HIGH_GAS` while claiming the `NO_MIN_GAS` baseline.
- OPC damages coal dispatch without a clear workbook-grounded reason.
- OPC cannot be separated cleanly from CAP.
- The affected generator set cannot be audited.

## Expected Outcome

The likely durable result is one of:

1. **OPC workbook behavior confirmed**
   - PyPSA-Earth OPC already matches the selected workbook rows or is corrected to match them.

2. **OPC implementation bug found**
   - Correct the implementation, rerun the OPC-only diagnostic, and document the correction.

3. **Additional source behavior found**
   - Implement the additional resource treatment behind config if it is relevant to the 2023 benchmark.

4. **OPC not sufficient alone**
   - Keep Module 13h accepted, keep `EAF-UC-OPC-NO-MIN-GAS` as the main 2023 baseline if it is structurally valid, and proceed to Module 13j only as a diagnostic/counterfactual scarcity-composition investigation.

5. **Accepted calibrated baseline**
   - `EAF-UC-OPC-NO-MIN-GAS` preserves the Module 13h coal improvement, applies the selected operational-limit rows, and becomes the main 2023 calibrated baseline for reporting. Any remaining OCGT/load-shedding mismatch should be reported as a limitation rather than silently corrected with `LOW_GAS` or `HIGH_GAS`.

6. **Sensitivity ladder completed**
   - After the accepted baseline, `EAF-UC-OPC-LOW-GAS` and `EAF-UC-OPC-HIGH-GAS` are run and reported as labelled workbook sensitivities. They should show which rows Module 13i applies and which annual-cap rows are delegated while preserving coal calibration.
   - Under the corrected Module 13i boundary, `LOW_GAS` and `HIGH_GAS` should have the same applied OCGT constraint set; any stronger annual cap behavior belongs in Module 13j.

## Notebook Update Requirement

After Module 13i solves are complete and the three OPC cases are available, update and rerun:

- `notebooks/za_validation/12_dispatch_calibration/dispatch_calibration_validation.ipynb`

Update the existing scenario list, plots, and summary tables. Do not add a new notebook section. Replace the old single `OPC` scenario with three explicit OPC scenarios:

- `EAF-UC-OPC-NO-MIN-GAS`
- `EAF-UC-OPC-LOW-GAS`
- `EAF-UC-OPC-HIGH-GAS`

The rerun notebook should allow direct comparison against:

- `STOCK`
- `NoCO2`
- `EAF-UC`
- `EAF-UC-OPC-NO-MIN-GAS`
- `EAF-UC-OPC-LOW-GAS`
- `EAF-UC-OPC-HIGH-GAS`
- `EAF-UC-...-CAP-...` after Module 13j is implemented
- `RSA-BM` / RSA reference, if the local reference output is available

The notebook tables and existing dispatch plots must include the three OPC cases separately so the effect of changing only `za_operational_constraints.scenario` is visible.

## Continuity

Do not refresh final HTML / report exports unless Module 13i is accepted or explicitly rejected. The dispatch calibration notebook above should be updated and rerun once the Module 13i OPC runs are complete.

Update after validation:

- `doc/za_implementation_log.md`
- vault `_status.md` and `_todo.md` only if Module 13i reaches accepted or blocked state
- shared log if canonical state changes
- personal log for the work session

Preserve existing dirty worktree changes. Do not revert unrelated modified or untracked files.
