# 00 Governance And Scope

## Purpose

Create a robust South Africa 2023 PyPSA-Earth electricity baseline that can be
used for thesis validation and later brownfield expansion. The baseline must
reconcile plant fleet, weather profiles, demand, grid representation, dispatch
constraints, and validation outputs against South Africa-specific evidence.

## Distinct Workstreams

- South Africa baseline: country-specific model layer and validation workflow.
- Reliability/myopic feature: generic PyPSA-Earth planning method in
  `doc/active/reliability-plan/`.
- This plan may produce inputs used by the reliability/myopic plan, but it must
  not redefine ENS constraints, investment-budget logic, carry-forward logic, or
  reliability solver hooks.
- The active plan files live in the vault under `6-codebases/Plans/`; Track 1
  bootstrap mirrors the reliability plan into the pypsa-earth fork at
  `doc/active/reliability-plan/` before implementation consumes it.

## Implementation Rule

The plan is ordered for sequential implementation. The implementing agent must
finish module `01`, pass its gates, then move to `02`, and so on. Later modules
may read earlier outputs but must not silently change earlier contracts.

## Non-Goals

- Baseline claims are limited to South Africa source reconciliation,
  fixed-capacity 2023 validation, and handoff readiness. Reliability policy
  results are owned by the separate reliability/myopic workstream.
- Do not port PyPSA-RSA wholesale.
- Do not treat PyPSA-RSA scenario files as active run configs.
- Do not begin expansion or reliability-index implementation before the fixed
  2023 validation baseline is accepted.
- Do not put South Africa-only assumptions into global PyPSA-Earth defaults when
  a local config overlay or local hook is enough.
- Do not implement from `background/` or `archive/` files unless this index
  explicitly makes a file normative.

## Governance Locks

- V1 prioritizes thesis-local reproducibility while using PyPSA-Earth
  configs/scripts and upstream-friendly hooks where practical.
- ZA validation reports may adapt upstream PyPSA-Earth validation notebook
  idioms when they remain reproducible, upstream-friendly, and secondary to the
  South Africa source hierarchy locked in this plan.
- Validation acceptance is staged in `12_validation_reporting_and_acceptance.md`
  as annual, monthly, hourly, then regional/handoff readiness.
- Module `03` has Gate A for profile generation and Gate B for deferred
  PyPSA-RSA profile comparison after `04`; Gate B does not block module `10`
  or `11` and blocks only final acceptance in `12`.

## Implementation Log Contract

Every module in this plan has a hard acceptance gate: before the implementing agent marks any module complete,
it must append a structured entry to `doc/za_implementation_log.md` at the pypsa-earth repo root.

### Log file: `doc/za_implementation_log.md`

Create this file if it does not exist. Append one entry per module completion using the following schema:

```
## [MODULE_ID] [MODULE_NAME] — [YYYY-MM-DD HH:MM]

- **Status:** complete | partial | blocked
- **Decisions taken:** (bullet list of implementation choices not already in the plan)
- **Deviations from plan:** (what was changed relative to the plan and why)
- **Source inputs used:** (file paths, commit hashes, URLs relied upon)
- **Output artifacts produced:** (file paths written or modified)
- **Open follow-ups:** (anything that must be addressed in a later module)
```

This log is mandatory. No module is considered complete without its log entry.

## Validation Notebook Policy

Every module that produces a validation artifact must also produce a Jupyter notebook.

### Notebook locations

| Module | Notebook path |
|---|---|
| 02 | `notebooks/za_validation/02_eskom_data/parser_report.ipynb` |
| 03 | `notebooks/za_validation/03_profiles/profile_validation.ipynb` |
| 06 | `notebooks/za_validation/06_demand/demand_io_otherre.ipynb` |
| 08 | `notebooks/za_validation/08_fleet/fleet_reconciliation.ipynb` |
| 10 | `notebooks/za_validation/10_network/fixed_network_audit.ipynb` |
| 11 | `notebooks/za_validation/11_dispatch/dispatch_calibration.ipynb` |
| 12 | `notebooks/za_validation/12_acceptance/acceptance_report.ipynb` |
| 12 | `notebooks/za_validation/12_acceptance/before_after_comparison.ipynb` |

### Notebook requirements

Each notebook must:
1. Read from canonical CSV/netCDF outputs — no hardcoded data
2. Use PyPSA and PyPSA-Earth canonical plotting idioms (use context7 to fetch `pypsa` and `pypsa-earth` documentation for plotting functions such as `plot_dispatch`, `plot_capacities`, `n.plot()`)
3. Produce complete graphs and charts with titles, axis labels, units, and legends
4. Run end-to-end without manual intervention from clean inputs
5. Export a static HTML version to `doc/za_validation/figures/<module>/`

Notebooks are presentation-ready artifacts. The user must be able to show them directly to their supervisor.

## Baseline Build Chain

```text
repo bootstrap and ZA config overlays
-> clean Eskom 2023 validation data
-> build 2023 weather cutout and renewable profiles
-> extract all candidate data audits
-> lock system boundary and carrier taxonomy
-> produce demand, import, export, load-allocation, and bus-attachment inputs
-> lock costs, fuels, efficiencies, emissions, and COUE/load-shedding cost
-> reconcile plant fleet and custom_powerplants.csv
-> build/audit spatial grid and transmission representation
-> build fixed-capacity 2023 network
-> solve and calibrate dispatch/availability
-> produce validation reports and acceptance artifacts
-> hand off expansion-ready baseline inputs
```
