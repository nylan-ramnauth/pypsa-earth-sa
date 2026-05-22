# Module 13l Handoff - Runtime Input Audit, Earth-Local RSA Source Packaging, and Reproducibility Lock

**Target agent:** Codex xhigh or equivalent standalone implementation agent  
**Working directory (Earth):** `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth`  
**Working directory (RSA reference, read-only during discovery):** `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-rsa`  
**Conda environment:** `pypsa-earth`

## Summary

Make the PyPSA-Earth ZA 2023 calibrated baseline self-contained.

This is a full runtime-input audit plus source-packaging module.

The Earth model should not require live reads from `../pypsa-rsa/...` during normal calibration builds or solves. PyPSA-RSA can remain the audit/reference source, but every RSA-derived workbook/CSV needed at runtime must be copied or materialized inside the PyPSA-Earth repo with hashes and provenance.

The module must also audit all other files read by the ZA 2023 calibration path and verify that they already live inside the Earth repo. If any non-RSA runtime input is outside the Earth repo, either move/copy it into Earth or explicitly classify it as audit-only/stale and remove it from runtime config.

This module should run after Modules 13i, 13j if used, and 13k. Module 13k classifies what each input actually represents; Module 13l then packages runtime-required sources into Earth using those classifications.

Do this before final notebook/report/HTML export refresh.

## Objective

Audit every runtime file used by the ZA 2023 calibration path, then create an Earth-local source package for RSA-derived runtime inputs:

```text
data/za_reference/pypsa_rsa_benchmark_2023/
```

Then update configs/scripts so the normal PyPSA-Earth ZA 2023 workflow reads from Earth-local inputs, not directly from `../pypsa-rsa`.

The intended final state:

- Earth repo can rebuild ZA 2023 calibration inputs without requiring a sibling RSA checkout.
- Every runtime-required input file is either already in Earth or copied/materialized into Earth.
- Config paths point only to Earth-local files for normal ZA 2023 calibration runs.
- Any missing required source file fails fast.
- Source hashes and original RSA paths are recorded.
- A complete runtime input manifest exists for the accepted baseline and selected sensitivities.
- `../pypsa-rsa` is optional reference/audit context, not a runtime dependency.

## Ordering

Recommended sequence:

1. Module 13i: implement `NO_MIN_GAS` operational-limits baseline and `LOW_GAS` / `HIGH_GAS` sensitivities.
2. Module 13j: optional CAP diagnostics, if still needed after 13i.
3. Module 13k: classify input provenance and 2023 accuracy.
4. Module 13l: audit all runtime input files, package finalized RSA-derived runtime inputs into Earth, and lock reproducibility.
5. Final validation notebook/report/HTML refresh.

If Module 13j is skipped or deferred, 13l can still proceed after 13i and 13k, but it must package only the runtime inputs actually needed by the accepted baseline and chosen sensitivities.

## Scope

Do:

- discover every file currently read at runtime by the ZA 2023 Earth calibration workflow
- classify whether each runtime file is already Earth-local, RSA-derived external, another external dependency, generated intermediate, or audit-only
- use `data/za_audit/za_2023_input_provenance_classification.csv` from Module 13k to label each packaged source
- copy required RSA-derived source workbooks/CSVs into an Earth-local reference directory
- copy or materialize any other non-Earth runtime input into Earth, unless it is explicitly removed from the runtime path
- update config defaults to point to the Earth-local copies
- update scripts only where needed to remove hard-coded `../pypsa-rsa` assumptions
- add file-existence and hash/provenance gates
- record a machine-readable complete runtime input manifest

Do not:

- alter coal EAF semantics
- alter coal UC behavior
- alter operational-limit semantics
- retune OCGT, load shedding, coal, or costs
- refresh final notebook/report/HTML exports unless explicitly requested after this module
- delete or modify the RSA reference repo

## Discovery Tasks

### A. Search for external references

Search the Earth repo for live RSA references:

```bash
rg -n "../pypsa-rsa|pypsa-rsa|Benchmark_2023|scenarios_to_run|fixed_technologies|plant_availability|operational_constraints|fuel_prices|emissions|reserve_margin|aux_stg_feed|annual_load" .
```

Also search for any parent-directory or absolute-path runtime references:

```bash
rg -n "\\.\\./|/Users/|/Volumes/|/private/|/tmp/|/var/folders|/mnt/|/home/" Snakefile scripts configs data/*.csv data/**/*.csv
```

Do not treat every match as a bug. Classify each match. Some are documentation, audit provenance, local temporary files, or harmless examples. Runtime config/script paths are the concern.

Inspect at least:

- `scripts/build_za_coal_plants.py`
- `scripts/za_fleet/build_za_coal_plants_network.py`
- `scripts/za_fleet/operational_constraints.py`, if present
- `scripts/solve_network.py`
- `configs/za/za_2023_fixed_validation.yaml`
- `Snakefile`
- `data/za_audit/input_file_manifest.csv`
- `data/za_audit/za_2023_input_provenance_classification.csv`
- any Module 13i/13j outputs or audit files
- notebook/report helper scripts only if they are part of the final validation refresh path

### B. Trace actual runtime inputs

For the accepted 2023 baseline target, trace the files read by:

- coal CSV rebuild
- EAF/coal network attachment
- operational-constraints attachment
- network solve
- validation metric extraction, if it is part of the accepted reporting path

Preferred methods:

- inspect Snakemake inputs and config keys
- inspect Python file reads in touched scripts
- inspect generated audit manifests
- run dry-run or targeted Snakemake commands where useful

The goal is a complete list of runtime inputs, not only a list of RSA workbooks.

### C. Classify each file

Classify each discovered file as one of:

- runtime-required
- runtime-generated intermediate
- audit-only
- stale/unused
- generated output provenance
- documentation/example only

Also classify location/source:

- Earth-local source
- Earth-local generated
- RSA-derived external
- other external path
- missing/unresolved

Only runtime-required inputs must be copied and wired into config. Audit-only references can remain as provenance notes but should not block normal runs.

Any runtime-required input that is not Earth-local must be either:

- copied/materialized into Earth and wired into config, or
- removed from runtime dependency if it is actually stale.

## Candidate Files To Package

Start with this candidate list, then refine based on discovery:

```text
scenarios/Benchmark_2023/scenarios_to_run.xlsx
scenarios/Benchmark_2023/sub_scenarios/fixed_technologies.xlsx
scenarios/Benchmark_2023/sub_scenarios/plant_availability.xlsx
scenarios/Benchmark_2023/sub_scenarios/operational_constraints.xlsx
scenarios/Benchmark_2023/sub_scenarios/fuel_prices.xlsx
scenarios/Benchmark_2023/sub_scenarios/emissions.xlsx
scenarios/Benchmark_2023/sub_scenarios/annual_load.xlsx
scenarios/Benchmark_2023/sub_scenarios/reserve_margin.xlsx
scenarios/Benchmark_2023/sub_scenarios/aux_stg_feed.xlsx
```

Do not blindly copy files into runtime config if they are not used. The package can include extra reference files if useful, but the manifest must mark whether each file is runtime-required.

## Target Directory Layout

Use this Earth-local layout unless there is a strong local convention to prefer another:

```text
data/za_reference/pypsa_rsa_benchmark_2023/
  README.md
  manifest.csv
  scenarios_to_run.xlsx
  sub_scenarios/
    fixed_technologies.xlsx
    plant_availability.xlsx
    operational_constraints.xlsx
    fuel_prices.xlsx
    emissions.xlsx
    annual_load.xlsx
    reserve_margin.xlsx
    aux_stg_feed.xlsx
```

The layout intentionally mirrors the RSA source layout where practical.

## Manifest Requirements

Write:

```text
data/za_reference/pypsa_rsa_benchmark_2023/manifest.csv
```

Required columns:

- `local_path`
- `original_rsa_path`
- `sha256`
- `bytes`
- `runtime_required`
- `provenance_class`
- `used_by_module`
- `used_by_script`
- `source_scenario`
- `source_sheet`
- `notes`

The `provenance_class` value should be copied or summarized from Module 13k's `data/za_audit/za_2023_input_provenance_classification.csv`.

Also update or create an audit entry under:

```text
data/za_audit/
```

Suggested file:

```text
data/za_audit/za_rsa_source_package_manifest.csv
```

This can duplicate or summarize the package manifest for validation notebooks and reports.

Also create a complete runtime input manifest:

```text
data/za_audit/za_2023_runtime_input_manifest.csv
```

Required columns:

- `path`
- `resolved_path`
- `exists`
- `inside_earth_repo`
- `source_class`
- `runtime_class`
- `sha256`
- `bytes`
- `used_by_rule`
- `used_by_script`
- `used_by_config_key`
- `module`
- `copied_to`
- `original_path`
- `notes`

This manifest is the main acceptance artifact for the "audit every file used to run the model" requirement.

## README Requirements

Write:

```text
data/za_reference/pypsa_rsa_benchmark_2023/README.md
```

It should state:

- these files are local copies of PyPSA-RSA `Benchmark_2023` inputs
- the package exists to make PyPSA-Earth ZA 2023 calibration self-contained
- source repo path used during packaging
- packaging date
- relevant scenario: `S_2023BM`
- model year: 2023
- selected baseline operational limits: `NO_MIN_GAS`
- sensitivity operational limits, if implemented: `LOW_GAS`, `HIGH_GAS`
- hashes are in `manifest.csv`
- do not edit copied workbooks manually without updating hashes/provenance

## Config Requirements

Update `configs/za/za_2023_fixed_validation.yaml` so runtime paths point to Earth-local sources.

Possible schema:

```yaml
za_rsa_reference:
  enable: true
  base_dir: data/za_reference/pypsa_rsa_benchmark_2023
  scenario_workbook: data/za_reference/pypsa_rsa_benchmark_2023/scenarios_to_run.xlsx
  sub_scenarios_dir: data/za_reference/pypsa_rsa_benchmark_2023/sub_scenarios
  require_local_sources: true
  manifest: data/za_reference/pypsa_rsa_benchmark_2023/manifest.csv
```

Then ensure downstream config blocks use these local paths, for example:

```yaml
za_coal_disaggregation:
  rsa_scenarios: data/za_reference/pypsa_rsa_benchmark_2023/sub_scenarios

za_operational_constraints:
  workbook: data/za_reference/pypsa_rsa_benchmark_2023/sub_scenarios/operational_constraints.xlsx
```

Xhigh should refine exact key names to match the implemented 13g/13h/13i code.

## Runtime Gate Requirements

Add fail-fast checks where appropriate:

- if `za_rsa_reference.require_local_sources: true`, reject paths that point outside the Earth repo for runtime-required RSA inputs
- if `za_runtime_inputs.require_earth_local: true`, reject any runtime-required input path outside the Earth repo unless explicitly allowlisted as audit-only
- fail if a required local workbook is missing
- fail if config asks for `NO_MIN_GAS`, `LOW_GAS`, or `HIGH_GAS` and the local `operational_constraints.xlsx` does not contain that scenario
- fail if config asks for `S_2023BM` and the local `scenarios_to_run.xlsx` does not contain it
- warn, but do not necessarily fail, if hashes differ from manifest unless the module implements strict hash locking

Strict hash locking can be configurable:

```yaml
za_rsa_reference:
  strict_hash_check: false
```

If set true, hash mismatch should fail.

Possible broader config:

```yaml
za_runtime_inputs:
  require_earth_local: true
  manifest: data/za_audit/za_2023_runtime_input_manifest.csv
  allow_audit_only_external_paths: true
```

## Validation

Run these checks:

1. Static path check:
   - no runtime config path points to `../pypsa-rsa`
   - no runtime script requires `../pypsa-rsa`
   - no runtime-required path points outside the Earth repo
   - audit-only references are documented as audit-only

2. Manifest check:
   - all runtime-required files exist
   - all runtime-required files are inside Earth
   - SHA-256 hashes recorded
   - file sizes recorded
   - original RSA source paths recorded for RSA-derived files
   - source/runtime classification recorded for every discovered file

3. Rebuild check:
   - rebuild coal CSVs using only Earth-local RSA source package
   - verify expected coal package gates:
     - 15 stations
     - 16 generator rows
     - total coal p_nom about `41.419 GW`
     - Arnot annual EAF about `0.480`
     - Arnot January about `0.448`
     - Arnot July about `0.524`

4. Operational-constraints check:
   - Module 13i can read `NO_MIN_GAS` from the Earth-local workbook
   - sensitivity scenarios `LOW_GAS` and `HIGH_GAS`, if implemented, can also be read from the Earth-local workbook
   - audit rows record local source paths

5. Solve smoke:
   - run the accepted or current 2023 baseline target with local sources only
   - expected target after Module 13i:
     - `EAF-UC-OPC-NO-MIN-GAS`
   - solve remains LP-only and optimal

## Acceptance Criteria

Accept Module 13l if:

- PyPSA-Earth ZA 2023 calibration can be rebuilt without a sibling PyPSA-RSA checkout.
- Every runtime-required input file is Earth-local.
- Runtime-required RSA inputs are Earth-local.
- Config defaults point to Earth-local source files.
- Complete runtime input manifest records all required files and classifications.
- RSA source package manifest records original RSA paths and hashes.
- Module 13k provenance classes are preserved in the runtime and source-package manifests.
- Missing required local sources fail fast.
- Coal CSV rebuild gates still pass.
- Module 13i baseline can run using local `operational_constraints.xlsx`.
- No calibration behavior changes except path/provenance changes.

Reject or block if:

- any normal ZA 2023 runtime path still requires `../pypsa-rsa`
- any normal ZA 2023 runtime path still requires another external path outside Earth
- local source copies cannot reproduce the existing generated inputs
- hashes/provenance cannot be recorded
- behavior changes unexpectedly relative to pre-packaging runs

## Continuity

Update after validation:

- `doc/za_implementation_log.md`
- `data/za_audit/za_2023_runtime_input_manifest.csv`
- `data/za_audit/za_2023_input_provenance_classification.csv`, only if packaging reveals corrections needed
- `data/za_audit/input_file_manifest.csv`, if this is the existing canonical input manifest
- `data/za_audit/za_rsa_source_package_manifest.csv`
- vault `_status.md` and `_todo.md` if Module 13l reaches accepted or blocked state
- shared log if canonical state changes
- personal log for the work session

Do not refresh final validation notebook / HTML / report exports unless Module 13l is accepted and the user explicitly asks for final reporting refresh.
