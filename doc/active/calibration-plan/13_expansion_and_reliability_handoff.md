# 13 Expansion And Reliability Handoff

## Goal

Turn the accepted 2023 South Africa baseline into a controlled starting point
for brownfield expansion and, later, reliability/myopic handoff.

## Handoff Artifact Table

The handoff package must include a machine-readable and markdown table with:

```text
artifact_name
path
hash
owner
accepted_validation_stage
baseline_only_or_future_scenario_input
receiving_contract
notes
```

Output paths:

```text
data/za_audit/za_handoff_artifact_table.csv
data/za_audit/za_baseline_reliability_diff.csv
doc/za_handoff.md
```

Minimum rows:

| Artifact | Owner | Receiving contract |
|---|---|---|
| validated 2023 solved network or buildable network artifacts | ZA 10/12 | reliability `07_implementation_handoff.md` network input |
| frozen `data/custom_powerplants.csv` | ZA 08 | reliability `07_implementation_handoff.md` fleet input |
| demand/import/export/other_re series | ZA 06/12 | reliability `07_implementation_handoff.md` demand and exogenous series input |
| local carrier cost rows | ZA 07/12 | reliability `07_implementation_handoff.md` cost/local carrier input |
| Eskom-34 busmap and grid/spatial mapping | ZA 09/12 | reliability `07_implementation_handoff.md` busmap/grid input |
| availability assumptions | ZA 11/12 | reliability `07_implementation_handoff.md` availability input |
| reliability stringency parameters | ZA 13 | reliability `07_implementation_handoff.md` `za_reliability_eta_y.csv` input |
| Scenario 4 weather-year cutout readiness | ZA 03/13 | reliability `07_implementation_handoff.md` weather-year input |
| observation schema adapter output | external observation workstream | reliability `07_implementation_handoff.md` observation GeoParquet input |
| retirement and future-asset policy | ZA 13 | reliability `07_implementation_handoff.md` brownfield/future asset input |
| validation report | ZA 12 | reliability `07_implementation_handoff.md` validation evidence |
| provenance report | ZA 01/04/12 | reliability `07_implementation_handoff.md` provenance evidence |
| limitations report | ZA 12 | reliability `07_implementation_handoff.md` accepted limitations |

Each receiving contract must name the target subsection in reliability
`07_implementation_handoff.md`. At minimum: `## 3 External Input Contract` for
Eskom-34 busmap and ZA exogenous series, `## 3 Cost data` for local carrier cost
rows, and `## 5 Snakemake Stubs` or the matching repo-layout subsection for
network/fleet solve inputs. If a subsection does not yet exist, open a follow-up
review item against reliability `07` before reliability implementation consumes
the artifact.

## Brownfield Transition Decisions

Before expansion implementation, lock:

- how the 2023 fleet carries into future years.
- retirement dates and lifetime assumptions.
- TDP planned lines default to scenario-only entry unless a reviewed expansion
  scenario promotes them to fixed builds.
- whether transmission expansion is allowed and under which corridor limits.
- REDZ, power corridors, EIA, SAPAD/SACAD, SKA, land-cover, and MTS hosting
  constraints for renewable expansion.
- future contracted projects default to `scenario_dependent` unless a reviewed
  source explicitly locks them as fixed builds, candidates, or exclusions.
- how 2023 calibration parameters carry forward without overfitting.

Required transition artifacts:

```text
data/za_audit/za_retirement_policy.csv
data/za_audit/za_future_asset_policy.csv
data/za_audit/za_reliability_eta_y.csv
doc/za_brownfield_transition_decisions.md
```

`za_retirement_policy.csv` columns:

```text
asset_id
carrier
retirement_year
source
applies_to_horizon
```

Coal retirements use IRP 2023 as the canonical source unless a later reviewed
source supersedes it. If pypsa-rsa fleet data contain usable unit retirement
dates, audit and record them as additional evidence before locking the policy.

`za_future_asset_policy.csv` columns:

```text
asset_id
carrier
treatment  # fixed_build, candidate, excluded, scenario_dependent
build_year
source
```

## Reliability Slack Penalty Basis

### Reliability slack penalty basis

The reliability slack penalty used in the Reliability Plan's deterministic EENS constraint
(per DEC-002) must reference the policy CoLS, not the solver safety-valve cost.

Handoff parameter:
- `eens_slack_penalty_zar_per_mwh: 116570`  (CSIR primary, 2024 ZAR)
- `eens_slack_penalty_sensitivity_zar_per_mwh: 9530`  (Nova Economics lower bound, 2018/19 ZAR)

These values must appear in `data/za_baseline_reliability_diff.csv` and be documented
in `doc/za_implementation_log.md` at Module 13 completion.

## Future-Year Carry-Forward Exclusions

The following must not enter 2030/2040/2050 without explicit scenario source and
review:

- 2023 renewable correction factors.
- 2023 outage levels.
- dispatch-calibration constraints introduced only to match 2023.
- temporary 2023 data repairs or fallback profiles.

Structural assumptions, source provenance, fleet retirement policy, validated
spatial/grid mapping, and reviewed local carrier definitions may carry forward
when the receiving reliability/myopic module accepts them.

### EAF carryforward policy

The 2023-calibration EAF values (carrier-level monthly EAF from Eskom data) are used for the
historical baseline validation only. They are NOT automatically carried forward into 2030/2040/2050
expansion scenarios.

The Reliability Plan (Reliability module 07) owns the decision on what availability assumptions to
use for expansion years. Do not hardcode 2023 EAF values into scenario configs.

## CSP Fallback Handoff Status

If V1 uses a temporary CSP fallback, the handoff table must mark it explicitly.
Temporary CSP fallback may not be used for final reliability claims unless the
limitation is explicitly accepted in `12_validation_reporting_and_acceptance.md`
and in the receiving reliability/myopic handoff contract.

## Reliability Receiving-Contract Bindings

This module may supply:

- validated South Africa base network.
- validated custom plant fleet.
- validated grid/bus-region representation.
- demand, import, export, and `other_re` series.
- local carrier costs and reporting metadata.
- availability, retirement, and future-asset assumptions.
- validation, provenance, and limitations reports.

Each supplied artifact must have a receiving entry in
`doc/active/reliability-plan/07_implementation_handoff.md` before reliability
implementation consumes it. The Eskom-34 busmap producer is ZA module `09`, not
the reliability handoff module.

Handoff-specific rows:

- `data/custom_busmap_elec_s_34.csv` is the V1 Eskom-34 busmap path.
- `data/za_audit/za_reliability_eta_y.csv` stores configurable defaults:
  `2030: 0.25`, `2040: 0.60`, `2050: 0.90`; values are parameters, not
  hardcoded constants.
- Scenario 4 weather years default to `[2019, 2020, 2021, 2022, 2023, 2024]`
  and must be configurable. The clean-repo assumption means cutouts are built
  unless a dry-run detects and hashes an existing cutout; 2023 is the base
  weather year for fixed validation.
- Observation production is external to pypsa-earth. The model consumes
  `data/reliability/observations/ntl_settlement_2023.parquet` as GeoParquet
  with `settlement_id`, `geometry`, `population`, `uptime`, `n_observations`,
  `source_year`, and CRS `EPSG:4326`.

It must not change:

- ENS target formulation.
- reliability budget formulation.
- dual/export rules.
- myopic carry-forward contract.
- scenario definitions owned by `doc/active/reliability-plan/`.

## Acceptance Gates

- Handoff artifact table exists with path, hash, owner, accepted stage,
  baseline/future-scenario classification, and receiving contract.
- Retirement and future-asset policy CSVs exist with the required schemas.
- Future-year carry-forward exclusions are documented.
- CSP fallback status is recorded if relevant.
- Differences between baseline assumptions and reliability/myopic assumptions are
  listed in `data/za_audit/za_baseline_reliability_diff.csv`.
- Required receiving entries in
  `doc/active/reliability-plan/07_implementation_handoff.md` are opened as
  follow-up review items or added after this table exists.
- Any required changes to frozen reliability/myopic modules are opened as
  separate review items, not made implicitly.
