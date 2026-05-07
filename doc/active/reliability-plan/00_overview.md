# 00 Overview

## Purpose

Build a PyPSA-Earth electricity-only planning workflow that uses observed
reliability information to define spatial all-hours ENS targets and studies how
budget-constrained expansion reallocates investment toward underserved regions.
For data-scarce systems, satellite nighttime lights are the V1 proxy for this
observed reliability layer. For data-rich systems, measured TSO/substation or
local-area uptime can feed the same target-building interface.

## Locked V1 Scope

- V1 reliability constraint method is the deterministic single-shot LP with ENS
  cap plus slack penalty per
  [[3-wiki/decisions/2026-05-07-v1-reliability-implementation-uses-deterministic-eens-constraints|DEC-002]];
  Lagrange relaxation is conceptual reference only.
- Country: South Africa.
- Primary empirical input for the South Africa thesis run: 2023 NTL-derived
  service-deficit proxy; the observation-year reproducibility lock is owned by
  `06_reproducibility_and_scenarios.md`.
- Observation abstraction: source-specific reliability observations are
  standardized to bus-level `r_b_obs` before target building. V1 implements
  `ntl_proxy`; measured uptime is the data-rich adapter contract.
- Primary model: PyPSA-Earth electricity-only workflow.
- Primary pathway mode: project-specific `foresight: myopic_elec_only`.
- Primary reliability constraint: all-hours annual bus-level ENS constraint.
- Late-night ENS: diagnostic and robustness output only.
- Investment basis: annualized PyPSA-Earth `capital_cost`, not overnight CAPEX;
  the budget frontier and `I_baseline_y` definition are owned by
  `06_reproducibility_and_scenarios.md`.
- Main pathway: 2030 -> carry capacity -> 2040 -> carry capacity -> 2050.
- Full thesis cluster target: `clusters: 34`, aligned to the Eskom 34 local
  areas through a custom busmap/supply-region clustering layer; small generic
  clusters are used first for smoke tests and dry-runs.

## Required Configuration Surface

The implementation must expose these configuration concepts under
`config["reliability"]`:

- `enable`
- `observations.source`
- `observations.spatial_unit`
- `observations.metric`
- `scenario.mode`
- `scenario.gamma`
- `scenario.improvement_eta`
- `budget.enable`
- `budget.limit`
- `slack.penalty_eur_per_mwh`
- `diagnostics.compute_late_ens`
- `pathway.period_budgets`
- `pathway.improvement_eta_by_horizon`
- `pathway.cost_year_by_horizon`
- `pathway.demand_assumption_by_horizon`
- `pathway.policy_assumption_by_horizon`
- `pathway.carry_forward_mode_by_component`
- `pathway.exclude_carriers_from_budget_and_carry_forward` (V1 default
  includes at minimum `"load shedding"`; additional dummy/balancing carriers
  may be added as they are discovered)

For `myopic_elec_only`, horizon-specific pathway fields override single-period
scenario fields. `null` is invalid for required horizon mappings.

Solver reproducibility keys must also be locked in the active PyPSA-Earth
config, including the selected Gurobi solver-options block, `Threads`, `Method`,
`Crossover`, `BarConvTol`, and `Seed`.

## Non-Goals

- Do not claim NTL estimates true regional VOLL.
- Do not require NTL when measured uptime is available; NTL is the data-scarce
  adapter, not the solver contract.
- Do not diagnose exact outage causes such as distribution, affordability, or
  local backup behavior.
- Do not use upstream `foresight: myopic`; it is sector-coupled and not the V1
  electricity-only pathway.
- Do not begin implementation until every source-of-truth module is agreed by
  Claude and Codex and marked frozen in `index.md`.

## Core Implementation Chain

```text
source-specific reliability observations
-> bus-level observed unreliability r_b_obs
-> horizon-specific all-hours ENS targets
-> PyPSA-Earth electricity-only solve with load shedding enabled
-> bus-level ENS constraints in extra_functionality
-> hard period-specific investment budget
-> myopic_elec_only pathway with carried capacity
-> diagnostics, duals, slack, budget flags, representation-gap outputs
```

## Main Scenarios

- Diagnostic historical validation: load shedding enabled, no reliability
  constraint, compare modeled scarcity and observed reliability signal.
- Budget-constrained baseline: least-cost expansion with budget only.
- Observed-reliability-informed all-hours ENS: budget plus bus-level ENS targets
  and slack.
- Planning-horizon pathway: 2030, 2040, 2050 with carried capacity.
- EENS weather robustness: mandatory final thesis result after deterministic ENS
  works; the weather-year list is configurable in
  `06_reproducibility_and_scenarios.md` with default
  `[2019, 2020, 2021, 2022, 2023, 2024]`.
- ENS stringency frontier: vary `Budget_y` and `eta_y`.
- Observed-reliability-priority VOLL sensitivity: optional penalty-weight
  comparison, not main interpretation.

Detailed budget frontier and scenario definitions are owned by
`06_reproducibility_and_scenarios.md`.

## Research Claim

The defensible claim is that empirical observed-reliability information can
guide reliability targets in capacity expansion planning. In data-scarce
systems, NTL provides a proxy for spatial service-deficit risk. In data-rich
systems, measured uptime can replace that proxy at the observation layer. Results
must be framed as model-conditional planning signals, not direct measurements of
true customer outage cost.
