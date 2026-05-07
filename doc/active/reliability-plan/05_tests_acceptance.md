# 05 Tests And Acceptance

## Review Freeze Gate

Implementation cannot start until `doc/active/reliability-plan/index.md` marks
all modules:

```text
Codex status = agreed
Claude status = agreed
Freeze status = frozen
```

## Required Fixtures

Run fixtures before any full South Africa scenario:

- Observation fixture: source-specific observations are converted to the
  standardized bus-level schema; every active bus maps to a real bus region;
  support classes and exclusion reasons are populated; all-hours demand is
  positive for active constrained buses. V1 must test the `ntl_proxy` adapter.
  The fixture must assert every standardized schema column from
  `01_reliability_formulation.md` is present with the expected type.
  A non-blocking measured-uptime fixture spec should verify that
  local-area/substation/bus uptime can produce the same schema and identical
  targets for the same synthetic `uptime_b` when a data-rich source is added.
- ENS fixture: tiny network, load-shedding dispatch from `Generator-p`, weighted
  ENS matches manual calculation using `n.snapshot_weightings.generators`.
- Budget fixture: greenfield, lower-bound brownfield, fixed-brownfield plus
  candidate, zero-budget, and low-budget cases.
- Dual-sign fixture: known binding custom `<=` constraint, tested sign
  convention for ENS and budget duals.
- Carry-forward fixture: `Generator`, `StorageUnit`, `Store`, `Line`, and
  `Link`; verifies capacity propagation and no recharging of fixed carried
  capacity. It must also verify zero-min candidate reset, `StorageUnit` explicit
  handling, `keep_existing_capacities: false` after base year, collision/drop
  logging, threshold-drop logging, and
  `carried_capacity_{planning_horizons}.csv` schema.
- Transmission fixture: Stage 2 unlock gate for final thesis pathway runs. It
  verifies `Line-s_nom` and DC/transmission `Link-p_nom` lower-bound
  carry-forward under `transmission_expansion_*_limit`.
- Iteration fixture: asserts that the active config sets
  `solving.options.skip_iterations: true` AND that
  `n.optimize.optimize_transmission_expansion_iteratively` is never invoked in
  the V1 reliability solve path (assert via call counter or import-level guard
  in the patched `solve_network.py`). Proving reliability hook idempotency
  before iterations are enabled is a V2 path, not required for V1 freeze.

The transmission fixture must prove:

- reliability budget terms use `capital_cost * (optimized_capacity -
  carried_minimum)` for lower-bound transmission assets
- carried transmission minima are not charged again
- upstream transmission global limits and the reliability budget do not charge
  or constrain the same carried capacity inconsistently
- if carried minima already saturate an upstream transmission limit, further
  transmission expansion is disabled and `transmission_limit_saturated` is
  reported
- final thesis pathway scenarios fail validation if this gate has not passed
  or if transmission budget terms are silently omitted

## Solver Integration Gates

The small solve must verify:

- load-shedding generators are found by carrier `"load shedding"`
- `Reliability-allhours-cap` and `Reliability-slack` exist with the intended
  dimensions in constrained reliability modes
- reliability variables and constraints use the `"bus"` dimension consistently
- `Reliability-budget` exists with the intended dimensions only when the budget
  is enabled
- `Reliability-budget` is hard and has no slack
- reliability penalty is added via `n.model.objective = ...`
- reliability-enabled solve passes `assign_all_duals=True`
- expected custom ENS and budget dual arrays are non-empty after solve,
  conditional on constrained reliability mode and budget enablement
- `collect_reliability_results` reads live `n.model` before
  `n.export_to_netcdf(...)` returns
- exported `ENS_b_all` matches a manual weighted load-shedding sum for the same
  solved network
- reliability CSVs are declared Snakemake outputs and survive shadow execution
- diagnostic mode writes the same reliability CSV schema as constrained modes,
  with not-applicable markers for constraint, slack, and dual columns that are
  not created
- non-uniform slack weights, if used, are normalized and exported with the
  effective local slack penalty
- `noisy_costs` plus reliability fails validation in V1

Stage 1 runs without transmission budget terms are allowed only as smoke tests
or explicitly labeled pre-verification sensitivity runs. They cannot be used as
final thesis pathway evidence.

## Workflow Dry-Run Gates

The first `myopic_elec_only` dry-run must prove:

- three horizons appear in chronological order
- all electricity and reliability artifacts are `{planning_horizons}`-tagged
- the same clustered topology and bus mapping are used across pathway horizons
- horizon-aware preprocessing rules appear in the DAG, including
  `build_demand_profiles_myopic_elec`, `add_electricity_myopic_elec`,
  `simplify_network_myopic_elec`, `cluster_network_myopic_elec`,
  `augmented_line_connections_myopic_elec` if enabled,
  `add_extra_components_myopic_elec`, and `prepare_network_myopic_elec`
- previous solved horizon is explicit input to the next `add_elec_brownfield`
- `add_existing_elec_baseyear` runs exactly once, only for the first planning
  horizon, with the matching `ruleorder` and `wildcard_constraints`
- no network, target, result, or diagnostic path collides across horizons
- every horizon has complete `cost_year_by_horizon`,
  `demand_assumption_by_horizon`, and `policy_assumption_by_horizon`
- GEGIS load inputs resolve through the horizon helper or validated
  `expected_region_files`
- mapped electricity cost files are generated or present
- reused summary/plot rules use horizon-mapped cost files
- unsupported Monte Carlo mode fails clearly
- custom rules have helper names in scope or duplicated locally
- non-monotone `eta_y` fails validation
- `null` in required horizon mappings fails validation
- `enable.retrieve_cost_data: false` without an explicit local cost strategy
  fails validation

## Smoke And Scaling Sequence

After fixtures pass:

1. Overnight small-cluster reliability smoke test with `skip_iterations: true`
   and `reliability.scenario.mode: diagnostic`.
2. Three-horizon dry-run for `solve_elec_myopic_pathway`.
3. Real three-horizon small-cluster South Africa run in a constrained mode:
   `ens_only` or `ens_and_budget`.
4. Validate pathway summary, carried-capacity tables, ENS diagnostics, budget
   flags, custom duals, and horizon assumption summary.
5. Transmission fixture passes; pathway scenarios include `Line-s_nom` and
   DC/transmission `Link-p_nom` in the reliability budget set. Otherwise the
   full thesis run fails validation.
6. Scale to the locked `clusters: 34` full thesis run only after all gates pass.
7. Run Scenario 4 weather-year EENS cases only after deterministic ENS pathway
   outputs pass per
   [[3-wiki/decisions/2026-05-07-v1-reliability-implementation-uses-deterministic-eens-constraints|DEC-002]];
   validate weather-year inputs, scenario probabilities, EENS summaries, and
   final robustness conclusions.

## Acceptance Outputs

The accepted implementation must produce:

- unconstrained `myopic_elec_only` baseline pathway summary with per-horizon
  `I_baseline_y` (declared acceptance artifact required by Scenarios 1-3)
- bus reliability observations and mapping diagnostics
- observation source metadata: `observation_source`, `observation_metric`,
  `observation_year`, support counts, aggregation weights, and exclusion reasons
- bus reliability targets by horizon
- solved network per horizon
- bus reliability results by horizon
- bus reliability summary by horizon
- `carried_capacity_{planning_horizons}.csv` for every horizon after the first,
  including `transmission_limit_saturated`
- horizon assumption summary
- pathway summary with `Budget_y`, `I_new,y`, cumulative investment, ENS, slack,
  duals, binding flags, representation-gap flags, and a four-way total-cost
  decomposition (`operational_cost`, `investment_cost`, `load_shedding_cost`,
  `reliability_slack_penalty`) so constrained-vs-unconstrained comparisons
  isolate the reliability penalty term from operational and investment cost
- Scenario 4 EENS/weather-robustness summary with weather years, scenario
  probabilities, `ENS_b,s,all`, `EENS_b_all`, slack, and budget treatment

For final thesis pathway scenarios, the accepted pathway summary must include
verified transmission expansion in the reliability budget set.
