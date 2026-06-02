# ZA Snakemake Professionalization Plan

Date: 2026-06-01
Status: Implemented cleanup pass
Scope: `configs/za/`, `Snakefile`, `scripts/solve_network.py`, ZA validation docs

## Objective

Make the ZA 2023 calibration workflow look and behave like a professional
PyPSA-Earth workflow:

- small visible rule surface;
- ordinary base config plus scenario overlays;
- durable reusable intermediate artifacts;
- fast scenario reruns from an existing EAF source network;
- validation notebooks that report results but do not own model logic;
- unchanged numerical outputs for the three accepted presentation scenarios.

The cleanup should not change model behavior. It should make the DAG easier to
read, easier to rerun, and less dependent on labelled diagnostic wrappers.

## Grounded Current State

Facts from the June 1 rerun:

- Full Snakemake rerun works from data bundle/cutout through the three scenario
  solves.
- The three `EAF-CONFIG-*` solved networks reproduce the previous presentation
  results to report precision.
- The `ror` scaling entry was invalid because the active ZA fleet/network does
  not contain `ror` generators. It has been removed from active scenario and
  diagnostic overlays.
- The main Snakefile now exposes 6 ZA-added rule names beyond base
  PyPSA-Earth.
- `prepare_za_input_data` is the single disabled-by-default source/model-input
  regeneration target, including the custom busmap, custom-line, and coal EAF
  input rebuild steps.
- `solve_network_eaf_config` is the only ZA scenario solve wrapper.
- Legacy labelled solves, audit-copy aliases, stock-baseline rules, source
  generation rules, and model-reporting diagnostics are removed from the main
  DAG.

Remaining concern:

- Three ZA network-mutation marker rules still remain visible. They are
  model-critical for the accepted source network, but they should eventually be
  folded into upstream-adjacent scripts if this fork is cleaned further.
- Scenario solves should keep the desired common path:

```text
existing EAF source network + scenario overlay -> solved scenario network
```

without rebuilding fleet reconciliation, powerplant alignment, grid diagnostics,
renewable profiles, or other source/audit materialization when those artifacts
already exist and are up to date.

## Snakemake Style Guidance

Context7 check against the current Snakemake docs highlights three relevant
workflow-design norms:

- organize workflows into explicit rules, scripts, config, results, and
  resources, with modular rule files where that fits the host project;
- use config files for workflow parameters instead of scenario-specific rule
  branches;
- Snakemake skips jobs when outputs are up to date with respect to declared
  inputs and relevant parameters, so dependency boundaries must be intentional.

For this PyPSA-Earth fork, "Earth-aligned" should mean following the local
PyPSA-Earth style first. If the repo keeps a central `Snakefile`, do not force a
new directory layout prematurely. If rule extraction is accepted, use a small
ZA-specific include file with neutral rule names rather than many labelled
branches.

## Single Optional Data-Regeneration Policy

The final workflow should not have many ZA-specific optional rule branches.
Rules that only regenerate source/reference/model-input data should be collapsed
into one disabled-by-default regeneration path, similar in spirit to
PyPSA-Earth's optional data-bundle and cutout retrieval/build stages.

Recommended config pattern:

```yaml
enable:
  za_input_data_regeneration: false
```

Recommended rule shape:

```text
prepare_za_input_data
```

This single rule, or one small include containing that rule and private helper
rules if unavoidable, should recreate all tracked/packageable ZA input data
needed to build and solve the accepted networks when those inputs are missing or
need refreshing. In normal reruns it should be disabled and the workflow should
consume the tracked packaged inputs directly.

Rules that build the actual source network or solve scenarios should stay in
the normal path until they can be folded into existing PyPSA-Earth stages or
replaced by tracked, stable input artifacts.

Validation checks, Earth-vs-RSA diagnostics, stock-baseline comparison, and
presentation/reporting work should not get their own Snakemake rule gates in
the final workflow. They should move to notebooks, archived provenance scripts,
or a clearly separate diagnostics workflow outside the normal model DAG.

## Non-Negotiable Invariants

Keep these unchanged:

| Scenario | Required output | Required objective |
|---|---|---:|
| No VRE / no OCGT cap | `results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-CONFIG-coal485_nuclear50_no_vre_no_ocgt_cap.nc` | `30326143568.65032` |
| VRE only | `results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-CONFIG-coal485_nuclear50_vre_only.nc` | `25449233841.801006` |
| VRE + OCGT cap | `results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-CONFIG-coal485_nuclear50_vre_ocgt_cap.nc` | `31212007124.84154` |

Also keep:

- fail-fast behavior for missing carriers in solve-time profile/availability
  adjustments;
- base config plus overlay CLI usage;
- validation notebooks as reporting only;
- `module14_joint_solve.py` and diagnostic configs as provenance unless a
  separate archival decision is made.

## Desired End-State DAG

The final user-facing workflow should have three understandable stages.

### Stage 1: Shared Source Build

Build or reuse stable shared inputs:

```text
retrieve_databundle_light
cutouts/cutout-2023-era5.nc
networks/za_2023_fixed_validation/base.nc
networks/za_2023_fixed_validation/elec_s_34_ec_lc1_NoCO2-1H.nc
networks/za_2023_fixed_validation/elec_s_34_ec_lc1_NoCO2-1H-EAF.nc
```

Normal runs should consume the packaged ZA input files directly. If those files
are missing or intentionally refreshed, the user should enable and run the
single optional `prepare_za_input_data` target before rebuilding the source
network.

### Stage 2: Fast Scenario Solves

Once the EAF source network exists, each scenario target should only need:

```text
networks/.../elec_s_34_ec_lc1_NoCO2-1H-EAF.nc
configs/za/scenarios/<scenario>.yaml
solve-time reference inputs
```

and should produce:

```text
results/.../elec_s_34_ec_lc1_NoCO2-1H-EAF-CONFIG-<scenario_label>.nc
```

### Stage 3: Reporting

Validation and presentation notebooks should discover/read solved outputs and
produce tables/figures. They should not mutate the model or define final
scenario constraints.

## Post-Implementation Rule Surface

The implemented Snakefile now has 6 ZA-added rules beyond base PyPSA-Earth.

| Rule | Status | Role | Next simplification |
|---|---|---|---|
| `prepare_za_input_data` | Optional; disabled by default | Regenerates packaged ZA source/model-input data through existing scripts, including custom busmap, custom-line, and coal EAF inputs. | Keep as the only public data-regeneration target. |
| `apply_za_custom_lines` | Active model path | Applies tracked ZA custom transmission-line inputs before extra components. | Fold into the nearest grid/component stage if the hook remains always-on. |
| `apply_za_local_carriers` | Active model path | Applies tracked ZA carrier metadata and fixed fleet adjustments before extra components. | Convert more behavior to ordinary input data consumed by upstream-style scripts. |
| `za_fix_csp_links_stores` | Active model path | Fixes ZA CSP link/store capacity representation before `prepare_network`. | Fold into `prepare_network` or general CSP handling if valid beyond this run. |
| `apply_za_coal_eaf` | Active source-network boundary | Builds the reusable EAF/UC source network from the prepared fixed network. | Keep unless EAF can be cleanly represented inside `prepare_network`. |
| `solve_network_eaf_config` | Active scenario solve | Solves config-labelled scenarios from the EAF source network. | Keep as the only ZA scenario solve rule. |

Removed from the main DAG:

- source/input generation rules, now represented by tracked packaged inputs and
  `prepare_za_input_data`;
- renewable/profile QA, fixed-network audit, Earth-vs-RSA diagnostics, and
  stock-baseline comparison rules, now reporting/provenance work;
- legacy labelled solve wrappers and audit-copy aliases;
- the solved non-scenario EAF wrapper, because accepted reruns use
  `solve_network_eaf_config`.

Implementation questions resolved for this pass:

- Normal reruns use tracked/packageable ZA inputs.
- `solve_network_eaf` is not required by the active rerun manual or refreshed
  validation notebooks.
- Stock-baseline comparison is archived/provenance work, not a main-DAG target.
- Diagnostics and reporting stay in notebooks or direct scripts outside the
  normal model DAG.
- CSP remains a visible ZA marker rule for now; generalization is a later
  cleanup.

## Cleanup Work Packages

### 1. Separate Source-Stage Config From Solve-Stage Overlays

Problem:

The scenario overlays currently contain some settings that describe the shared
EAF source-network build, not just the solve. When those keys enter the global
Snakemake config for a scenario target, upstream rules can appear stale or
parameter-changed.

Recommendation:

- Move common source-network assumptions into
  `configs/za/za_2023_fixed_validation.yaml` or a clearly documented
  source-stage overlay.
- Keep scenario overlays limited to solve-time choices:
  - `za_scenario.label`;
  - `za_operational_constraints`;
  - `za_generation_constraints`;
  - `za_profile_scaling`;
  - `za_availability_overrides`.
- Avoid repeating `za_fleet` and shared `za_coal_disaggregation` source-build
  settings in each scenario overlay unless they truly vary by scenario.

Acceptance gate:

- Running a scenario target with `--force` should show only the generic solve
  job, not fleet/grid/powerplant rebuild jobs, when the EAF source network
  already exists.

Example check:

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml configs/za/scenarios/za_2023_coal485_nuclear50_vre_only.yaml --cores 4 --dry-run --force results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-CONFIG-coal485_nuclear50_vre_only.nc
```

Expected job surface after cleanup: `solve_network_eaf_config` only, plus no
upstream ZA prep jobs.

### 2. Narrow `solve_network_eaf_config` Inputs and Params

Problem:

The generic solve rule should not depend on source-build audit files or
source-stage config signatures unless the solver genuinely reads them.

Recommendation:

- Review each `input` and `params` entry in `solve_network_eaf_config`.
- Keep direct solver inputs only:
  - EAF source network;
  - required generic PyPSA-Earth solve inputs such as `agg_p_nom_minmax`;
  - operational-constraints workbook if enabled/read at solve time.
- Remove EAF audit files from the solve rule input if they are only provenance.
  If an audit link is still desired, write it as metadata or document it rather
  than making every scenario solve depend on it.
- Restrict `za_config_solve_signature` to solve-time config blocks. Do not
  include `za_fleet` or source-stage coal-disaggregation blocks unless the solve
  script reads them after network load.

Acceptance gate:

- Editing only a solve overlay should not mark `apply_za_coal_eaf`,
  `build_powerplants`, `build_za_grid_spatial`, or `materialize_za_2023_fleet`
  as needed.

### 3. Define a Single Durable ZA Source Network Target

Problem:

Users need one obvious reusable model-ready input network for notebook
experiments and fast solves.

Recommendation:

- Treat this file as the canonical reusable source network:

```text
networks/za_2023_fixed_validation/elec_s_34_ec_lc1_NoCO2-1H-EAF.nc
```

- Ensure all heavy source-prep rules terminate there.
- Make the rerun manual clear that this is the checkpoint after which scenario
  solves should be fast.
- If possible, expose a neutral alias/checkpoint target that is easy to explain
  without adding many extra rules. If an alias rule would increase rule count,
  prefer documentation over a new rule.

Acceptance gate:

- From a clean clone, scenario targets can still rebuild the EAF source network
  automatically.
- From an existing clone with the EAF source network present, scenario targets
  do not rebuild the source network unless a true source input changed.

### 4. Collapse ZA Data Preparation To One Optional Rule

Problem:

The default clean ZA config still activates many input-preparation and audit
rules. This was useful during calibration, but it is high for a final workflow.

Recommendation:

Work toward this end state:

```text
enable.za_input_data_regeneration: false
prepare_za_input_data
```

The normal workflow should use tracked/packageable ZA inputs. If those inputs
are missing or need to be refreshed, the user explicitly enables and runs the
single regeneration target. Reporting, QA, diagnostics, and historical
comparisons should move to notebooks or archived provenance workflows rather
than additional Snakemake rule gates.

Rules to remove from the default DAG as standalone rules after their accepted
outputs are tracked or regenerated by `prepare_za_input_data`:

- `build_za_eskom_validation_data`;
- `build_za_carrier_taxonomy`;
- `build_za_demand_import_export_inputs`;
- `build_za_costs_fuels_efficiencies`;
- `build_za_fleet_reconciliation`;
- `materialize_za_2023_fleet`;
- `build_za_grid_spatial`;
- `build_za_custom_lines`;
- `build_za_coal_plants`;
- `validate_za_renewable_profiles`;
- `build_za_fixed_network_audit`;
- `build_za_earth_rsa_diagnostic`;
- `build_za_source_audits`;
- audit materialization aliases and legacy labelled wrappers.

Candidate rules to fold into upstream-adjacent stages:

- `apply_za_custom_lines` into grid/cluster preparation;
- `apply_za_local_carriers` into cost/carrier or add-extra-components handling;
- `za_fix_csp_links_stores` into the nearest component-preparation script.

Do not collapse everything into one opaque script if that would make debugging
harder. The goal is fewer visible workflow branches, not less auditability.

Acceptance gate:

- Default active extra rules should fall below 18 by removing or folding
  non-model rules, not by adding more config switches.
- Stretch target: no more than 5 active extra ZA rules.
- Best target: 2 to 3 active extra ZA rules: one optional data-regeneration
  rule, one EAF source-network boundary if still needed, and one generic
  config-labelled solve rule.
- Enabling `prepare_za_input_data` from missing packaged inputs, then rerunning
  the source-network build and three scenario solves, must reproduce the same
  objective values listed in the invariants.

### 5. Remove Legacy Diagnostics From The Main Workflow

Problem:

The legacy Module 14 labelled solve wrappers are useful provenance but should
not define the normal workflow surface.

Recommendation:

- Remove the legacy labelled solve wrappers from the main `Snakefile` once the
  accepted `EAF-CONFIG-*` scenario solves are protected by regression checks.
- Do not add new labelled solve wrappers.
- If historical diagnostics are needed later, put them in:
  - archived configs;
  - documentation;
  - notebooks that read already-solved networks;
  - a separate diagnostics workflow outside the normal PyPSA-Earth model DAG.

Acceptance gate:

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml --list
```

should show only the clean default workflow surface.

There is no expectation that `za_legacy_diagnostic_rules=True` remains available
in the cleaned workflow.

### 6. Update Documentation and Config Together

Any DAG/config simplification must update:

- `doc/active/calibration-plan/rerun-za-2023-baselines.md`;
- `doc/active/calibration-plan/za_snakemake_extra_rules_audit.md`;
- scenario overlay comments if common source-stage keys are moved;
- notebook path/suffix references if solved output names change.

The rerun manual should remain short and terminal-oriented:

```text
clone -> activate env -> retrieve bundle -> retrieve/build cutout
-> build EAF source network -> solve three overlays -> rerun notebooks
```

## Implementation Record

Completed in this cleanup pass:

1. Audited `solve_network_eaf_config` and kept only solve-time config blocks in
   the scenario signature.
2. Treated the accepted generated ZA files as packaged normal inputs and moved
   their regeneration behind `prepare_za_input_data`.
3. Moved common source-network assumptions out of the three scenario overlays.
4. Removed standalone ZA source/reference/data materialization rules from the
   visible main DAG and folded their script execution into
   `prepare_za_input_data`.
5. Removed validation checks, Earth-vs-RSA diagnostics, stock-baseline
   comparison, legacy labelled solve wrappers, and audit aliases from the
   normal model DAG.
6. Kept `solve_network_eaf_config` as the only config-labelled scenario solve
   rule and removed the solved non-scenario EAF wrapper.
7. Updated the rerun manual and extra-rule audit.

Deferred to the next cleanup pass:

- fold `apply_za_custom_lines`, `apply_za_local_carriers`, and
  `za_fix_csp_links_stores` into upstream-adjacent scripts if the same outputs
  can be preserved;
- run a full regeneration-from-missing-inputs acceptance test before deleting
  any currently tracked packaged input.

## Final Verification Status

- [x] `snakemake --list` parses under the default config.
- [x] The default config has `enable.za_input_data_regeneration: false`.
- [x] `prepare_za_input_data` is the only optional ZA data/source/reference
      regeneration entry point, including custom busmap/custom-line/coal EAF
      input rebuilds.
- [x] All three scenario targets dry-run.
- [x] Isolated forced dry-runs of each scenario schedule only
      `solve_network_eaf_config` when restricted to the existing EAF source
      network boundary.
- [x] Default active extra ZA rules are reduced to 6, with every remaining extra
      rule justified as model-critical or an unavoidable source-network
      boundary.
- [x] Validation checks, Earth-vs-RSA diagnostics, stock-baseline comparison,
      labelled solve wrappers, and reporting/presentation work are outside the
      normal model DAG.
- [x] Existing solved networks still contain the three accepted objective values:
      `30326143568.65032`, `25449233841.801006`, and `31212007124.84154`.
- [ ] Full normal rerun from packaged inputs was not repeated in this cleanup
      pass; the previous June 1 rerun already proved it before rule cleanup.
- [ ] Full regeneration rerun from missing packaged inputs was not repeated in
      this cleanup pass; run it before deleting any tracked packaged input.
- [ ] Validation notebooks were not rerun in this cleanup pass because notebooks
      and solved output names did not change.
- [ ] `4-work/slides/presentation_figures.ipynb` was not checked in this cleanup
      pass.

## Prompt For Further Context7 Use

When refining this plan, use Context7 to check current Snakemake documentation
for:

- modular Snakefile organization;
- configfile and overlay semantics;
- rerun triggers from changed inputs, params, code, or metadata;
- best practice for optional/reporting rules;
- whether `--force`, `--forcerun`, `ancient()`, or explicit config signatures
  are appropriate for this use case.

Avoid using `ancient()` or broad force flags as the primary design. The cleaner
solution is a dependency graph where source-stage artifacts and solve-stage
overlays are separated by construction.
