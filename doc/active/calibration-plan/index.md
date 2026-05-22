# South Africa Baseline Model Source Of Truth

Status: `reorganized 2026-05-14`. This folder is the active implementation-order
contract for making PyPSA-Earth a robust and accurate South Africa 2023 baseline
model. It is separate from the observed-reliability ENS + `myopic_elec_only`
feature plan in `doc/active/reliability-plan/`.

Archived source snapshot:

```text
docs/active/archive/source_snapshots/za_baseline_mining_plan.md
```

The archived snapshot is preserved for comparison only and must not be
implemented from directly.

## Implementation Modules

The modules are ordered so an implementing agent can execute them in sequence:
implement `01`, then `02`, and continue only when the acceptance gates for the
current module pass.

| Module | Implementation responsibility |
|---|---|
| [`00_governance_and_scope.md`](00_governance_and_scope.md) | Non-implementation scope, review protocol, relationship to reliability/myopic workstream |
| [`01_repo_bootstrap_and_config.md`](01_repo_bootstrap_and_config.md) | Repo inspection, local ZA folders, config overlays, solver/environment locks, provenance skeleton |
| [`02_eskom_validation_data_pipeline.md`](02_eskom_validation_data_pipeline.md) | Repair Eskom 2023 data, produce clean hourly validation data and annual targets |
| [`03_weather_cutout_and_profiles.md`](03_weather_cutout_and_profiles.md) | Build/smoke-test 2023 ERA5 cutout and renewable profiles, including CSP fallback policy |
| [`04_source_data_audits.md`](04_source_data_audits.md) | Extract powerplantmatching, PyPSA-RSA, REIPPPP, profile, availability, grid, and transmission candidate audit tables |
| [`05_system_boundary_and_carrier_taxonomy.md`](05_system_boundary_and_carrier_taxonomy.md) | Lock national boundary, embedded PV, CSP, OCGT, Sasol, hydro imports, storage carriers |
| [`06_demand_import_export_model_inputs.md`](06_demand_import_export_model_inputs.md) | Produce 8760 demand, import, export, sign-convention, load-allocation, and bus-attachment artifacts |
| [`07_costs_fuels_efficiencies_and_coUE.md`](07_costs_fuels_efficiencies_and_coUE.md) | Lock costs, fuels, efficiencies, emissions, local carrier cost rows, and COUE/load-shedding cost units |
| [`08_fleet_reconciliation_and_custom_powerplants.md`](08_fleet_reconciliation_and_custom_powerplants.md) | Reconcile plant fleet, freeze `custom_powerplants.csv`, smoke-test normalization |
| [`09_grid_spatial_and_transmission_model.md`](09_grid_spatial_and_transmission_model.md) | Audit OSM grid, RSA supply regions, custom busmap/subregions, optional corridor caps |
| [`10_earth_rsa_baseline_diagnostic.md`](10_earth_rsa_baseline_diagnostic.md) | Diagnostic only: quantify PPM vs RSA fleet gap, OSM vs RSA grid per voltage, OSM vs RSA substations, OSM vs St Clair line-ratings delta |
| [`11_fixed_capacity_network_build.md`](11_fixed_capacity_network_build.md) | Build fixed 2023 PyPSA-Earth network with no expansion and validated carrier/input attachment |
| [`12_dispatch_calibration_and_availability.md`](12_dispatch_calibration_and_availability.md) | Solve fixed dispatch, produce interim calibration reports, add availability/outage constraints only as needed |
| [`12_availability_provenance.md`](12_availability_provenance.md) | Companion to Module 12: source provenance for the coal-only station-weekly EAF overlay applied on top of the structural baseline |
| [`13_validation_reporting_and_acceptance.md`](13_validation_reporting_and_acceptance.md) | Produce final validation reports, tolerance checks, acceptance artifacts, provenance docs |
| [`13m_official_2023_fleet_reconciliation_and_sasol.md`](13m_official_2023_fleet_reconciliation_and_sasol.md) | Make 2023 coal fleet basis configurable, back up current `custom_powerplants.csv`, and test optional Sasol/conventional IPP inclusion |
| [`13n_calibration_demand_adjustment.md`](13n_calibration_demand_adjustment.md) | Replace RSA Contracted Demand with calibrated demand excluding unmodelled sources for 2023 dispatch calibration |
| [`14_expansion_and_reliability_handoff.md`](14_expansion_and_reliability_handoff.md) | Convert validated 2023 baseline into expansion-ready inputs without changing reliability solver contracts |

## Model Data Sources

Canonical map of which upstream data feeds which model input. Keep these four
files together — the markdown is the narrative source-of-truth, the three
`graph.*` files are renderings of the same dependency graph in different
formats.

| File | Purpose |
|---|---|
| [`model_data_sources.md`](model_data_sources.md) | Narrative source-of-truth: every model input, its upstream dataset, and the module that owns it |
| [`model_data_sources.graph.svg`](model_data_sources.graph.svg) | Dependency graph, SVG (interactive/zoomable) |
| [`model_data_sources.graph.png`](model_data_sources.graph.png) | Dependency graph, PNG (slide/report embed) |
| [`model_data_sources.graph.pdf`](model_data_sources.graph.pdf) | Dependency graph, PDF (print) |

## Archive

Intermediate working files preserved for provenance. These are no longer the
primary artifact for any module but are kept so the decision trail and prior
drafts remain auditable. Do not implement from these files directly — they have
been superseded by the numbered module specs above.

| File | What it is |
|---|---|
| [`archive/10_Sonnet_plan_draft.md`](archive/10_Sonnet_plan_draft.md) | Sonnet's early draft of Module 10, superseded by `10_earth_rsa_baseline_diagnostic.md` |
| [`archive/module11_findings_and_module12_inputs.md`](archive/module11_findings_and_module12_inputs.md) | Interim findings note from Module 11 used to feed Module 12 design |
| [`archive/module12_implementation_review_findings.md`](archive/module12_implementation_review_findings.md) | Review note on the Module 12 implementation pass |
| [`archive/module12_notebook_refactor_prompt.md`](archive/module12_notebook_refactor_prompt.md) | Prompt artifact used to refactor the Module 12 validation notebook |
| [`archive/module13_ocgt_investigation_report.md`](archive/module13_ocgt_investigation_report.md) | OCGT dispatch investigation sub-report produced during Module 13 work |
| [`archive/module13b_stock_baseline_prompt.md`](archive/module13b_stock_baseline_prompt.md) | Prompt artifact for the Module 13b stock baseline pass |
| [`archive/opus_brief_09b_and_11.md`](archive/opus_brief_09b_and_11.md) | Opus session brief covering Module 09b and 11 hand-off |
| [`archive/opus_brief_re_capacity_fix.md`](archive/opus_brief_re_capacity_fix.md) | Opus session brief on the capacity-fix investigation |
| [`archive/pre_11_questions.md`](archive/pre_11_questions.md) | Pre-Module 11 open questions captured before spec freeze |
| [`archive/pre_12_hydro_and_biomass.md`](archive/pre_12_hydro_and_biomass.md) | Pre-Module 12 notes on hydro and biomass treatment |
| [`archive/pre_module13_closeout_prompt.md`](archive/pre_module13_closeout_prompt.md) | Prompt artifact for closing out the pre-Module 13 investigation |
| [`archive/pre_module13_investigation_plan.md`](archive/pre_module13_investigation_plan.md) | Investigation plan written before Module 13 implementation |
| [`archive/review-findings-2026-05-07.md`](archive/review-findings-2026-05-07.md) | Early cross-module review findings (2026-05-07) |

## Freeze Rule

Implementation cannot begin until every row is:

```text
Codex status = agreed
Claude status = agreed
Freeze status = frozen
```

During implementation, each module must pass its own acceptance gates before the
next numbered module starts. If a module discovers that a later design decision
is wrong or incomplete, update the owning source-of-truth module and re-run the
Codex/Claude review for the affected module before proceeding.

Generic fresh-agent review prompt:

```text
docs/active/reviews/prompts/fresh_agent_za_baseline_review_brief.md
```
