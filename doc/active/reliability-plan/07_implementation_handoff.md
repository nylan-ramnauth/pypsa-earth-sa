# 07 Implementation Handoff

This module closes wiring and bootstrap gaps the implementing agent must
resolve with repo access on day one. It is not a design contract. Modules
00-06 own all design decisions; 07 only records the repo-specific values, file
paths, and concrete Snakemake stubs needed to start coding.

The implementing agent must fill in every section below with the user before
writing the first commit. Once filled, this module is part of the freeze and
must be kept in sync with the codebase.

All numerical and configuration locks below assume the V1 deterministic
single-shot LP method per
[[3-wiki/decisions/2026-05-07-v1-reliability-implementation-uses-deterministic-eens-constraints|DEC-002]].
No Lagrange or dual-decomposition machinery is implemented in V1.

## 1. Repo Layout

Resolved inspection values:

| Item | Locked or inspected value |
|---|---|
| PyPSA-Earth fork URL | `https://github.com/nylanramnauth-droid/pypsa-earth-sa.git` |
| Local clone path | `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth/` |
| Upstream remote | `https://github.com/pypsa-meets-earth/pypsa-earth.git`; push disabled locally |
| Working branch | `za-clean-base` |
| Branch inspection | `origin/za-clean-base` at `c1fd1a985879134a351c78d905af3dc8a17bdf95`; local checkout during inspection was `main` at `858915533d296afd0f0b4074517f323e1161aac5` |
| Clean-branch check | `origin/za-clean-base` has three SA prompt/roadmap commits over upstream merge-base `96e89285529f86d090376d6663f2bcebd3f9b6c7`; no P0 implementation code found in those commits. Current `upstream/main` has advanced to `f8eab87a892a73d7106b3459613c1ee2ce64f256`, so rebase/freeze verification is required before implementation. |
| Release tag from local repo | `v0.8.0` |
| Plan mirror path inside fork | `doc/active/reliability-plan/` |
| Worktree note | Inspection found one unrelated untracked nested-repo file: `doc/za_pypsa_rsa_mining_plan.md`; do not delete or rely on it without user confirmation. |

Lock the following:

- PyPSA-Earth fork URL (or path to local checkout)
- working branch for the reliability work
- local clone path used by the agent
- whether `pypsa-earth` upstream is added as a remote and which release tag the
  fork sits on top of
- worktree or branch policy for in-progress reliability development

File locations to lock inside the fork:

- `scripts/reliability_constraints.py`: home for solver helpers listed in
  `02_solver_integration.md` (`read_reliability_targets`, `validate_target_df`,
  `get_load_shedding_generators`, `build_bus_level_load_shedding_expr`,
  `build_bus_level_demand_param`, `add_reliability_constraints`,
  `add_investment_budget_constraint`, `collect_reliability_results`,
  `reliability_mode_is_constrained`, `reliability_budget_is_enabled`)
- `scripts/carry_forward_elec_capacities.py`: home for `add_elec_brownfield`
  per `04_carry_forward_contract.md`
- `scripts/build_bus_reliability_observations.py`: home for source-specific
  reliability observation adapters and bus-level aggregation
- `scripts/build_bus_reliability_targets.py`: home for the target builder
- `custom_snakefiles/electricity_myopic.smk`: horizon-aware electricity-only
  rules listed in `03_myopic_elec_only_workflow.md`
- `custom_snakefiles/reliability.smk`: observation, target, and reporting
  rules
- exact line-range patches to `scripts/solve_network.py` for the
  `extra_functionality` hook, `assign_all_duals=True`, named outputs, and
  `noisy_costs` validation; record file:line ranges as a patch table

Initial `scripts/solve_network.py` patch table from repo inspection:

| Patch target | Current line anchor | Required V1 change |
|---|---:|---|
| load-shedding unit behavior | `151-162` | Preserve upstream `load_shedding * 1000` EUR/kWh to EUR/MWh conversion; reliability slack uses the reconciled EUR/MWh value. |
| `extra_functionality` hook body | `1040-1118` | Add reliability target read, ENS constraint hook, budget hook, and V1 `noisy_costs` validation after upstream constraints. |
| solve kwargs | `1127` | Keep upstream `kwargs["extra_functionality"] = extra_functionality`; add `assign_all_duals=True` when `reliability.enable` is true. |
| network metadata for hook | `1134-1136` | Attach reliability target path and config needed by helper functions before optimization. |
| export path | `1223` | Collect reliability diagnostics and write named CSV outputs before `n.export_to_netcdf(...)`. |

Record the resolved values directly in this module under `## 1. Repo Layout`
once the agent and user agree.

## 2. Version Pins

Resolved or partially resolved pins:

| Item | Value |
|---|---|
| PyPSA-Earth release tag | `v0.8.0` |
| V1 freeze commit hash | `[TO BE FILLED ON FREEZE]` |
| `pypsa` | env constraint `pypsa>=0.25.1, <=0.30.3`; exact installed version `[TO BE FILLED ON FREEZE]` |
| `linopy` | transitive env dependency; exact installed version `[TO BE FILLED ON FREEZE]` |
| `atlite` | env constraint `atlite>=0.4.1`; exact installed version `[TO BE FILLED ON FREEZE]` |
| `snakemake` | env constraint `snakemake-minimal<8` |
| Python | env constraint `python>=3.10, <3.12`; exact interpreter `[TO BE FILLED ON FREEZE]` |
| xarray | env constraint `xarray>=2023.11.0, <=2025.01.2` |
| LP solver | Gurobi |
| Gurobi version | `13.0.0` |
| Gurobi license type | academic named-user |
| Gurobi license path | `/Users/nylan/gurobi.lic` |
| Gurobi license expiry | `2027-01-20` |
| OS freeze target | `[TO BE FILLED ON FREEZE]` |
| `requirements_reliability.txt` commit | `[TO BE FILLED ON FREEZE]` |
| Dual-sign fixture pass date | `[TO BE FILLED ON FREEZE]` |

Lock the following before the first solve:

- PyPSA-Earth release tag the fork is based on
- fork commit hash for the V1 freeze
- `pypsa` version
- `linopy` version
- LP solver: Gurobi for V1; record Gurobi version, license type (named-user,
  WLS, academic), license file path, and license expiry. HiGHS is allowed
  only as a fallback comparison solver, not the headline V1 solver.
- Python version
- OS the freeze is reproducible on
- `requirements_reliability.txt` (or equivalent) committed at the fork commit
  hash above
- date the dual-sign fixture passed for the locked solver

Note: any solver change after freeze requires re-running the dual-sign fixture
from `05_tests_acceptance.md`.

## 3. External Input Contract

The empirical reliability-observation pipeline is owned outside this fork. Lock
the active source contract here so the reliability builder can consume it
without surprises. V1 South Africa uses `ntl_proxy`; data-rich countries may use
`measured_uptime` without changing the solver.

Common observation-source fields:

- `observations.source`: `ntl_proxy` or `measured_uptime`
- `observations.metric`: `uptime_share`
- observation year or start/end dates
- spatial unit: `settlement`, `substation`, `local_area`, or `bus`
- source file path under the project data tree
- source CRS and geometry or mapping table
- value column for uptime share
- support/coverage fields and quality flags
- aggregation weight field: population, load, customers, coverage, or explicit
  equal-weight fallback
- whether `protected(...)` is required to prevent `--delete-all-output` from
  removing external source files

### Observation Schema Adapter

The pypsa-earth model consumes a solver-ready observation file but does not own
its production. Production is external and handled by the parallel observation
workstream.

Expected V1 South Africa input:

```text
data/reliability/observations/ntl_settlement_2023.parquet
```

Expected GeoParquet schema:

```text
settlement_id
geometry
population
uptime
n_observations
source_year
CRS = EPSG:4326
```

Adapter requirements outside pypsa-earth:

```text
Input: Reliability-Assessment settlement-level parquet with
       settlement_id, year, n_days_obs, uptime, population, lon, lat
Steps:
  1. Join settlement geometry by settlement_id.
  2. Rename n_days_obs -> n_observations.
  3. Derive source_year = 2023.
  4. Write GeoParquet with CRS = EPSG:4326.
```

The interface is data-agnostic. NTL is the V1 proxy because South Africa lacks
SAIDI/SAIFI or measured uptime by supply region; a data-rich uptime source can
replace it by matching the same schema and target-builder contract.

The authoritative standardized bus-level output schema is defined in
`01_reliability_formulation.md`; this section only records source-side inputs
needed to produce that schema.

South Africa baseline receiving entries:

The South Africa baseline workstream in
`docs/active/za_baseline_source_of_truth/13_expansion_and_reliability_handoff.md`
owns the producer-side handoff artifact table. This reliability handoff module
must bind the following receiving entries after the ZA table records paths,
hashes, owners, and accepted validation stages:

- validated 2023 solved network or buildable network artifacts
- frozen `data/custom_powerplants.csv`
- demand/import/export/`other_re` series
- local carrier cost rows and reporting metadata
- Eskom-34 busmap and grid/spatial mapping
- availability assumptions
- retirement and future-asset policy
- validation report
- provenance report
- limitations report

The Eskom-34 busmap producer is ZA module `09_grid_spatial_and_transmission_model.md`,
not this reliability handoff module. The Gurobi pin and PyPSA-Earth fork commit
recorded here must match the values recorded by ZA module
`01_repo_bootstrap_and_config.md`.

NTL settlement-level outputs for `observations.source: ntl_proxy`:

- file path: `data/reliability/observations/ntl_settlement_2023.parquet`
- file format: GeoParquet
- column schema: `settlement_id`, `geometry`, `population`, `uptime`,
  `n_observations`, `source_year`
- CRS for settlement geometries: `EPSG:4326`
- producing script/notebook commit hash and dataset version:
  `[TO BE FILLED ON FREEZE BY EXTERNAL OBSERVATION WORKSTREAM]`

Settlement geometry source:

- shapefile or GeoPackage path
- naming convention for `settlement_id`
- whether settlements are points or polygons; aggregation rule confirmed
  accordingly

Measured uptime outputs for `observations.source: measured_uptime`:

- file path under the project data tree
- file format: CSV or parquet
- column schema, including at minimum: `region_or_asset_id`, `uptime`,
  `observation_start`, `observation_end`, `source_year`, and `quality_flag`
- spatial mapping: direct `bus`, geometry, bus-region polygon join, or explicit
  substation/local-area-to-bus mapping table
- optional denominator/coverage columns: customer count, load, outage-hours
  coverage, or reporting completeness
- source owner and access constraints, including whether data can be committed,
  staged externally, or only referenced by path

Eskom-34 custom busmap:

- source shapefile or polygon set used to define the 34 supply regions
- build recipe (custom script or one-off notebook) that produces the
  PyPSA-Earth-compatible busmap artifact
- artifact path consumed by `cluster_network_myopic_elec`:
  `data/custom_busmap_elec_s_34.csv`
- whether the artifact is checked into the repo or staged externally

Atlite cutout pre-flight:

- configured Scenario 4 weather years from `scenario_4_weather_years`; default
  `[2019, 2020, 2021, 2022, 2023, 2024]`
- which accepted years have available South Africa cutouts at the locked
  PyPSA-Earth release
- which weather years require building a new cutout, and the build cost
- 2024 cutout availability must be verified by dry-run; exclude if incomplete
- weather years that are dropped for V1 with explicit exclusion reason

GEGIS files pre-flight:

- confirm `data/ssp2-2.6/{2030,2040,2050}/era5_2013/Africa.nc` exist locally
- confirm helper resolution against `expected_region_files` matches

Gurobi license:

- license type: academic named-user
- `gurobi.lic` file path: `/Users/nylan/gurobi.lic`
- expiry date: `2027-01-20`
- renewal owner: Nylan RAMNAUTH unless superseded
- whether the locked license permits the model size at `clusters: 34` for
  three horizons plus the Scenario 4 weather-year sweep
- fallback HiGHS configuration in case the license lapses mid-thesis; any HiGHS
  run must be labeled fallback/comparison and must re-run solver-specific
  fixtures before interpretation

Cost data:

- whether `enable.retrieve_cost_data: true` will pull `costs_2030.csv`,
  `costs_2040.csv`, `costs_2050.csv` from the upstream `technology-data` repo,
  or whether local CSVs must be staged
- V1 default: use `enable.retrieve_cost_data: true`; record the
  `technology-data` commit hash if remote retrieval is used

## 4. Numerical Defaults

Locked V1 starting values:

| Setting | V1 value | Unit | Source |
|---|---|---|---|
| `solving.options.load_shedding` | `100` | EUR/kWh | upstream `config.default.yaml` |
| `solving.options.skip_iterations` | `true` | boolean | `02_solver_integration.md` |
| `solving.options.noisy_costs` | `false` | boolean | `02_solver_integration.md` |
| `slack.penalty_eur_per_mwh` | `100000` | EUR/MWh | `load_shedding_eur_per_kwh * 1000` |
| `epsilon_demand` | `1.0` | MWh/year | bus-active filter |
| `epsilon_primal` | `1e-3` | MWh | binding-flag primal residual |
| `epsilon_dual` | `1e-6` | EUR/MWh | binding-flag dual activity |
| carry-forward threshold (power) | `1e-3` | MW | `04_carry_forward_contract.md` |
| carry-forward threshold (energy) | `1e-3` | MWh | `04_carry_forward_contract.md` |
| WACC / discount rate | upstream `process_cost_data` default | dimensionless | `06_reproducibility_and_scenarios.md` |
| Gurobi `FeasibilityTol` | `1e-7` | solver tolerance | reproducibility of `I_baseline_y` |
| Gurobi `OptimalityTol` | `1e-7` | solver tolerance | reproducibility of `I_baseline_y` |
| Gurobi `Method` | `2` | solver option | barrier for cleaner duals |
| Gurobi `Crossover` | `0` | solver option | stable barrier duals |
| Gurobi `BarConvTol` | `1e-8` | solver tolerance | barrier convergence |
| Gurobi `Threads` | `1` | solver option | reproducibility lock |
| Gurobi `Seed` | `0` | solver option | reproducibility lock |
| `gamma` central | `1.0` | dimensionless | `06_reproducibility_and_scenarios.md` |
| `eta_2030, eta_2040, eta_2050` | `0.25, 0.60, 0.90` | dimensionless | config defaults under `reliability.pathway.improvement_eta_by_horizon` |
| Scenario 4 weather-year weights | equal | probability weights | `06_reproducibility_and_scenarios.md` |
| `scenario_4_weather_years` | `[2019, 2020, 2021, 2022, 2023, 2024]` | years | user answer Q-001 |

Unit reconciliation: upstream stores `load_shedding` as EUR/kWh. The inspected
`scripts/solve_network.py:161` multiplies by `1000`, so
`100 EUR/kWh = 100,000 EUR/MWh`. Slack target equals
`load_shedding_eur_per_kwh * 1000`, not `1000 * load_shedding_eur_per_mwh`.

Gurobi options live in a named block under `solving.solver_options`, selected
by `solving.solver.options`. Set `solving.solver.name: gurobi` and select the
locked V1 block before running reliability scenarios.

Record the locked values in the project config and in this module once
confirmed.

## 5. Concrete Snakemake Stubs

The implementing agent must produce concrete rule definitions for at least the
following before the first dry-run. These stubs land in
`custom_snakefiles/electricity_myopic.smk` and
`custom_snakefiles/reliability.smk`.

### Baseline calibration and `solve_elec_myopic_pathway` aggregate targets

```python
rule solve_elec_myopic_baseline_pathway:
    input:
        solved=expand(
            "results/" + RDIR + "networks/baseline/elec_s{simpl}_{clusters}_ec_l{ll}_{opts}_{planning_horizons}.nc",
            **config["scenario"],
        ),
        carried_capacity=expand(
            "resources/" + RDIR + "myopic_elec_only/baseline/carried_capacity_{planning_horizons}.csv",
            planning_horizons=config["scenario"]["planning_horizons"][1:],
        ),
        horizon_assumptions=expand(
            "results/" + RDIR + "baseline/horizon_assumptions_{planning_horizons}.csv",
            **config["scenario"],
        ),
    output:
        baseline_pathway_summary="results/" + RDIR + "myopic_elec_only/baseline_pathway_summary_s{simpl}_{clusters}_l{ll}_{opts}.csv",
    script:
        "../scripts/collect_elec_myopic_results.py"

rule solve_elec_myopic_pathway:
    input:
        solved=expand(
            "results/" + RDIR + "networks/elec_s{simpl}_{clusters}_ec_l{ll}_{opts}_{planning_horizons}.nc",
            **config["scenario"],
        ),
        reliability_results=expand(
            "results/" + RDIR + "reliability/bus_reliability_results_{planning_horizons}.csv",
            **config["scenario"],
        ),
        carried_capacity=expand(
            "resources/" + RDIR + "myopic_elec_only/carried_capacity_{planning_horizons}.csv",
            planning_horizons=config["scenario"]["planning_horizons"][1:],
        ),
        horizon_assumptions=expand(
            "results/" + RDIR + "horizon_assumptions_{planning_horizons}.csv",
            **config["scenario"],
        ),
        baseline_pathway_summary="results/" + RDIR + "myopic_elec_only/baseline_pathway_summary_s{simpl}_{clusters}_l{ll}_{opts}.csv",
    output:
        pathway_summary="results/" + RDIR + "myopic_elec_only/pathway_summary_s{simpl}_{clusters}_l{ll}_{opts}.csv",
    script:
        "../scripts/collect_elec_myopic_results.py"
```

The user invokes these aggregate rules by asking Snakemake for concrete summary
files at the locked `{simpl}/{clusters}/{ll}/{opts}` combination, not by naming
the wildcarded rules directly. The baseline summary is produced first and then
used as an explicit input to the constrained pathway aggregation.

### Patched `solve_network` rule (named outputs and reliability inputs)

```python
output:
    solved="results/" + RDIR + "networks/elec_s{simpl}_{clusters}_ec_l{ll}_{opts}_{planning_horizons}.nc",
    reliability_results="results/" + RDIR + "reliability/bus_reliability_results_{planning_horizons}.csv",
    reliability_summary="results/" + RDIR + "reliability/bus_reliability_summary_{planning_horizons}.csv",

input:
    network="...",                                         # existing input
    reliability_targets="resources/" + RDIR + "reliability/bus_reliability_targets_{planning_horizons}.csv",
    carried_capacity_table=lambda w: (
        "resources/" + RDIR + f"myopic_elec_only/carried_capacity_{w.planning_horizons}.csv"
        if str(w.planning_horizons) != str(config["scenario"]["planning_horizons"][0])
        else []
    ),

shadow: "shallow"
```

The `solve_network.py` patch must read `snakemake.input.reliability_targets`
into `n.reliability_targets_path` before solving and write
`snakemake.output.reliability_results` before
`n.export_to_netcdf(snakemake.output.solved)` returns.

### Baseyear and brownfield ordering

```python
ruleorder: add_existing_elec_baseyear > add_elec_brownfield

rule add_existing_elec_baseyear:
    wildcard_constraints:
        planning_horizons=str(config["scenario"]["planning_horizons"][0]),
    input:
        prepared="networks/" + RDIR + "elec_s{simpl}_{clusters}_ec_l{ll}_{opts}_{planning_horizons}.nc",
    output:
        with_baseyear="networks/" + RDIR + "myopic_elec_only/elec_s{simpl}_{clusters}_ec_l{ll}_{opts}_{planning_horizons}_baseyear.nc",
    ...

rule add_elec_brownfield:
    input:
        prepared="networks/" + RDIR + "elec_s{simpl}_{clusters}_ec_l{ll}_{opts}_{planning_horizons}.nc",
        previous_solved=lambda w: solved_previous_horizon(w),
    output:
        with_brownfield="networks/" + RDIR + "myopic_elec_only/elec_s{simpl}_{clusters}_ec_l{ll}_{opts}_{planning_horizons}_brownfield.nc",
        carried_capacity_table="resources/" + RDIR + "myopic_elec_only/carried_capacity_{planning_horizons}.csv",
    ...
```

Define `solved_previous_horizon(w)` mirroring upstream sector myopic.

### `build_demand_profiles_myopic_elec` GEGIS helper

The helper from `03_myopic_elec_only_workflow.md` is the V1 default:

```python
from copy import deepcopy
from pathlib import Path

def horizon_load_paths(w):
    y = str(w.planning_horizons)
    demand_by_horizon = config["reliability"]["pathway"]["demand_assumption_by_horizon"]
    demand_y = demand_by_horizon.get(y, demand_by_horizon.get(int(y)))
    if demand_y is None:
        raise KeyError(f"Missing demand_assumption_by_horizon for {y}")
    cfg_y = deepcopy(config)
    cfg_y["load_options"] = dict(cfg_y.get("load_options", {}))
    cfg_y["load_options"]["ssp"] = demand_y["ssp"]
    cfg_y["load_options"]["prediction_year"] = demand_y["prediction_year"]
    cfg_y["load_options"]["weather_year"] = demand_y["weather_year"]
    paths = get_load_paths_gegis("data", cfg_y)
    expected = demand_y.get("expected_region_files", [])
    if expected:
        normalize = lambda seq: {str(Path(p).resolve()) for p in seq}
        if normalize(paths) != normalize(expected):
            raise ValueError(
                f"GEGIS load paths for {y} do not match expected_region_files"
            )
    return paths
```

## 6. Scenario Disambiguation

Lock the following with the user before runs.

Scenario 0 (Diagnostic Historical Validation):

- planning year for the diagnostic run (recommend `2023` to match the
  observation year)
- whether the run is overnight or single-horizon `myopic_elec_only`
  (recommend overnight)
- `extendable_carriers: {Generator: [], Store: [], Link: []}` so no expansion
  happens
- `solving.options.load_shedding: true` so modeled load shedding can be observed
  for comparison with the active reliability-observation source

Scenario 1 standalone smoke (Budget-Constrained Baseline):

- whether the standalone smoke is a single-horizon overnight run on a
  reduced cluster count, or the full `myopic_elec_only` baseline pathway used
  to compute `I_baseline_y`
- recommend: standalone smoke is overnight on the reduced integration-test
  cluster; the full unconstrained baseline pathway is a separate calibration
  run feeding `I_baseline_y` per `06_reproducibility_and_scenarios.md`

Scenario 1/2/3 thesis runs:

- always full `myopic_elec_only` pathway with horizons `[2030, 2040, 2050]`
  and Stage 2 transmission carry-forward unlocked

Scenario 4:

- runs the locked pathway once per accepted weather year; report final-horizon
  EENS at 2050 with optional per-horizon EENS extensions
- `scenario_4_weather_years` default:
  `[2019, 2020, 2021, 2022, 2023, 2024]`; if set to `[2024]`, only 2024 runs.
- 2024 cutout availability is dry-run verified and excluded with reason if
  incomplete.

## 7. Day-1 Bootstrap Sequence

Recommended ordering for the first session with repo access:

1. Resolve sections 1 and 2 above; commit `requirements_reliability.txt` and
   record version pins. Verify Gurobi is callable from the locked Python
   environment (`gurobipy.Model().optimize()` on a trivial LP); record the
   license expiry in this module.
2. Resolve section 3: confirm the active reliability-observation source
   contract, settlement or measured-uptime geometries/mappings, Eskom-34 busmap
   artifact, Atlite cutout availability, GEGIS files, cost data path, and Gurobi
   license. Run a one-shot pre-flight script that asserts every expected input
   is reachable and prints the missing ones.
3. Resolve section 4: write the locked numerical defaults into
   `config.default.yaml` (or the project config) under `reliability` and
   `solving.options`.
4. Resolve section 6: write the Scenario 0 and Scenario 1 standalone configs
   as separate config files or scenario presets.
5. Implement section 5 stubs: aggregate target rule, patched solve rule,
   baseyear and brownfield rules, GEGIS helper. Run dry-runs against the
   concrete locked baseline summary path and constrained pathway summary path,
   not the wildcarded rule names, and iterate until the gates in
   `05_tests_acceptance.md` pass.
6. Implement the reliability fixtures from `05_tests_acceptance.md` in
   `tests/reliability/` and run them on the small integration-test cluster.
7. Run the overnight Scenario 0 smoke test with
   `reliability.scenario.mode: diagnostic`. Verify the diagnostic CSV gate.
8. Run the unconstrained `myopic_elec_only` baseline pathway as the
   `I_baseline_y` calibration step on the small cluster.
9. Run the constrained Scenarios 1-3 against the resulting frontier on the
   small cluster.
10. Pass the Stage 2 transmission fixture, then scale to `clusters: 34`.
11. Run Scenario 4 weather-year cases after deterministic ENS pathway outputs
    pass.

## 8. Status

| Section | Status | Owner |
|---|---|---|
| 1. Repo Layout | filled from repo inspection; freeze rebase/check required | implementing agent + user |
| 2. Version Pins | partially filled; exact installed versions and freeze commit marked `[TO BE FILLED ON FREEZE]` | implementing agent + user |
| 3. External Input Contract | filled for V1 observation schema, busmap path, cutout list, and Gurobi license; external producer commit pending | implementing agent + user |
| 4. Numerical Defaults | locked for V1 defaults and unit reconciliation | implementing agent + user |
| 5. Concrete Snakemake Stubs | scaffold provided; concrete paths pending repo confirmation | implementing agent |
| 6. Scenario Disambiguation | filled for Scenario 4 weather years and IEW scope | implementing agent + user |
| 7. Day-1 Bootstrap Sequence | recommended ordering | implementing agent |

This module enters the freeze once sections 1, 2, 3, 4, 5, and 6 are filled
and the user confirms.
