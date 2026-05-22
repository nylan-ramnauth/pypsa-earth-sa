# Module 13m Handoff - Official 2023 Fleet Reconciliation, Custom Powerplants Backup, and Optional Sasol

**Target agent:** Codex xhigh or equivalent standalone implementation agent  
**Working directory (Earth):** `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth`  
**Working directory (RSA reference, read-only during discovery):** `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-rsa`  
**Conda environment:** `pypsa-earth`  
**Solver:** Gurobi  
**Formulation:** LP relaxation / linearised UC only, not MILP

## Summary

Module 13h gave a strong coal-dispatch improvement, but the current 2023 coal fleet still has a provenance problem: the model uses `41.419 GW` of coal capacity, while Eskom's official 2023 nominal Eskom-owned coal capacity is `39.099 GW` at 31 March 2023.

The difference is exactly explained by:

- Kusile: current model `4.320 GW` vs Eskom 2023 nominal `2.880 GW` (`+1.440 GW`)
- Medupi: current model `4.320 GW` vs Eskom 2023 nominal `3.600 GW` (`+0.720 GW`)
- Kelvin: current model `0.160 GW`, not in Eskom-owned coal table (`+0.160 GW`)

`39.099 + 1.440 + 0.720 + 0.160 = 41.419 GW`

This module makes that fleet basis explicit and configurable. It also adds an optional Sasol/conventional-IPP switch so Sasol can be tested transparently, without silently folding it into Eskom coal UC.

Critical rule: before changing `data/custom_powerplants.csv`, copy the current accepted file to a backup path and write an audit hash. The current file is a valuable Module 13g/13h/13j artifact and must remain recoverable.

## Objective

Implement a configurable 2023 fleet-calibration layer that can run at least these cases:

1. Current RSA-derived fleet, no Sasol: current behavior / control.
2. Official Eskom 2023 nominal coal fleet, no Sasol.
3. Official Eskom 2023 nominal coal fleet, optional Sasol enabled.

The goal is not to tune blindly. The goal is to determine whether the current scarcity/dispatch residuals are driven by:

- overstated coal capacity,
- missing Sasol/conventional IPP generation,
- VRE underproduction,
- or remaining dispatch/constraint issues.

## Why This Module Comes Before VRE Scaling

Do not use VRE scaling as the next calibration layer until the fixed dispatchable fleet basis is clear.

VRE scaling is still likely needed later because current ERA5/Atlite wind/PV/CSP generation is below Eskom observed 2023 generation. But applying VRE scaling before fixing the dispatchable fleet would risk compensating for a coal-capacity or missing-Sasol modeling error.

Recommended order:

1. Module 13m: official 2023 fleet reconciliation and optional Sasol.
2. Re-run `NO_MIN_GAS`, `LOW_GAS`, and selected CAP diagnostics.
3. Then apply VRE scaling only as a separate labelled calibration layer if still needed.

## Required Config Shape

Keep the config simple. Add one block under `configs/za/za_2023_fixed_validation.yaml`.

Suggested block:

```yaml
# Module 13m - configurable 2023 fleet basis.
za_2023_fleet_calibration:
  enable: true

  custom_powerplants:
    path: data/custom_powerplants.csv
    backup_before_mutation: true
    backup_dir: data/za_audit/backups

  coal_fleet:
    # Options:
    # - rsa_var_hr_41p419: current Module 13g/13h fleet from RSA VAR_HR, 41.419 GW
    # - eskom_nominal_2023: official Eskom 31 Mar 2023 nominal coal fleet, 39.099 GW
    # - calibrated_2023: project-selected 2023 calibrated fleet; initially alias to eskom_nominal_2023 unless explicitly changed
    mode: calibrated_2023
    include_kelvin: false

  sasol:
    enable: false
```

Also update the existing Module 13j annual-cap block so Sasol caps can be set directly when Sasol is enabled:

```yaml
za_scarcity_cap:
  enable: false
  model_year: 2023
  # Generator carriers currently expected across the calibrated ZA variants:
  # coal, csp, load shedding, nuclear, ocgt_diesel, onwind, solar,
  # sasol_coal, sasol_gas
  annual_generation_caps_twh:
    ocgt_diesel: 5.243
    sasol_coal: 5.5
    sasol_gas: 2.8
```

The Sasol rows may remain commented or disabled by `za_scarcity_cap.enable: false` in the default config, but the config schema, validation, audit, and documentation must make clear that `sasol_coal` and `sasol_gas` are valid annual-cap carriers once `za_2023_fleet_calibration.sasol.enable: true`.

If implementation needs more detail, keep it nested under this block. Do not create scattered top-level flags.

## Required Backup Behavior

Before any script mutates or regenerates `data/custom_powerplants.csv`, copy the current file to a timestamped backup such as:

```text
data/za_audit/backups/custom_powerplants_pre_13m_YYYYMMDD_HHMMSS.csv
```

Also write:

```text
data/za_audit/custom_powerplants_backup_manifest.csv
```

Required manifest columns:

- `created_at`
- `source_path`
- `backup_path`
- `source_sha256`
- `backup_sha256`
- `source_rows`
- `backup_rows`
- `reason`
- `git_status_summary`

Gate:

- fail if backup is requested but cannot be written
- fail if source and backup hashes differ immediately after copy
- fail if `data/custom_powerplants.csv` is missing before backup

## Coal Fleet Modes

### `rsa_var_hr_41p419`

This is the current Module 13g/13h behavior:

- coal total: `41.419 GW`
- source basis: RSA `VAR_HR`
- includes Kelvin `160 MW`
- uses Medupi `4.320 GW`
- uses Kusile `4.320 GW`
- keeps existing Hendrina split behavior

This mode is the control. It must keep current results reproducible.

### `eskom_nominal_2023`

Use official Eskom Integrated Report 2023 nominal coal capacity at 31 March 2023:

- coal total: `39.099 GW`
- Komati nominal: `0 MW`
- Kelvin excluded by default
- Medupi: `3.600 GW`
- Kusile: `2.880 GW`
- older station values should match Eskom nominal values where already aligned

Official source:

```text
Eskom Holdings SOC Ltd, Integrated Report 2023,
Plant information, "Power station capacities at 31 March 2023"
https://www.eskom.co.za/heritage/wp-content/uploads/2024/03/2023_Annual_Report.pdf
```

### `calibrated_2023`

This is the project-selected baseline fleet. Initially set it to the official Eskom 2023 nominal fleet unless the implementation audit finds a defensible reason to retain a specific deviation.

If `calibrated_2023` differs from `eskom_nominal_2023`, the implementation must write an explicit audit row explaining each difference.

## Sasol Optional Layer

Add Sasol as a configurable optional layer:

```yaml
za_2023_fleet_calibration:
  sasol:
    enable: false
```

When `sasol.enable: false`:

- current no-Sasol perimeter is preserved
- no `sasol_coal` or `sasol_gas` generators are attached
- OPC and CAP audits may still list Sasol rows as skipped/missing

When `sasol.enable: true`:

- add Sasol as non-UC dispatchable generation
- do not include Sasol in Eskom coal UC
- do not count Sasol as Eskom thermal/coal in coal Pearson validation unless a separate comparison row is explicitly added
- add carriers if missing:
  - `sasol_coal`
  - `sasol_gas`
- apply annual generation caps through the existing Module 13j CAP mechanism or a shared helper, not through hidden ad hoc logic
- ensure the `za_scarcity_cap.annual_generation_caps_twh` config supports `sasol_coal` and `sasol_gas`

Starting RSA-derived Sasol values to audit before use:

| Asset | Carrier | Capacity |
|---|---|---:|
| Secunda_coal | `sasol_coal` | `600.04 MW` |
| Sasolburg_coal | `sasol_coal` | `128.00 MW` |
| Sasol_ice | `sasol_gas` | `174.60 MW` |
| Sasol_ocgt | `sasol_gas` | `250.00 MW` |
| Total | mixed | `1,152.64 MW` |

Known RSA-style annual caps from `NO_MIN_GAS` to audit:

| Carrier | Annual cap |
|---|---:|
| `sasol_coal` | `5.5 TWh` |
| `sasol_gas` | `2.8 TWh` |

Important: these are not yet proven from official Eskom hourly data. They are scenario assumptions unless Module 13k/13l source audits classify them more strongly.

## Implementation Scope

Do:

- preserve the current `data/custom_powerplants.csv` through a backup before mutation
- make coal fleet basis configurable
- make Sasol inclusion configurable
- keep the current Module 13h coal UC path working
- keep current `rsa_var_hr_41p419` behavior reproducible
- write audit files that show exactly which fleet basis was used
- update notebook/reporting labels only after solve outputs are generated

Do not:

- silently overwrite `data/custom_powerplants.csv`
- silently include Sasol in coal UC
- silently use official Eskom nominal capacity without labelling the changed fleet basis
- silently change VRE scaling in this module
- deduct the 5.144 TWh dispatchable accounting gap from demand
- claim Sasol explains the 5.144 TWh gap unless independently sourced

## Required Implementation Notes

### Custom Powerplants

The implementation can either:

- regenerate `data/custom_powerplants.csv` according to `za_2023_fleet_calibration`, or
- materialize mode-specific files and point the build path at the selected file.

Prefer the second approach if it is cleaner and avoids unnecessary churn:

```text
data/za_validation/custom_powerplants_rsa_var_hr_41p419.csv
data/za_validation/custom_powerplants_eskom_nominal_2023.csv
data/za_validation/custom_powerplants_calibrated_2023.csv
```

If mode-specific files are used, the selected file must still be copied or linked into the path expected by the existing workflow, or the workflow must be updated to read the configured path consistently.

### Coal Disaggregation

The coal disaggregation builder currently uses:

- RSA workbook for plant metadata and p_nom
- `custom_powerplants.csv` only for bus mapping and split weights

For `eskom_nominal_2023` / `calibrated_2023`, update this so coal p_nom is not forced back to RSA `VAR_HR` values. The selected fleet mode must own the coal station capacities used by:

- `za_coal_plants_2023.csv`
- `za_coal_eaf_hourly_2023.csv`
- network generator `p_nom`
- audit totals

Preserve Hendrina split behavior, but reweight using selected Hendrina capacity.

### Sasol Constraints

If Sasol is enabled, Sasol constraints must respect the selected operational-constraints scenario and model year. Do not hardcode `NO_MIN_GAS` values as the default for every run.

The rule is:

- `za_operational_constraints.scenario` and `za_operational_constraints.model_year` select workbook-grounded Sasol rows for the current solve.
- Annual `output_energy/year/max` rows remain owned by Module 13j CAP semantics.
- If a selected scenario contains Sasol annual cap rows and CAP is enabled for Sasol, materialize those cap values into the CAP layer for that labelled solve.
- If CAP is disabled, audit the selected Sasol annual cap rows as available-but-not-applied, consistent with the Module 13i/13j boundary.
- If the user provides explicit direct caps in `za_scarcity_cap.annual_generation_caps_twh`, those explicit config values override workbook-derived suggestions for that labelled diagnostic.
- The implementation must allow `annual_generation_caps_twh` to contain multiple carriers at once, for example `ocgt_diesel`, `sasol_coal`, and `sasol_gas`, with one annual cap per carrier.

Example for an explicit diagnostic only:

```yaml
za_scarcity_cap:
  enable: true
  annual_generation_caps_twh:
    sasol_coal: 5.5
    sasol_gas: 2.8
```

Do not make Sasol caps mandatory when `sasol.enable: true`. Allow:

- Sasol enabled with no CAP, to test unconstrained dispatch contribution.
- Sasol enabled with selected-scenario CAP values, to test scenario-consistent constraints.
- Sasol enabled with explicit CAP values, to test labelled diagnostics.

Audit the source of every applied Sasol constraint as one of:

- `selected_opc_scenario_delegated_to_cap`
- `explicit_cap_config`
- `not_applied_cap_disabled`
- `no_matching_scenario_row`

## Required Audit Outputs

Write:

```text
data/za_audit/za_2023_fleet_mode_audit.csv
data/za_audit/custom_powerplants_backup_manifest.csv
```

`za_2023_fleet_mode_audit.csv` required columns:

- `mode`
- `sasol_enabled`
- `source_file`
- `station_or_asset`
- `carrier`
- `p_nom_mw`
- `official_eskom_2023_nominal_mw`
- `rsa_var_hr_mw`
- `current_model_previous_mw`
- `difference_vs_official_mw`
- `difference_vs_rsa_var_hr_mw`
- `included_in_coal_uc`
- `included_in_eskom_coal_validation`
- `bus`
- `source_class`
- `source_evidence`
- `notes`

Also update existing coal and OPC/CAP audits if their row counts or skipped rows change.

## Required Solves

Run these at minimum if runtime allows:

1. Control:
   - `rsa_var_hr_41p419`
   - `sasol.enable: false`
   - `NO_MIN_GAS`
2. Official fleet baseline:
   - `calibrated_2023` or `eskom_nominal_2023`
   - `sasol.enable: false`
   - `NO_MIN_GAS`
3. Optional Sasol diagnostic:
   - `calibrated_2023` or `eskom_nominal_2023`
   - `sasol.enable: true`
   - `NO_MIN_GAS`
4. Scarcity sensitivity:
   - best no-Sasol and/or Sasol case
   - `LOW_GAS`

CAP diagnostics are optional after this module. If run, label them clearly:

- no CAP baseline
- OCGT CAP diagnostic
- Sasol CAP diagnostic, if Sasol enabled

## Required Metrics

Report for each solve:

- coal TWh
- OCGT TWh
- Sasol coal TWh, if enabled
- Sasol gas TWh, if enabled
- VRE TWh by wind/PV/CSP
- PHS generation and pumping TWh
- load shedding TWh
- coal hourly Pearson r vs Eskom thermal
- annual named-generation subtotal vs Eskom named comparable subtotal
- balance residual using the Section 7 accounting logic
- number of coal UC generators
- total coal p_nom
- whether Gurobi remained LP-only

## Acceptance / Classification

Classify results, do not force acceptance.

Suggested labels:

- `accepted_baseline_candidate`: improves or preserves coal shape while using better official 2023 fleet provenance and does not create implausible scarcity
- `diagnostic_only`: useful for understanding residuals but not a baseline
- `blocked_requires_source`: depends on Sasol or official fleet data that remains unsourced
- `rejected_regression`: worsens dispatch materially without improving provenance enough

Do not declare final acceptance unless:

- fleet source is explicit,
- `custom_powerplants.csv` backup exists and hashes pass,
- coal capacity total matches selected mode,
- Sasol state is explicit,
- dispatch metrics are reported,
- notebook labels do not confuse RSA-derived and official-fleet runs.

## Notebook / Reporting

Do not add a new notebook section unless necessary.

If solve outputs are accepted or useful diagnostics, integrate them into the existing dispatch calibration notebook plots/tables with concise labels:

- `UC-RSA-FLEET`
- `UC-OFFICIAL-FLEET`
- `UC-OFFICIAL-FLEET-SASOL`
- `LOW-GAS-OFFICIAL-FLEET`

Avoid claiming the official-fleet result is better simply because it uses official capacity. The dispatch metrics must decide.

## Continuity

At the end:

- update `doc/za_implementation_log.md`
- update `doc/active/calibration-plan/13m_official_2023_fleet_reconciliation_and_sasol.md` with implementation status and results
- update `doc/za_model_limitations.md` if fleet/Sasol limitations change
- write personal/shared continuity logs
- update `_status.md` / `_todo.md` only if the baseline state changes or the module reaches a durable blocked state

Preserve dirty worktree changes. Do not revert unrelated files.

## Implementation Status - 2026-05-16 04:20

Status: partial implementation complete; solve classification still pending.

Implemented:

- Added `za_2023_fleet_calibration` config with `calibrated_2023` currently aliasing `eskom_nominal_2023`.
- Added backup-first materialization through `scripts/materialize_za_2023_fleet.py` and `scripts/za_fleet/fleet_calibration.py`.
- Backed up the pre-13m `data/custom_powerplants.csv` to `data/za_audit/backups/custom_powerplants_pre_13m_20260516_041640.csv`.
- Wrote `data/za_audit/custom_powerplants_backup_manifest.csv`; source and backup SHA256 match.
- Materialized official Eskom 2023 coal basis into `data/custom_powerplants.csv`: 132 rows, 39.099 GW coal, Kelvin excluded, Medupi 3.600 GW, Kusile 2.880 GW.
- Wrote `data/za_audit/za_2023_fleet_mode_audit.csv`.
- Regenerated coal EAF/UC input CSVs on the same fleet basis:
  - `data/za_validation/za_coal_plants_2023.csv`: 14 stations, 15 generator rows, 39.099 GW.
  - `data/za_validation/za_coal_eaf_hourly_2023.csv`: 8760 x 14.
  - `data/za_validation/za_coal_bus_assignment.csv`: 15 generator-bus assignments.
- Added optional non-UC Sasol attachment support behind `za_2023_fleet_calibration.sasol.enable`.
- Added `sasol_coal` and `sasol_gas` local carrier cost rows for the optional diagnostic path.
- Added Snakemake wiring for `materialize_za_2023_fleet` and `build_za_coal_plants`.
- Patched CAP solve wiring so CAP rules use annual-cap helpers instead of hardcoding only `{"ocgt_diesel": 5.243}`.
- Added selected-OPC Sasol cap derivation from `operational_constraints.xlsx` annual `output_energy` / `year` / `max` rows. For `NO_MIN_GAS` in 2023 this derives `sasol_coal: 5.5` TWh and `sasol_gas: 2.8` TWh.
- Added `za_scarcity_cap_annual_generation_cap_sources` solve params so Sasol caps delegated from selected OPC rows audit as `selected_opc_scenario_delegated_to_cap`; explicit config fallback remains `explicit_cap_config`.
- Added labelled dry-run target:
  `results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-UC-OFFICIAL-FLEET-SASOL-OPC-{NO-MIN-GAS,LOW-GAS}-CAP-OCGT-SASOL-OPC-DELEGATED.nc`.
  The backing rule is `solve_network_eaf_opc_cap_ocgt_sasol_opc_delegated`.
- The labelled Sasol CAP target passes this cap dict for `NO-MIN-GAS`: `{"ocgt_diesel": 5.243, "sasol_coal": 5.5, "sasol_gas": 2.8}`.
- The existing `solve_network_eaf_cap` and `solve_network_eaf_opc_cap` targets still pass only `{"ocgt_diesel": 5.243}` under the default `sasol.enable: false`; if Sasol is enabled, the same helper includes selected-OPC Sasol caps alongside the OCGT diagnostic cap.

Validation completed:

- `python -m py_compile` passed for touched Python files.
- Direct materializer run passed.
- Direct coal CSV regeneration passed.
- In-memory Sasol attachment smoke test passed: 1,152.64 MW attached, no committable Sasol rows.
- Snakemake dry-runs passed for `materialize_za_2023_fleet`, `build_za_coal_plants`, `build_powerplants`, and the `NO-MIN-GAS` solve path.
- In-memory CAP smoke passed through `scripts/za_fleet/scarcity_cap.py::resolved_config` with `{"ocgt_diesel": 5.243, "sasol_coal": 5.5, "sasol_gas": 2.8}` and source map `{"ocgt_diesel": "Eskom observed 2023 OCGT generation target", "sasol_coal": "selected_opc_scenario_delegated_to_cap", "sasol_gas": "selected_opc_scenario_delegated_to_cap"}`.
- Snakemake dry-runs passed for the existing `...OPC-NO-MIN-GAS-CAP-OCGT-ESKOM2023.nc` target and the labelled official-fleet Sasol CAP target `...OFFICIAL-FLEET-SASOL-OPC-NO-MIN-GAS-CAP-OCGT-SASOL-OPC-DELEGATED.nc`; no full solve was executed.

Not yet executed:

- Full official-fleet `NO_MIN_GAS` solve.
- Optional Sasol-enabled solve.
- `LOW_GAS` official-fleet sensitivity.
- Full labelled Sasol CAP solve.
- Notebook/report refresh and acceptance classification.
