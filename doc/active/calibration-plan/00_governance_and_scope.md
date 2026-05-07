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
