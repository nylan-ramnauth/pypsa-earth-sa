# South Africa Baseline Model Source Of Truth

Status: `review-updated 2026-05-07`. This folder is the active implementation-order contract for
making PyPSA-Earth a robust and accurate South Africa 2023 baseline model. It is
separate from the observed-reliability ENS + `myopic_elec_only` feature plan in
`doc/active/reliability-plan/`.

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
| `00_governance_and_scope.md` | Non-implementation scope, review protocol, relationship to reliability/myopic workstream |
| `01_repo_bootstrap_and_config.md` | Repo inspection, local ZA folders, config overlays, solver/environment locks, provenance skeleton |
| `02_eskom_validation_data_pipeline.md` | Repair Eskom 2023 data, produce clean hourly validation data and annual targets |
| `03_weather_cutout_and_profiles.md` | Build/smoke-test 2023 ERA5 cutout and renewable profiles, including CSP fallback policy |
| `04_source_data_audits.md` | Extract powerplantmatching, PyPSA-RSA, REIPPPP, profile, availability, grid, and transmission candidate audit tables |
| `05_system_boundary_and_carrier_taxonomy.md` | Lock national boundary, embedded PV, CSP, OCGT, Sasol, hydro imports, storage carriers |
| `06_demand_import_export_model_inputs.md` | Produce 8760 demand, import, export, sign-convention, load-allocation, and bus-attachment artifacts |
| `07_costs_fuels_efficiencies_and_coUE.md` | Lock costs, fuels, efficiencies, emissions, local carrier cost rows, and COUE/load-shedding cost units |
| `08_fleet_reconciliation_and_custom_powerplants.md` | Reconcile plant fleet, freeze `custom_powerplants.csv`, smoke-test normalization |
| `09_grid_spatial_and_transmission_model.md` | Audit OSM grid, RSA supply regions, custom busmap/subregions, optional corridor caps |
| `10_earth_rsa_baseline_diagnostic.md` | Diagnostic only: quantify PPM vs RSA fleet gap, OSM vs RSA grid per voltage, OSM vs RSA substations, OSM vs St Clair line-ratings delta |
| `11_fixed_capacity_network_build.md` | Build fixed 2023 PyPSA-Earth network with no expansion and validated carrier/input attachment |
| `12_dispatch_calibration_and_availability.md` | Solve fixed dispatch, produce interim calibration reports, add availability/outage constraints only as needed |
| `13_validation_reporting_and_acceptance.md` | Produce final validation reports, tolerance checks, acceptance artifacts, provenance docs |
| `14_expansion_and_reliability_handoff.md` | Convert validated 2023 baseline into expansion-ready inputs without changing reliability solver contracts |

## Review Status

| Module | Codex status | Claude status | Open blockers | Freeze status |
|---|---|---|---|---|
| `00_governance_and_scope.md` | review fixes applied | agreed | none | frozen after path clarification |
| `01_repo_bootstrap_and_config.md` | review fixes applied | needs re-review | none | pending re-freeze after overlay/solver-lock review |
| `02_eskom_validation_data_pipeline.md` | review fixes applied | needs re-review | none | pending re-freeze after raw-data path/source-column review |
| `03_weather_cutout_and_profiles.md` | review fixes applied | needs re-review | none | pending re-freeze after clean-repo cutout review |
| `04_source_data_audits.md` | review fixes applied | agreed | none | frozen after duplicate/commit checks |
| `05_system_boundary_and_carrier_taxonomy.md` | review fixes applied | needs re-review | none | pending re-freeze after biomass/local-carrier review |
| `06_demand_import_export_model_inputs.md` | blocker resolved | needs re-review | none | pending re-freeze after GEGIS integration-contract review |
| `07_costs_fuels_efficiencies_and_coUE.md` | review fixes applied | needs re-review | none | pending re-freeze after cost-year/load-shedding review |
| `08_fleet_reconciliation_and_custom_powerplants.md` | review fixes applied | needs re-review | none | pending re-freeze after custom_powerplants header/filter review |
| `09_grid_spatial_and_transmission_model.md` | review fixes applied | needs re-review | none | pending re-freeze after Eskom-34 custom-busmap review |
| `10_earth_rsa_baseline_diagnostic.md` | implemented | in progress | none | pending verification run |
| `11_fixed_capacity_network_build.md` | review fixes applied | needs re-review | none | pending re-freeze after local-hook/audit-schema review |
| `12_dispatch_calibration_and_availability.md` | review fixes applied | needs re-review | none | pending re-freeze after output-wildcard/EAF-input review |
| `13_validation_reporting_and_acceptance.md` | review fixes applied | agreed | none | frozen after provenance/PHS detection clarification |
| `14_expansion_and_reliability_handoff.md` | review fixes applied | needs re-review | none | pending re-freeze after reliability-handoff review |

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

Completed focused refinement review item:

```text
PyPSA-Earth validation-notebook reuse
```

Scope is limited to the additive validation/reporting refinements in `00`, `03`,
`08`, and `12`. Do not reopen `01`, `02`, `04`, `05`, `06`, `07`, `09`, `10`,
`11`, or `13` unless the focused review finds a direct contradiction.
