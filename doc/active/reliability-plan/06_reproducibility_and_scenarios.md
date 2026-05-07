# 06 Reproducibility And Scenarios

## V1 Reproducibility Locks

Lock the first South Africa implementation before scenario runs:

- country: South Africa
- observation year: `2023`
- observation source for locked South Africa run: `ntl_proxy` with
  `spatial_unit: settlement` and `metric: uptime_share`; data-rich runs may use
  `measured_uptime` under the same standardized `r_b_obs` contract
- smoke-test foresight mode: `overnight`
- preferred thesis foresight mode: `myopic_elec_only`
- full-run clustered network: `clusters: 34`, aligned to the Eskom 34 local
  areas through a custom busmap/supply-region clustering layer; the busmap
  artifact path and source (Eskom supply-region shapefile or derived layer)
  must be pinned in the project config and recorded in the pathway summary
- reduced integration-test network: smallest South Africa cluster count the
  local PyPSA-Earth configuration can build reliably
- planning horizons: electricity-only myopic dynamics preferred
- independent overnight solves without carry-forward: fallback sensitivity only
- budget basis: annualized expansion cost using the same PyPSA-Earth
  `capital_cost` values as the objective
- currency and price year: PyPSA-Earth upstream default (EUR, reference year
  matching the active `costs_{year}_elec.csv`); WACC follows upstream
  `process_cost_data` defaults unless an explicit South Africa value is
  recorded in the pathway summary
- environment pin: PyPSA-Earth release version plus local fork commit hash;
  Linopy, PyPSA, and the LP solver must be pinned in
  `requirements_reliability.txt` or equivalent. V1 locks Gurobi as the LP
  solver; the Gurobi version, license type (named-user, WLS, academic), and
  license expiry must be recorded. The dual-sign fixture from
  `05_tests_acceptance.md` is solver specific and must be re-run on any
  solver change.
- final thesis evidence must use the Stage 2 transmission-budget path from
  `04_carry_forward_contract.md` and `05_tests_acceptance.md`
- if a thesis horizon reports `transmission_limit_saturated = true` after
  Stage 2 unlock, the run does not fail; transmission expansion is disabled
  for that horizon and the saturation flag must be surfaced in the pathway
  summary so reviewers can interpret the binding upstream global limit
- NERSA reliability standards are future validation evidence only for V1.
  Internal eta parameters are sufficient for thesis defensibility unless a
  later reviewed source explicitly promotes NERSA criteria into the active
  acceptance contract.

Mandatory thesis scenarios are Scenarios 0-4. Scenarios 0-3 establish the
deterministic ENS pathway; Scenario 4 is the final EENS/weather-robustness
result after deterministic ENS is working. Scenarios 5-6 are optional
extensions or sensitivities.

Scenario labels remain NTL-focused for the South Africa thesis because the
locked empirical source is `ntl_proxy`. If `observations.source =
measured_uptime` is used for a data-rich country, the same ladder becomes
measured-reliability-informed planning with no solver changes.

## Budget Frontier

For V1, report a compact budget frontier rather than relying on one externally
chosen number:

```text
Budget_y in {0.75, 1.00, 1.25} * I_baseline_y
```

Expose the multiplier set as a config parameter, defaulting to:

```yaml
reliability:
  budget:
    frontier_multipliers: [0.75, 1.00, 1.25]
```

`I_baseline_y` is the annualized physical expansion cost from the unconstrained
least-cost `myopic_elec_only` baseline pathway for the same year and clustered
network. It must be period-incremental under the same carry-forward mechanics as
the constrained pathway, not an independent overnight expansion for that year.

If credible South Africa policy or Eskom utility capex envelope data are found,
report them as externally anchored budget cases with source, currency, price
year, annualization assumptions, and whether the case is used as the primary
policy budget. Keep the `{0.75, 1.00, 1.25} * I_baseline_y` frontier as the
internal baseline for comparability.

Execution order: an unconstrained `myopic_elec_only` baseline pathway is run
first as a calibration step, with the same clustered topology, carry-forward
mechanics, demand assumptions, and cost assumptions as the constrained runs.
`I_baseline_y` is extracted per horizon from this baseline pathway (annualized
new-capacity cost only, fixed carried capacity excluded). Scenarios 1-3 are
then run against the resulting frontier. The baseline pathway is stored as a
declared acceptance artifact, not regenerated implicitly.

## Central Target Parameters

The central deterministic pathway uses:

```text
eta_2030 = 0.25
eta_2040 = 0.60
eta_2050 = 0.90
gamma = 1.0
```

Expose eta values under
`reliability.pathway.improvement_eta_by_horizon[y]`. These are configurable
defaults, not constants embedded in scripts.

Non-monotone `eta_y` fails validation. `gamma` remains global in the central
case; Scenario 5 may vary it as an optional stringency sensitivity.

## Scenario 0: Diagnostic Historical Validation

Run PyPSA-Earth with historical data and no expansion where possible.

Purpose:

- compare modeled all-hours ENS/load shedding against observed unreliability
- compute late-night ENS as an observation-window diagnostic
- assess whether the model reproduces the spatial pattern of the observed
  service-deficit signal
- identify where the model may miss observed reliability problems

Reliability config: `reliability.enable: true`, `scenario.mode: diagnostic`,
`budget.enable: false`. ENS reliability constraint: off.

## Scenario 1: Budget-Constrained Baseline Expansion

Run the planning year without observed-reliability ENS constraints:

```text
2030 demand
2030 technology costs
standard PyPSA-Earth assumptions
investment budget
standard load-shedding cost
```

Use the V1 budget frontier above.

Purpose:

- establish baseline investment allocation under limited budget
- compute baseline all-hours ENS
- identify which regions receive investment without observed-reliability target
  information

Reliability config: `reliability.enable: true`, `scenario.mode: diagnostic`,
`budget.enable: true`. ENS reliability constraint: off. `Reliability-budget`:
on.

## Scenario 2: Observed-Reliability-Informed All-Hours ENS-Constrained Expansion

Run the same budget-constrained expansion, but add:

```text
ENS_b_all <= ENS_limit_b_all + slack_b
```

Purpose:

- test whether explicit observed-reliability all-hours targets shift investment
- report remaining slack and unmet reliability targets
- report late-night ENS diagnostics for comparison with the observation window
- compare allocation against Scenario 1

Reliability config: `reliability.enable: true`, `scenario.mode: ens_and_budget`,
`budget.enable: true`. ENS reliability constraint: on. `Reliability-budget`:
on.

## Scenario 3: Planning-Horizon Extension

Run Scenarios 1 and 2 through `myopic_elec_only` for:

```text
2030
2040
2050
```

with changing:

- demand
- technology costs
- policy constraints
- period budgets
- all-hours reliability improvement targets that tighten over time

Implementation requirement:

```text
foresight: myopic_elec_only
Budget_2030, Budget_2040, Budget_2050
eta_2030 < eta_2040 < eta_2050
capacity_2030_opt -> capacity_2040_existing
capacity_2040_opt -> capacity_2050_existing
```

Purpose:

- assess how reliability-oriented investment differs across horizons
- test whether early investments reduce or intensify later scarcity
- compare against independent overnight-year sensitivities only as fallback
- provide the deterministic ENS pathway baseline for Scenario 4

Final thesis pathway runs for Scenario 3 and later must pass the Stage 2
transmission fixture: `Line-s_nom` and DC/transmission `Link-p_nom` expansion
must be included in the reliability budget set.

## Scenario 4: EENS Weather-Robustness Main Result

After Scenarios 0-3 pass, run multiple weather-year cases. V1 locks the
following:

- scope: the locked `myopic_elec_only` pathway is solved once per weather year
  using the same 2030 -> 2040 -> 2050 horizons and the same Stage 2
  transmission-budget contract; the EENS robustness statement is reported at
  the final horizon (2050) with optional per-horizon EENS extensions
- implementation pattern: per-weather-year independent `myopic_elec_only`
  solves with post-hoc weighted aggregation of bus-level ENS results into
  `EENS_b,y,all`. Investment decisions are not shared across weather years in
  V1. This independent-sweep design is the V1 implementation per
  [[3-wiki/decisions/2026-05-07-v1-reliability-implementation-uses-deterministic-eens-constraints|DEC-002]].
  Extensive-form multi-scenario LPs and scenario-decomposed Lagrange
  relaxations are explicitly out of scope for V1
- scenario weather years are configurable through `scenario_4_weather_years`;
  default: `[2019, 2020, 2021, 2022, 2023, 2024]`. If the user sets
  `scenario_4_weather_years: [2024]`, only 2024 runs.
- the plan assumes a clean repo, so Scenario 4 cutouts are not pre-built by
  default and must be built or detected by pre-flight. 2024 cutout availability
  is verified by the dry-run gate; exclude it if incomplete and record the
  exclusion reason.
- observation year remains `2023` for all weather-year cases; only the
  weather-dependent supply and demand inputs vary through `weather_year`

EENS reporting (post-hoc, not an LP constraint; investment decisions are not
shared across weather years in V1):

```text
EENS_b,y,all = sum_s p_s * ENS_b,s,y,all
post-hoc check: EENS_b,y,all should satisfy EENS_b,y,all <= EENS_limit_b,y,all
violations are reported as diagnostics, not solver-enforced
```

Purpose:

- test reliability targets under plausible weather conditions
- connect deterministic ENS implementation to stochastic EENS literature
- report whether the observed-reliability-informed pathway remains reliable
  under weather-year variation
- produce the final thesis robustness result

Scenario probabilities `p_s` must be stated explicitly; equal weights are the V1
default unless a documented alternative is used.

## Scenario 5: ENS Target Stringency Frontier

Optional extension after Scenarios 0-4.

Run a compact sensitivity sweep against the central deterministic pathway. The
sweep applies a single multiplier per axis to the central trajectory:

```text
gamma in {0.25, 0.5, 1.0, 1.5}        # global scaling of r_b_obs
eta_multiplier in {0.5, 0.75, 1.0}    # uniform scaling of (eta_2030, eta_2040, eta_2050)
```

The central case corresponds to `gamma = 1.0` and `eta_multiplier = 1.0`. The
multiplier set is upper-bounded at `1.0` because central `eta_2050 = 0.90`
already approaches the feasible ceiling; multipliers above `1.0` would push
`eta_2050` out of the valid `[0, 1)` range. Any combination producing a
non-monotone or out-of-range `eta_y` after scaling fails validation and is
skipped.

Purpose:

- build a cost-reliability frontier
- show how ENS strictness affects investment, total cost, and slack use
- avoid dependence on one arbitrary translation parameter

Report total investment, modeled all-hours ENS, total reliability slack, system
cost, active buses with binding constraints, and interpretable shadow prices.

## Scenario 6: Observed-Reliability-Priority Load-Shedding Cost Sensitivity

Deferred past IEW 2026. This optional extension is out of scope for the IEW 2026
submission and may be revisited for the full thesis only after Scenarios 0-4
are stable.

Test an implicit reliability approach:

```text
VOLL_b = VOLL_base * (1 + alpha * reliability_priority_b)
```

This is a sensitivity, not the main method. It should be framed as an
observed-reliability-priority penalty or externally informed differentiated
VOLL sensitivity, not as NTL-estimated or satellite-estimated regional VOLL.

If external VOLL data are available, a stronger sensitivity can combine external
VOLL structure by consumer/time with observed service-deficit priority weights.

If Scenario 6 is executed, `alpha` and the function from `r_b_obs` to
`reliability_priority_b` must be pinned in the project config alongside the
resulting `VOLL_b` table; defaults are not provided in V1.
