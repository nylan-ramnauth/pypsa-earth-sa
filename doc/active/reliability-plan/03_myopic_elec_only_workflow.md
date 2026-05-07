# 03 Myopic Electricity-Only Workflow

## Pathway Mode

Implement a project-specific mode:

```yaml
foresight: myopic_elec_only
```

Do not reuse upstream `foresight: myopic`, which is sector-coupled.

For a given pathway run, keep the same clustered topology and bus mapping across
2030, 2040, and 2050. For the locked thesis run this means the same
`clusters: 34` custom busmap/supply-region layer aligned to Eskom local areas.
This keeps reliability targets, bus outputs, and carried capacity comparable
across horizons.

In `myopic_elec_only`, `simplify_network_myopic_elec` and
`cluster_network_myopic_elec` are copy-or-symlink-with-hash-check rules from the
single frozen topology artifact, not full per-horizon reruns.

The pathway target is:

```text
2030 solved network -> carry capacity -> 2040 solved network -> carry capacity -> 2050 solved network
```

## Required Rules

Add horizon-aware electricity-only rules:

```text
solve_elec_myopic_pathway
build_demand_profiles_myopic_elec
add_electricity_myopic_elec
simplify_network_myopic_elec
cluster_network_myopic_elec
augmented_line_connections_myopic_elec, if enabled
add_extra_components_myopic_elec
prepare_network_myopic_elec
add_existing_elec_baseyear
add_elec_brownfield
solve_elec_myopic_network
collect_elec_myopic_results
```

Rules must use `{planning_horizons}` in every intermediate network, result,
demand, carried-capacity, reliability-target, reliability-diagnostic, and
summary output path to avoid collisions in one Snakemake DAG.

The first horizon uses `add_existing_elec_baseyear`; later horizons use
`add_elec_brownfield` with the previous solved NetCDF as an explicit input.
`collect_elec_myopic_results` joins period outputs into the pathway summary.

Add Snakemake ordering and baseyear matching guards:

```python
ruleorder: add_existing_elec_baseyear > add_elec_brownfield
wildcard_constraints:
    planning_horizons=config["scenario"]["planning_horizons"][0]
```

## Horizon Artifacts

Use horizon-tagged artifacts, including:

```text
networks/.../elec_{planning_horizons}.nc
networks/.../elec_s{simpl}_{planning_horizons}.nc
networks/.../elec_s{simpl}_{clusters}_{planning_horizons}.nc
networks/.../elec_s{simpl}_{clusters}_ec_l{ll}_{opts}_{planning_horizons}.nc
results/.../networks/elec_s{simpl}_{clusters}_ec_l{ll}_{opts}_{planning_horizons}.nc
resources/.../demand_profiles_{planning_horizons}.csv
resources/.../reliability_targets_{planning_horizons}.csv
resources/.../myopic_elec_only/carried_capacity_{planning_horizons}.csv
results/.../bus_reliability_results_{planning_horizons}.csv
results/.../bus_reliability_summary_{planning_horizons}.csv
results/.../horizon_assumptions_{planning_horizons}.csv
```

Because topology is frozen within a pathway run, still use horizon-tagged
copy/check artifacts so the DAG is explicit and reviewable.

## Reliability Observations And Targets

Target-building rules must be source-agnostic after the observation adapter.
Expose the observation source under `config["reliability"]["observations"]`:

```yaml
reliability:
  observations:
    source: ntl_proxy        # V1 thesis default
    spatial_unit: settlement # data-rich alternatives: substation/local_area/bus
    metric: uptime_share
```

`ntl_proxy` is the implemented South Africa V1 adapter. `measured_uptime` is the
data-rich adapter contract: measured TSO/substation/local-area uptime maps to
the same bus-level `r_b_obs` and reliability target schema. Downstream
`reliability_targets_{planning_horizons}.csv` paths and solve rules are
unchanged by the observation source.

## Costs

Every horizon must map to an electricity cost file:

```text
resources/.../costs_{cost_year_by_horizon[y]}_elec.csv
```

Use PyPSA-Earth `process_cost_data`; do not introduce a separate cost source.
The horizon-aware cost input applies to at least:

```text
add_electricity_myopic_elec
simplify_network_myopic_elec
cluster_network_myopic_elec
augmented_line_connections_myopic_elec, if enabled
add_extra_components_myopic_elec
prepare_network_myopic_elec
```

If reused, post-solve reporting rules such as `make_summary` and `plot_network`
must also use the horizon-mapped cost file.

V1 keeps non-year cost settings constant across horizons unless explicit
horizon-specific cost-config plumbing is implemented.

Validation must fail if `enable.retrieve_cost_data` is false without an explicit
validated local `data/costs.csv` strategy, because otherwise all `{year}`
wildcards can silently use the same fallback cost file.

## GEGIS Demand

Do not reuse the upstream parse-time global `load_data_paths`.

`load_options.weather_year` in the GEGIS demand route is the demand-side ERA5
year used for SSP load profiles. Scenario 4's weather-year sweep is configured
separately and may require supply-side Atlite cutouts for each accepted weather
year.

`build_demand_profiles_myopic_elec` must select `ssp`, `prediction_year`,
`weather_year`, and optional `scale` from:

```text
reliability.pathway.demand_assumption_by_horizon[y]
```

V1 default: implement the helper that calls
`get_load_paths_gegis("data", config_y)` with horizon-overwritten
`load_options`, and use the per-horizon `expected_region_files` list as a
runtime comparator that fails fast if the helper's resolved paths drift from
the configured set.

For South Africa V1, expected GEGIS files are:

```text
data/ssp2-2.6/2030/era5_2013/Africa.nc
data/ssp2-2.6/2040/era5_2013/Africa.nc
data/ssp2-2.6/2050/era5_2013/Africa.nc
```

The dry-run must prove each horizon resolves to the intended demand file and
fail if any expected GEGIS file is missing or misresolved.

Each horizon must export a horizon-assumption summary with `horizon`,
`cost_file`, `demand_source`, `total_annual_load`, `peak_load`, `policy_case`,
`co2_limit_or_price`, and `technology_cost_year`.

`collect_elec_myopic_results` must join the horizon-assumption summaries into
the pathway summary.

## Custom Rule Scope

PyPSA-Earth includes `custom_rules` early in the upstream `Snakefile`. Any
custom rule file must be self-contained or must hoist required helpers before
the include point. It must not assume later helpers such as `memory(w)` or
`retrieve_subregion(...)` are in scope.

Monte Carlo mode is unsupported for V1 and must fail validation unless the
Monte Carlo solve branch is explicitly patched and dry-run validated.
