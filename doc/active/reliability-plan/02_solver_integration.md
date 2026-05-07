# 02 Solver Integration

## Hook Location

Reliability constraints must be added inside PyPSA-Earth solve-stage
`extra_functionality`, after upstream constraints such as `BAU`, `SAFE`, `CCL`,
reserve, `RES`, `EQ`, battery, and bidirectional-link constraints.

V1 patches `scripts/solve_network.py` directly. Do not maintain a separate
replacement solve script in V1. A custom Snakemake rule alone is insufficient
because the inspected solve script hard-codes the `extra_functionality`
function passed to `n.optimize`.

## Reliability Hook

Before solving, attach:

```python
n.reliability_targets_path = snakemake.input.reliability_targets
```

The solve-stage code must be observation-source agnostic. It consumes the
standardized reliability target CSV only; it must not branch on the source
adapter, such as NTL proxy, measured uptime, or later observation adapters.

Inside `extra_functionality`:

```python
if n.config.get("reliability", {}).get("enable", False):
    target_df = read_reliability_targets(n.reliability_targets_path)
    if reliability_mode_is_constrained(n.config):
        add_reliability_constraints(n, snapshots, n.config, target_df)
    if reliability_budget_is_enabled(n.config):
        add_investment_budget_constraint(n, n.config)
```

Mode taxonomy:

```text
diagnostic: read targets and write diagnostics; do not add ENS constraints
ens_only: constrained mode; add ENS cap, slack, and slack penalty
ens_and_budget: constrained mode plus Reliability-budget
```

`scenario.mode` controls ENS-constraint enablement only. `budget.enable` is
orthogonal and may be true under any mode, including `diagnostic`. The two
`if`-guards above run independently, so a `diagnostic + budget.enable=true`
configuration is valid (used for Scenario 1) and produces a budgeted run with
no ENS cap.

All custom bus dimensions must be named `"bus"` and alignment-tested across LHS,
RHS, slack, and dual outputs.

`Reliability-allhours-cap` and `Reliability-slack` exist only in constrained
reliability modes. Diagnostic reliability modes read targets and write
diagnostics, but do not add those constraints.

`add_reliability_constraints` must also add the slack penalty to
`n.model.objective` in constrained reliability modes.

Implement the solver helpers in a small reliability module with at least:

```text
read_reliability_targets
validate_target_df
get_load_shedding_generators
build_bus_level_load_shedding_expr
build_bus_level_demand_param
add_reliability_constraints
add_investment_budget_constraint
collect_reliability_results
reliability_mode_is_constrained
reliability_budget_is_enabled
```

## Budget Constraint

When enabled, the investment budget is a hard no-slack `<=` constraint:

```text
Reliability-budget
```

`Reliability-budget` exists only when the reliability budget is enabled.

Validation must reject an active scenario with populated
`pathway.period_budgets` and `reliability.budget.enable: false`; do not silently
ignore configured budgets.

Dual access:

```python
n.model.constraints["Reliability-budget"].dual
```

If a low-budget constrained case cannot satisfy reliability targets,
`Reliability-slack` absorbs the ENS violation. Never add budget slack in V1.

The budget helper must walk only Linopy extendable-capacity variables that exist
in `n.model`, such as `Generator-p_nom`, `StorageUnit-p_nom`, and
`Store-e_nom`. This structurally excludes non-extendable load-shedding
generators; carrier exclusion remains a defensive guard.

Include transmission variables (`Line-s_nom` and DC `Link-p_nom`) in the V1
budget only if `04_carry_forward_contract.md` permits transmission
carry-forward for the selected run. Otherwise skip transmission budget terms.

## Solver Options

For V1 `myopic_elec_only`:

```yaml
solving:
  options:
    skip_iterations: true
```

Iterative transmission expansion is deferred until the reliability hook is
proven idempotent under repeated `extra_functionality` calls.

When `reliability.enable: true`, including overnight smoke tests, the solve call
must pass:

```python
assign_all_duals=True
```

Because V1 uses `skip_iterations: true`, this only needs to be wired through the
non-iterative `n.optimize` path until iterative solves are explicitly enabled.

Assert after solve that expected custom dual arrays are non-empty before writing
diagnostics:

```text
Reliability-allhours-cap.dual: required only in constrained reliability modes
Reliability-budget.dual: required only when the budget is enabled
```

Reliability mode flags must stay under `config["reliability"]`, not in the
hyphen-separated `opts` wildcard, to avoid collisions with upstream parsers.

## Diagnostics And Export

`collect_reliability_results` must run against the live solved network and live
`n.model` before `n.export_to_netcdf(snakemake.output.solved)` returns. Custom
Linopy variables, custom duals, and slack solutions are not guaranteed to be
available after export.

Reliability diagnostics are mandatory CSV outputs for every
reliability-enabled solve, including diagnostic mode. The solve rule should use
named outputs:

```python
output:
    solved="results/.../network.nc",
    reliability_results="results/.../bus_reliability_results.csv",
    reliability_summary="results/.../bus_reliability_summary.csv",
```

Then export:

```python
n.export_to_netcdf(snakemake.output.solved)
```

Every reliability CSV written by the solve script must be declared as a
Snakemake output because the solve rule uses shadow execution.

In diagnostic mode, write the same CSV schema with constraint, slack, and dual
columns present but marked not applicable where the corresponding custom
constraint or variable was not created.

## Noisy Costs

For V1, fail validation when `reliability.enable: true` and
`solving.options.noisy_costs` is enabled. Do not support post-prepare slack
penalty recalibration in V1.
