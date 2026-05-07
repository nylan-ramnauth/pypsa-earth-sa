# 04 Carry-Forward Contract

## V1 Representation

Use component-specific carry-forward:

```text
Generator: fixed brownfield + separate extendable candidates
StorageUnit: fixed brownfield + separate extendable candidates
Store: fixed brownfield + separate extendable candidates
Line: staged lower-bound carry-forward with required verification gate
Link: fixed brownfield for validated non-transmission physical links; staged
      lower-bound carry-forward for DC/transmission links with required
      verification gate
```

Budget expressions must match the representation. Fixed brownfield capacity is not charged again. Lower-bound transmission budgets charge only expansion above
the carried minimum. Final thesis pathway scenarios must include verified
transmission expansion in the reliability budget set; excluding transmission is
allowed only for smoke tests or explicitly labeled pre-verification sensitivity
runs.

## `add_elec_brownfield` Contract

Before carry-forward, assign `build_year` to current-horizon new assets.

After the base-year existing-capacity step, later horizons must set
`keep_existing_capacities: false` before current-horizon preparation imports
assets. Validation must fail if a later horizon sets it true. Otherwise
IRENA/current existing capacities can be re-imported in the same horizon as
carried capacity from the previous solved network.

For current-horizon extendable candidates whose minima come from
existing-capacity statistics, reset nominal minima and nominal values to avoid
double counting:

```text
Generator, StorageUnit: p_nom_min = 0 and p_nom = 0
Store: e_nom_min = 0 and e_nom = 0
```

For previous-horizon `Generator`, `StorageUnit`, `Store`, and non-transmission
physical `Link` assets:

- drop non-physical and excluded carriers
- drop `lifetime == inf` rows when they track global current-horizon values
  already present in the current network
- drop expired finite-lifetime assets where `build_year + lifetime < year`
- drop non-extendable previous assets that already exist as fixed current assets
- drop optimized capacities below the configured carry-forward threshold
- copy optimized nominal capacity into the nominal capacity field
- set carried assets non-extendable
- import required time-dependent input series, including `p_max_pu`, `p_min_pu`,
  and time-varying marginal-cost fields where present

The carry-forward threshold must be explicit config. V1 default:
`1e-3 MW` for power-nominal components and `1e-3 MWh` for energy-nominal
components.

`StorageUnit` must be handled explicitly using `p_nom`, `p_nom_opt`,
`p_nom_min`, `p_nom_extendable`, `max_hours`, efficiency fields, bus, carrier,
and time-dependent fields where present. Do not copy the upstream brownfield
loop blindly because upstream omits `StorageUnit`.

Do not include sector-coupled gas/H2 retrofit logic in the electricity-only
script.

## Naming And Collisions

Asset names must be deterministic. Use stable suffixes or an explicit mapping:

```text
{original_asset_name}-{build_year}
{original_asset_name}-{planning_horizons}-candidate
```

If an imported previous-horizon asset name collides with an asset already
present in the current prepared network, V1 drops the previous row before import
and records the action in `carried_capacity_{planning_horizons}.csv`. Renaming
is a later fallback only if dropping would lose validated physical capacity.

## Transmission

For `Line` and DC/transmission `Link` lower-bound carry-forward:

- set `s_nom_min` or `p_nom_min` to the previous optimized value
- keep topology and extendability unless excluded or blocked by transmission
  limit handling
- budget only expansion above the carried lower bound

Transmission carry-forward must be reconciled with upstream
`transmission_expansion_cost_limit` and
`transmission_expansion_volume_limit` global constraints.

V1 uses staged inclusion:

```text
stage 1: generation/storage carry-forward may be implemented and smoke-tested
without transmission budget terms, but those runs are not final thesis pathway
evidence
```

```text
stage 2: before final thesis scenarios, include Line-s_nom and DC/transmission
Link-p_nom expansion in the reliability budget set after the transmission
verification gate passes
```

The transmission verification gate must prove:

- reliability budget terms use `capital_cost * (optimized_capacity -
  carried_minimum)` for lower-bound transmission assets
- carried minima are not charged again
- upstream transmission global limits and the reliability budget do not charge
  or constrain the same carried capacity inconsistently
- if carried minima already saturate an upstream transmission limit, further
  transmission expansion is disabled and `transmission_limit_saturated` is
  reported
- if the gate has not passed, final pathway scenarios must fail validation
  rather than silently omit transmission from the budget set

The transmission fixture in `05_tests_acceptance.md` is the Stage 2 unlock gate.
It must pass before final thesis pathway runs can use the transmission budget
set.

## Carried Capacity Table

Each horizon after the first must write
`carried_capacity_{planning_horizons}.csv` with at least:

```text
horizon
component
asset_name_previous
asset_name_current
carrier
bus_or_branch_endpoints
optimized_attribute
optimized_value_previous
carried_value_current
representation
budget_treatment
build_year
lifetime
excluded_flag
exclusion_reason
transmission_limit_saturated
```

Write rows for imported, lower-bounded, excluded, expired, and threshold-dropped
assets.
