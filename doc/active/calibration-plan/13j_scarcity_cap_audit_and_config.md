# Module 13j Handoff - OCGT / Scarcity CAP Audit and Configurable Implementation

**Target agent:** Codex xhigh or equivalent standalone implementation agent
**Working directory (Earth):** `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth`
**Working directory (RSA reference, read-only):** `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-rsa`
**Conda environment:** `pypsa-earth`
**Solver:** Gurobi
**Formulation:** LP relaxation / linearised UC only, not MILP

## Summary

**Implementation status (2026-05-16 02:04):** configurable CAP wiring is implemented, the requested `NO_MIN_GAS + CAP` and `LOW_GAS + CAP` diagnostics solved optimal, and the dispatch notebook/HTML exports were refreshed. The default config still keeps CAP disabled. CAP remains a labelled diagnostic/counterfactual, not the selected `S_2023BM` parity baseline.

Module 13h is accepted for coal dispatch calibration. The current `EAF-UC` case gets coal close to Eskom and outperforms RSA-BM on the coal diagnostic, but it exposes a scarcity-composition problem:

- coal dispatch is good
- OCGT dispatch is too high
- load shedding is too low

Module 13j audits and implements a configurable annual generation cap separately from OPC.

This module should test whether a CAP can reduce the current overuse of OCGT without damaging the accepted coal calibration, while explicitly diagnosing the expected side effect: because the current Earth model still under-produces VRE and some other non-coal energy sources, an OCGT cap will probably shift unmet energy into load shedding rather than fully "fix" scarcity composition.

Module 13i handles OPC cost/operational-constraint semantics. This module handles direct annual generation caps for selected technologies/carriers.

Critical grounding from the RSA audit: `S_2023BM` selects `operational_limits = NO_MIN_GAS`, and the active 2023 `NO_MIN_GAS` rows do not include an annual OCGT diesel cap. The 5.5 TWh `ocgt_diesel` cap appears in the `HIGH_GAS` operational-limits scenario, not in the selected RSA-BM 2023 setting. Therefore, any direct OCGT cap must be configurable and labelled diagnostic/counterfactual unless the benchmark target is intentionally changed.

## Objective

Module 13j is not the first-choice baseline implementation.

The main 2023 calibrated baseline should be developed first through Module 13i:

- `EAF-UC-OPC-NO-MIN-GAS`
- coal UC enabled
- RSA-BM `S_2023BM` operational-limits scenario
- no hidden `HIGH_GAS` OCGT cap

Module 13j should be used only after Module 13i if the team wants a transparent calibration test or counterfactual that asks:

> What would happen if the 2023 calibrated UC baseline also capped OCGT annual generation at Eskom's observed 2023 OCGT generation?

The CAP can improve visual/metric alignment with Eskom OCGT and may improve load-shedding magnitude. It may also reveal a structural energy deficit: if VRE remains too low, the model has less non-scarcity energy available, so capping OCGT can raise load shedding too much. It should not be reported as the main RSA-BM parity baseline unless the project explicitly decides that the baseline should include an additional direct generation cap beyond `S_2023BM`.

## Current Grounding

Accepted Module 13h `EAF-UC` metrics:

- coal: `171.962 TWh`
- OCGT: `27.441 TWh`
- load shedding: `6.051 TWh`
- coal hourly Pearson r: `0.598`
- July coal MAE: `1,339 MW`
- July coal bias: `+1,183 MW`

Corrected Module 13i metrics after delegating annual output-energy caps to Module 13j:

- `EAF-UC-OPC-NO-MIN-GAS`
  - coal: `171.962 TWh`
  - OCGT: `27.441 TWh`
  - load shedding: `6.051 TWh`
  - coal hourly Pearson r: `0.598`
- `EAF-UC-OPC-LOW-GAS`
  - coal: `172.670 TWh`
  - OCGT: `14.934 TWh`
  - load shedding: `17.499 TWh`
  - coal hourly Pearson r: `0.616`

After the Module 13i boundary correction, `HIGH_GAS` without Module 13j CAP is identical to `LOW_GAS` in the current Earth model. The notebook should therefore keep `LOW_GAS` as the single OPC sensitivity until Module 13j adds an explicit cap.

Eskom reference values from the validation notebook:

- coal: `165.627 TWh`
- OCGT: `5.243 TWh`
- load shedding: `16.755 TWh`

Validated Module 13j diagnostic results from the 2026-05-16 run:

| Scenario | Coal TWh | OCGT TWh | Load shedding TWh | OCGT + load shedding TWh | Coal hourly r | Result |
|---|---:|---:|---:|---:|---:|---|
| `EAF-UC-OPC-NO-MIN-GAS` | `171.962` | `27.441` | `6.051` | `33.492` | `0.598` | workbook-grounded baseline |
| `EAF-UC-OPC-NO-MIN-GAS-CAP-OCGT-ESKOM2023` | `172.723` | `5.243` | `27.137` | `32.380` | `0.615` | diagnostic; cap works but over-raises shedding |
| `EAF-UC-OPC-LOW-GAS` | `172.670` | `14.934` | `17.499` | `32.433` | `0.616` | OPC sensitivity closest to Eskom shedding |
| `EAF-UC-OPC-LOW-GAS-CAP-OCGT-ESKOM2023` | `172.723` | `5.243` | `27.137` | `32.380` | `0.615` | diagnostic; same aggregate result as `NO_MIN_GAS + CAP` |

CAP audit outcome:

- both CAP diagnostics include exactly five `ocgt_diesel` generators
- both bind at `5.243000 TWh` with zero material slack
- total load is unchanged at `225.874862 TWh`
- coal UC remains active with 16/16 coal rows committable and 0 non-coal rows committable
- Gurobi logs are LP/barrier only; no MIP, branch-and-bound, or MIP-gap output was found

Interpretation:

- The CAP implementation is mechanically sound.
- The annual OCGT cap does not solve the scarcity-composition problem because it mostly converts OCGT energy into load shedding.
- `LOW_GAS` remains the better scarcity-composition sensitivity if the project wants a diagnostic close to Eskom load-shedding magnitude.
- The source-selected 2023 baseline remains `EAF-UC-OPC-NO-MIN-GAS` without a hidden annual OCGT cap.

Previous pre-13h CAP behavior:

- `EAF-OPC-CAP` improved OCGT magnitude but did not include the accepted Module 13h coal UC behavior.
- The old CAP case should not be assumed valid for the current UC candidate without re-audit.

Interpretation:

- Coal is calibrated well enough for Module 13h acceptance.
- The remaining issues are scarcity composition and missing non-scarcity energy.
- `LOW_GAS` improves load shedding magnitude but OCGT remains too high at `14.934 TWh`.
- Earth VRE generation is still materially low in the current notebook:
  - wind: `7.312 TWh` vs Eskom `11.613 TWh`
  - solar PV: `3.625 TWh` vs Eskom `5.015 TWh`
  - CSP: `0.806 TWh` vs Eskom `1.375 TWh`
- A CAP may be needed as a transparent diagnostic, but it may mostly convert remaining OCGT into load shedding because VRE and other supply remain underproduced.
- Apply the CAP only after the capped resource set and units are verified.
- For realistic 2023 RSA-BM parity, do not silently use `HIGH_GAS`.
- For 2030+ expansion experiments, it may be useful to relax, switch, or explicitly choose a different operational-limits scenario, but that must be visible in config and reporting.

## RSA 2023 CAP Grounding

From `scenarios/Benchmark_2023/scenarios_to_run.xlsx`, scenario `S_2023BM`:

```text
simulation_years = list(range(2023,2024))
operational_limits = NO_MIN_GAS
```

From `scenarios/Benchmark_2023/sub_scenarios/operational_constraints.xlsx`, sheet `operational_constraints`:

- `NO_MIN_GAS` is the active RSA-BM 2023 operational-limits scenario.
- `NO_MIN_GAS` has no 2023 annual `ocgt_diesel` cap.
- `HIGH_GAS` includes a 2023 annual `ocgt_diesel` cap of `5.5 TWh`.
- `HIGH_GAS` also includes a weekly maximum capacity-factor row for `ocgt_diesel + ocgt_avf` of `0.5` in 2023.

Implication:

- A `NO_MIN_GAS` run is the realistic 2023 benchmark-parity setting.
- A `HIGH_GAS`-derived OCGT cap is a diagnostic/counterfactual scarcity-composition constraint unless the project deliberately chooses `HIGH_GAS` as the target scenario.
- Module 13j should support simple direct caps by config. The primary 2023 cap test should use Eskom observed OCGT generation from the validation notebook: `5.243 TWh`. The RSA `HIGH_GAS` `5.5 TWh` row is useful context because it is close, but it is not the primary calibration target.

## Scope

Preserve Module 13h behavior unless a CAP interaction bug is found.

Do not change during implementation:

- coal plant `p_nom` sources
- coal bus mapping
- Hendrina split logic
- `rsa_eaf_projected` availability semantics
- coal UC `p_min_pu`, ramp, startup/shutdown, or linearized UC behavior
- final validation notebook / HTML / report exports until the diagnostic result is classified; the 2026-05-16 run classified the CAP result as a diagnostic limitation and refreshed `dispatch_calibration_validation.ipynb` plus both HTML exports.

Do not tune blindly. First establish PyPSA-RSA parity or explicitly document that the CAP is a PyPSA-Earth diagnostic constraint.

## Main Questions

1. Does the selected RSA-BM 2023 scenario `NO_MIN_GAS` impose an annual OCGT cap? Current finding: no.
2. Which non-selected RSA operational-limits scenarios, especially `HIGH_GAS`, contain OCGT or scarcity CAP rows?
3. If a cap is used, what exact resource set is capped?
4. Is the cap based on OCGT generation only, diesel/peaker generation, gas plus diesel, OCGT plus load shedding, or another scarcity proxy?
5. Is the cap annual, monthly, weekly, or snapshot-weighted?
6. What is the target cap value and where does it come from?
7. Are units handled correctly in PyPSA-Earth?
8. Does the CAP still work with Module 13h coal UC and LP relaxation?
9. Does RSA include additional CAP-like constraints beyond gas/OCGT?
10. Should a CAP be retained, relaxed, or removed when moving from calibrated 2023 validation to 2030+ expansion scenarios?

## RSA CAP Audit Tasks

In `6-codebases/repos/pypsa-rsa`, search for:

- `OPC`
- `OCGT`
- `gas`
- `diesel`
- `peaker`
- `load shedding`
- `load_shedding`
- `annual`
- `cap`
- `constraint`
- `global_constraint`
- `snapshot_weightings`
- `primary_energy`
- `marginal_cost`

Identify:

- whether a custom annual energy constraint exists
- the exact carriers/generators/resources included
- target cap value and units
- whether snapshot weights are used
- whether the cap is scenario-specific
- whether the cap interacts with OPC prices
- whether the cap is limited to OCGT or includes additional scarcity resources
- whether the cap belongs to `NO_MIN_GAS`, `HIGH_GAS`, or another operational-limits scenario

Current known row to treat carefully:

| Scenario | Carrier/resource | Constraint | Period | Apply to | Unit | 2023 value | Parity status |
|---|---|---|---|---|---|---:|---|
| `HIGH_GAS` | `ocgt_diesel` | maximum output energy | year | all | `TWh` | `5.5` | diagnostic/counterfactual for `S_2023BM` |
| `HIGH_GAS` | `ocgt_diesel + ocgt_avf` | maximum capacity factor | week | all | `%` | `0.5` | diagnostic/counterfactual for `S_2023BM` |

These rows are useful precedents, but they are not active in `S_2023BM` unless the configured operational-limits scenario is changed.

Record exact source files and line references.

## PyPSA-Earth CAP Audit Tasks

In `6-codebases/repos/pypsa-earth`, inspect the current CAP implementation for previously plotted cases:

- `EAF-OPC-CAP`

Check:

- generator subset
- carrier names
- snapshot weighting
- unit conversions
- cap value source
- whether the cap is hard-coded
- whether the cap was copied from `HIGH_GAS`
- whether any previous run labelled `EAF-OPC-CAP` as RSA-BM parity even though it used a non-selected scenario row
- whether load shedding is accidentally included or excluded
- whether CAP can be enabled without OPC
- whether CAP survives the solve path with `linearized_unit_commitment=True`
- whether the old CAP implementation assumes pre-13h network structure

## Required Config Design

Add an explicit config block in `configs/za/za_2023_fixed_validation.yaml`.

The public config surface should be simple: enable the cap, select the model year, and provide a per-carrier annual cap directly in TWh.

```yaml
za_scarcity_cap:
  enable: false
  model_year: 2023
  # Generator carriers in the current accepted EAF-UC network:
  # coal, csp, load shedding, nuclear, ocgt_diesel, onwind, solar
  #
  # Full carrier table seen in the current network:
  # AC, PHS, battery, coal, csp, hydro, load shedding, nuclear,
  # ocgt_diesel, ocgt_gas, onwind, ror, solar
  #
  # The implementation must refresh/audit this list from the solved network
  # before applying caps.
  annual_generation_caps_twh:
    ocgt_diesel: 5.243
```

Different carriers must be able to have different caps:

```yaml
za_scarcity_cap:
  enable: true
  model_year: 2023
  annual_generation_caps_twh:
    ocgt_diesel: 5.243
    ocgt_gas: 1.0
```

Optional advanced fields should only be added if implementation requires them. If added, keep them secondary and defaulted:

```yaml
  include_generators: []
  exclude_generators: []
```

Do not expose implementation details such as workbook path, RSA source scenario, selected workbook rows, snapshot-weighting flags, audit flags, or benchmark opt-in flags in the normal calibration config. The implementation should use internal defaults:

- cap expression: one snapshot-weighted annual dispatch constraint per configured carrier in `annual_generation_caps_twh`
- audit: always write the audit table when CAP is enabled
- failure behavior: fail if no generators match a configured capped carrier, unless an explicit future advanced option says otherwise
- provenance: audit whether the chosen cap value comes from Eskom observed 2023 generation, a known RSA row such as `HIGH_GAS` `ocgt_diesel = 5.5 TWh`, or another explicitly stated source; do not require users to select RSA workbook rows

Requirements:

- `za_scarcity_cap.enable: false` must preserve current Module 13h behavior exactly.
- CAP must be independently toggleable from Module 13i OPC.
- CAP must not require OPC to be enabled.
- CAP targets must come from config, not hard-coded constants.
- CAP technology/carrier set must come from the keys of `annual_generation_caps_twh`.
- For `S_2023BM`, any direct OCGT cap should be labelled diagnostic/counterfactual because `NO_MIN_GAS` has no annual OCGT cap.
- The default canonical 2023 validation config should leave `za_scarcity_cap.enable: false` unless the human explicitly decides to make a diagnostic/counterfactual run active.
- CAP generator inclusion must be auditable.
- CAP should support multiple carriers with different cap values so future sensitivities can cap additional technologies without code changes.

Suggested audit output:

- `data/za_validation/za_scarcity_cap_audit.csv`

Suggested audit fields:

- `model_year`
- `component`
- `name`
- `carrier`
- `bus`
- `p_nom`
- `annual_dispatch_twh`
- `included_in_cap`
- `annual_generation_cap_twh`
- `reason`
- `source`
- `parity_status`

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

## Candidate Constraint Semantics

If the CAP is annual generation, it should be snapshot-weighted and unit-consistent.

Conceptually:

```text
sum_t sum_g dispatch[g, t] * snapshot_weight[t] <= cap_target_mwh
```

where `g` is the configured capped generator set.

Do not assume:

- one-hour snapshots unless verified
- carrier naming is identical between RSA and Earth
- OCGT is the only capped resource
- previous `EAF-OPC-CAP` code is still correct after Module 13h
- `HIGH_GAS` is the active RSA-BM 2023 scenario

## Validation Modes

Run at least three modes:

### 1. Baseline

Scenario name:

- `EAF-UC-OPC-NO-MIN-GAS`

Settings:

- coal disaggregation enabled
- `availability_mode: rsa_eaf_projected`
- coal UC enabled
- OPC enabled with Module 13i `NO_MIN_GAS` semantics
- CAP disabled

Expected corrected Module 13i baseline:

- coal: `171.962 TWh`
- OCGT: `27.441 TWh`
- load shedding: `6.051 TWh`
- coal hourly Pearson r: `0.598`

Interpretation:

- this is the main calibrated 2023 baseline candidate
- Module 13j diagnostics should compare against this scenario, not replace it silently

### 2. CAP-Only Diagnostic

Scenario name:

- `EAF-UC-CAP-OCGT-ESKOM2023`

Settings:

- coal disaggregation enabled
- `availability_mode: rsa_eaf_projected`
- coal UC enabled
- OPC disabled
- CAP enabled
- `za_scarcity_cap.annual_generation_caps_twh.ocgt_diesel: 5.243`, adjusted to actual Earth carrier names if needed

Interpretation:

- calibration diagnostic using Eskom observed 2023 OCGT generation as the annual cap
- not RSA-BM 2023 parity unless the project deliberately changes the benchmark scenario from `NO_MIN_GAS` to `HIGH_GAS`
- expected risk: OCGT falls toward `5.243 TWh`, but load shedding may rise sharply because this mode has no `LOW_GAS` weekly OCGT operational limit and the model still under-produces VRE

### 3. Baseline OPC + CAP Diagnostic

Scenario name:

- `EAF-UC-OPC-NO-MIN-GAS-CAP-OCGT-ESKOM2023`

Settings:

- coal disaggregation enabled
- `availability_mode: rsa_eaf_projected`
- coal UC enabled
- OPC enabled with Module 13i `NO_MIN_GAS` semantics
- CAP enabled
- `za_scarcity_cap.annual_generation_caps_twh.ocgt_diesel: 5.243`, adjusted to actual Earth carrier names if needed

Interpretation:

- tests the source-selected `NO_MIN_GAS` OPC baseline with one transparent additional annual OCGT cap
- expected risk: the cap may mostly replace OCGT with load shedding rather than improving the underlying energy balance

### 4. LOW_GAS OPC + CAP Diagnostic

Scenario name:

- `EAF-UC-OPC-LOW-GAS-CAP-OCGT-ESKOM2023`

Settings:

- coal disaggregation enabled
- `availability_mode: rsa_eaf_projected`
- coal UC enabled
- OPC enabled with Module 13i `LOW_GAS` semantics
- CAP enabled
- `za_scarcity_cap.annual_generation_caps_twh.ocgt_diesel: 5.243`, adjusted to actual Earth carrier names if needed

Interpretation:

- this is the most important 13j diagnostic after the corrected notebook result
- `LOW_GAS` already gets load shedding close to Eskom (`17.499 TWh` vs `16.755 TWh`) but leaves OCGT too high (`14.934 TWh` vs `5.243 TWh`)
- adding the OCGT cap may over-correct scarcity by raising load shedding well above Eskom if missing VRE/non-coal energy is the real residual problem
- compare this directly against `EAF-UC-OPC-LOW-GAS`, not only against `NO_MIN_GAS`

Optional additional mode:

- `EAF-UC-OPC-LOW-GAS-CAP-OCGT-RSA-HIGH-GAS-5P5`
- same as the LOW_GAS + CAP diagnostic, but use `ocgt_diesel: 5.5` TWh to reproduce the magnitude of the RSA `HIGH_GAS` annual cap row through Module 13j
- label this as a sensitivity/counterfactual, not the selected `S_2023BM` baseline

Report for each mode:

- solve status
- coal TWh
- OCGT TWh
- load shedding TWh
- OCGT + load shedding TWh
- total physical generation TWh
- VRE TWh by wind, solar PV, and CSP
- coal hourly Pearson r
- coal weekly Pearson r
- July coal MAE
- July coal bias
- scarcity weekly Pearson r if available
- whether Gurobi remains LP-only

## Required Checks

For any CAP-enabled solve:

- coal UC remains active
- all coal rows remain committable
- non-coal rows are not accidentally made committable
- `linearized_unit_commitment=True` is still used
- Gurobi log has no MIP / branch-and-bound / MIP gap output
- CAP constraint is active
- capped generation respects the configured cap
- total load is unchanged
- CAP audit table is populated
- cap carrier set and per-carrier annual TWh values are recorded in the audit
- audit explicitly states whether the cap is benchmark parity or diagnostic
- capped-resource set matches the configured `annual_generation_caps_twh` keys or deviations are explicitly documented

## Acceptance Criteria

Accept a CAP candidate only if:

- coal hourly Pearson r remains close to Module 13h, preferably near `0.598`
- coal annual TWh remains close to Eskom, ideally within about `5%`
- OCGT falls materially from `27.441 TWh`
- load shedding rises materially from `6.051 TWh`
- OCGT / load-shedding composition moves toward Eskom:
  - Eskom OCGT: `5.243 TWh`
  - Eskom load shedding: `16.755 TWh`
- total physical generation and scarcity composition remain interpretable; if the cap mostly creates excess load shedding because VRE is too low, classify it as a diagnostic limitation rather than a final calibration fix
- solve remains optimal and LP-only
- CAP is configurable through `configs/za/za_2023_fixed_validation.yaml`
- CAP can be toggled independently from Module 13i OPC
- CAP carrier set and per-carrier annual TWh targets are explicit
- any `HIGH_GAS`-derived cap is labelled diagnostic/counterfactual for `S_2023BM`
- the final 2023 calibrated baseline remains reportable without silently relying on a non-selected RSA scenario
- the report can clearly distinguish "RSA-BM parity baseline" from "counterfactual scarcity-cap sensitivity"

Reject or diagnose if:

- coal r falls back near `0.33`
- coal annual dispatch returns to about `185 TWh`
- the cap improves scarcity composition only by damaging coal calibration
- the cap hits OCGT but pushes load shedding far above Eskom because the model lacks enough VRE/non-scarcity generation
- `LOW_GAS + CAP` performs worse than `LOW_GAS` on scarcity composition after accounting for OCGT and load shedding together
- the capped resource set is not auditable
- a `HIGH_GAS` cap is presented as `S_2023BM` parity
- the implementation is not RSA-parity and is presented as if it is

## Expected Outcome

The likely durable result is one of:

1. **Accepted CAP candidate**
   - `EAF-UC-CAP-OCGT-ESKOM2023` or `EAF-UC-OPC-NO-MIN-GAS-CAP-OCGT-ESKOM2023` preserves the Module 13h coal improvement and improves OCGT/load-shedding composition. This remains a calibration diagnostic/counterfactual candidate unless the human explicitly promotes it over the RSA-BM parity baseline.

2. **CAP implementation bug found**
   - Correct PyPSA-Earth CAP parity, rerun, and document the correction.

3. **RSA has no direct CAP parity**
   - For `S_2023BM`, keep the CAP as an explicitly documented PyPSA-Earth diagnostic/counterfactual constraint, not an RSA-parity claim.

4. **Structural limitation found**
   - CAP is working, but the model still cannot match scarcity composition without additional cost calibration or reliability constraints. Keep Module 13h accepted and record Module 13j as diagnosed limitation.

5. **Expansion-scenario guidance**
   - Document whether the CAP should be removed, relaxed, or replaced by a 2030+ operational-limits scenario when moving from 2023 calibration to expansion modelling.

## Continuity

Module 13j validation has now classified the CAP result as a diagnostic limitation. The dispatch calibration notebook and HTML exports were refreshed on 2026-05-16, but the broader validation report text remains a separate reporting step.

Update after validation:

- `doc/za_implementation_log.md`
- vault `_status.md` and `_todo.md` because Module 13j reached diagnosed/closed state
- shared log if canonical state changes
- personal log for the work session

Preserve existing dirty worktree changes. Do not revert unrelated modified or untracked files.
