# 01 Reliability Formulation

## Observation Source Contract

The reliability preprocessing layer is data-agnostic. It converts a
source-specific observed reliability dataset into standardized bus-level
observed unreliability, `r_b_obs`, before PyPSA-Earth target building. The
solver and Linopy constraints must consume only the standardized target table,
not the original observation source.

Supported source contracts:

```text
ntl_proxy: settlement-level NTL uptime, settlement geometry, and population
measured_uptime: measured TSO/substation/local-area/bus uptime and a bus mapping
```

For the South Africa V1 thesis run, `observations.source = ntl_proxy`. For
data-rich systems, `observations.source = measured_uptime` uses the same target
builder after converting measured uptime to bus-level uptime.

For NTL settlement input:

```text
uptime_s = share of valid light-observed days over the observation year for settlement s
```

For measured uptime input:

```text
uptime_i = measured service-availability share for substation, local area, or bus i
```

The observation builder aggregates the active source to the active model bus
regions for the current run. For the locked `clusters: 34` thesis run, those bus
regions should align with Eskom local areas through the custom
busmap/supply-region layer. For any other cluster count, aggregate observations
to the actual PyPSA bus-region polygons used by that run.

The standardized bus-level observed reliability table must contain at least:

```text
bus
observation_source
observation_metric
observation_year
uptime_b
r_b_obs
active_constraint
exclusion_reason
support_count
aggregation_weight
```

`support_count` is the number of source observations mapped to bus `b`
(settlements for `ntl_proxy`; source records/areas/assets for
`measured_uptime`). `aggregation_weight` is the per-bus sum of the raw weights
used in the weighted mean, such as population, load, customer count, coverage,
or explicit equal weights.

The standardized bus-level observed unreliability index is:

```text
uptime_b = weighted mean uptime over observations mapped to bus b
r_b_obs = 1 - uptime_b
```

For `ntl_proxy`, use population weights as the default settlement-to-bus
aggregation weight. For `measured_uptime`, use the source-provided coverage,
load, customer, or population weight when available; otherwise use an explicitly
reported equal-weight fallback. The standardized CSV reports the aggregate
per-bus weight, not every input-side observation weight. `r_b_obs` is not VOLL
and is not a physical outage diagnosis. It is used to set relative improvement
targets for spatially underserved buses.

Each active bus must map to a real clustered bus region. If a bus has no mapped
observation input, keep it in diagnostics with `active_constraint=false` and an
exclusion reason. Detailed source-specific data-quality filtering is owned by
the empirical observation pipeline, not by the PyPSA-Earth reliability
constraint builder.

## Demand And ENS Targets

For each horizon `y` and active bus `b`:

```text
D_b,y,all = sum_t w_t * load_b,t,y
ENS_limit_b,y,all = (1 - eta_y) * gamma * r_b_obs * D_b,y,all
ENS_b,y,all <= ENS_limit_b,y,all + slack_b,y
```

Implementation requirements:

- Use all solved snapshots for the active V1 constraint.
- Use `n.snapshot_weightings.generators` for both demand targets and ENS LHS.
- Exclude buses with `D_b,y,all <= epsilon_demand` from active constraints and
  keep them in diagnostics with an exclusion reason.
- Constrain all buses with mapped observation input and positive all-hours
  demand.
- Treat `target_quantile` as diagnostic/reporting-only in V1 unless a separate
  targeted-bus policy scenario is explicitly enabled.
- Central pathway values are `eta_2030 = 0.25`, `eta_2040 = 0.60`, and
  `eta_2050 = 0.90`; non-monotone pathways fail validation.
- Eta values for each horizon must be exposed as config parameters under
  `reliability.pathway.improvement_eta_by_horizon[y]`; they are defaults, not
  hardcoded constants. Scenario sweeps and Scenario 5 stringency frontiers
  change them at runtime.
- Central `gamma = 1.0`; `gamma` is global for V1 unless Scenario 5 sensitivity
  changes it.

## ENS LHS

Modeled ENS is load-shedding generator dispatch:

```text
ENS_b,y,all = sum_t w_t * Generator-p[t, load_shedding_generators_at_b]
```

Load shedding must be selected by carrier:

```text
n.generators.carrier == "load shedding"
```

Name suffix matching is fallback only.

## Slack

Slack is an MWh variable over active buses:

```text
Reliability-slack[bus] >= 0
```

Slack penalty is added to `n.model.objective`. The penalty is reported in
EUR/MWh. V1 target is `100,000 EUR/MWh`. `solving.options.load_shedding` is
stored in EUR/kWh in upstream PyPSA-Earth and `solve_network.py` multiplies it
by `1000` to EUR/MWh. Therefore:

```text
slack.penalty_eur_per_mwh = load_shedding_eur_per_kwh * 1000
```

With the upstream default `load_shedding = 100 EUR/kWh`, the reconciled slack
penalty is `100,000 EUR/MWh`. Lock the unit in
`07_implementation_handoff.md` Section 4. `noisy_costs` is not allowed with
reliability in V1.

Non-uniform slack weights use population-weighted mean 1 normalization by
default. Report both base and effective local slack penalty.

## Duals And Interpretation

Read custom duals from the live Linopy model:

```python
n.model.constraints["Reliability-allhours-cap"].dual
n.model["Reliability-slack"].solution
```

Binding flags must use primal residual plus tested sign-normalized or absolute
dual logic. Do not rely on an unverified signed-dual comparison.

Dual interpretation:

```text
model-implied marginal system cost of tightening the bus ENS limit by 1 MWh
```

This is not customer VOLL. It is conditional on the model, budget, slack
penalty, represented network, and active candidate set. If slack is used, report
dual values alongside realized slack and local slack penalty.

## Diagnostics

Every reliability scenario reports:

- modeled all-hours ENS by bus
- ENS limit and residual
- slack MWh and slack share
- raw dual, sign-normalized dual, primal residual, binding flag
- late-night ENS diagnostic if timestamp-like snapshots support it; skip or mark
  invalid when snapshots are non-timestamp-like or too coarsely aggregated
- representation-gap flags for high observed unreliability but low modeled ENS

## Representation-Gap Analysis

Representation gaps are mandatory diagnostics for the main scenarios. They flag
cases where the observed reliability source suggests high service deficit but
PyPSA-Earth has low or zero modeled scarcity, which can happen because the model
may not represent distribution failures, local load-shedding allocation, voltage
or feeder problems, affordability constraints, backup generation, or demand
mapping error.

For each bus, compute:

```text
primal_binding_flag_b = abs(lhs_b - rhs_b) <= epsilon_primal
dual_activity_flag_b = abs(sign_normalized_dual_b) > epsilon_dual
binding_flag_b = primal_binding_flag_b and dual_activity_flag_b
representation_gap_flag_b =
    r_b_obs high
    and modeled_ENS_share_b low
    and binding_flag_b is false
```

Default thresholds:

```text
modeled_ENS_share_b = ENS_b,y,all / D_b,y,all
r_b_obs > median r_b_obs among buses with mapped observation input
modeled_ENS_share_b < 0.01 * r_b_obs
```

Report raw dual, sign-normalized dual, and primal residual. If dual sign
handling is uncertain, use the primal residual as the binding indicator and
treat the dual as diagnostic until the dual-sign fixture passes.

For any bus with positive ENS violation or slack, also compute:

```text
missing_capacity_b ~= ENS_violation_b / shortage_hours_b
```

where `shortage_hours_b` is the weighted number of snapshots with modeled load
shedding at bus `b`. This is a diagnostic translation of unmet ENS into an
approximate firm-capacity equivalent, not an optimization substitute and not a
driver of V1 investment decisions.

An optional later sensitivity may test a reduced-form local adequacy constraint:

```text
local_firm_capacity_b + reliable_import_capacity_b >= k_b * peak_load_b
```

If used, label it as a planning sensitivity, not a causal interpretation of the
observation signal.
