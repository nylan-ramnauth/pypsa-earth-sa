# 01 Repo Bootstrap And Config

## Goal

Prepare the PyPSA-Earth repository so every later South Africa baseline step has
stable paths, local config overlays, provenance outputs, and reproducible runtime
settings.

## Inputs

Expected local repositories:

```text
PyPSA-Earth target:
/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth

PyPSA-RSA reference:
/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-rsa
```

The implementing agent must verify these paths and record actual branch, commit,
dirty status, Python version, environment manager, solver availability, and CDS
API availability before editing code.

## PyPSA-Earth Additions

Create local South Africa directories:

```text
data/za_validation/
data/za_audit/
doc/
configs/za/
```

Create local config overlays:

```text
configs/za/za_2023_fixed_validation.yaml
```

Do not create `za_2023_grid_audit.yaml` or `za_expansion_base.yaml` as bootstrap
artifacts unless a later module reopens and names an actual consumer. They are
dead artifacts in the current implementation chain.

## Overlay Composition

The ZA overlay is not auto-discovered by upstream PyPSA-Earth. The implementing
agent must either append:

```python
configfile: "configs/za/za_2023_fixed_validation.yaml"
```

to the top-level `Snakefile` configfile block at lines 38-41, or invoke
Snakemake with:

```text
--configfile configs/za/za_2023_fixed_validation.yaml
```

Do not edit `config.yaml` or upstream defaults directly for ZA-only settings.

The fixed-validation overlay must set or expose:

```yaml
countries: ["ZA"]
snapshots:
  start: "2023-01-01"
  end: "2024-01-01"
electricity:
  custom_powerplants: replace
  estimate_renewable_capacities:
    stats: false
  renewable_carriers: [solar, onwind, hydro, csp]
  extendable_carriers:
    Generator: []
    StorageUnit: []
    Store: []
    Link: []
solving:
  solver:
    name: gurobi
    options: gurobi-default
  solver_options:
    gurobi-default:
      threads: 1        # use for parallel batches (many concurrent solves)
      method: 2         # barrier
      crossover: 0
      BarConvTol: 1.e-5
      OptimalityTol: 1.e-6
      FeasibilityTol: 1.e-6
  options:
    load_shedding: true
    noisy_costs: false
```

`electricity.extendable_carriers.Store: []` intentionally disables the upstream
`[battery, H2]` Store defaults for this fixed-capacity validation baseline.

### Solver configuration

All solves — including 1-week smoke runs, 1-month smoke runs, and the full 8760-hour solve — use Gurobi.
HiGHS is not used at any stage.

For serial single-solve runs (e.g., full 8760 standalone): set `threads: 2`.
For batched parallel runs (e.g., many years, many scenarios): set `threads: 1`.
Rationale: academic named-user license (version 13.0.0, expiry 2027-01-20, no WLS pool).

### Output currency

Add `output_currency: ZAR` to the ZA overlay config:

```yaml
output_currency: ZAR
```

This key is not native to upstream PyPSA-Earth. It is read by the local hook `apply_za_local_carriers`
(implemented in Module 07) which applies the EUR→ZAR conversion as a post-processing step on all cost
outputs. The internal solver operates in EUR throughout.

### Upstream PyPSA-Earth commit pin

The plan is calibrated against upstream PyPSA-Earth commit:

```
<IMPLEMENTING AGENT: read HEAD of 6-codebases/repos/pypsa-earth and record the exact hash here>
```

If a rebase from upstream main is needed after this pin, the implementing agent must:
1. Review the diff between the pinned commit and the new HEAD
2. Check whether any change affects modules 07, 08, 09, or 10 (costs, fleet, grid, network build)
3. Record the rebase decision in `doc/za_implementation_log.md` before proceeding
4. Update this pin to the new hash

Auto-following upstream main without explicit review is not allowed.

**Recent upstream changes to be aware of at plan-write time:**

- **PR #1622 (`Attach wind and solar generators using real positions from powerplants.csv`):**
  Wind and solar generators are now attached at the real lat/lon from `powerplants.csv` rather than
  cluster centroids. This makes lat/lon columns in `custom_powerplants.csv` load-bearing for ZA local
  carriers, and may mean that `bus` column assignment happens automatically from coordinates.
  Implementing agent must verify: does `add_electricity` still require an explicit `bus` column in
  `custom_powerplants.csv` for ZA carriers, or does it auto-resolve from lat/lon?
  Document the finding in `doc/za_implementation_log.md` before building Module 09.

- **`electricity_grid_connection` PR (commit `f8eab87a`):**
  Adds a per-generator grid-connection cost. The ZA overlay must explicitly decide whether to enable,
  disable, or override this for ZA local carriers. See Module 07 for the decision.

### Environment version pinning

A locked environment file `envs/za_environment.yaml` must be committed at the start of Module 01.
At minimum, pin: `python`, `pypsa`, `atlite`, `powerplantmatching`, `linopy`, `gurobi`, `numpy`, `pandas`,
`geopandas`, `snakemake`. Record the exact versions used in `doc/za_implementation_log.md`.

`other_re` is not a native PyPSA-Earth config key and must not be expected under
`electricity.extra_accounting_carriers`. Module `06` owns the 8760 `Other RE`
time series. Module `10` owns the local network-injection hook that writes the
`other_re` Carrier row and attaches it as fixed exogenous accounting generation.
It is not an extendable renewable resource.

Before modules `03`, `10`, and `11` proceed, the implementing agent must record:

- Gurobi license/availability for final solves.
- successful `gurobipy.Model().optimize()` trivial-LP smoke test in the locked
  Python environment.
- CDS/ERA5 access or a verified prebuilt 2023 cutout with path, hash, and
  provenance.
- PyPSA-Earth and PyPSA-RSA commit hashes.
- active `load_options` values, including `ssp`, `weather_year`, and
  `prediction_year`.
- detect-and-reuse status for `cutouts/cutout-2023-era5.nc`: if the file exists
  and its hash/provenance are recorded, treat the cutout dependency as satisfied
  and skip live retrieval/build in the fixed-validation run.

Runtime pre-flight output:

```text
data/za_audit/za_runtime_preflight.csv
doc/za_data_provenance.md
```

## Provenance Skeleton

Create empty or first-pass provenance outputs:

```text
data/za_audit/input_file_manifest.csv
data/za_audit/source_hashes.csv
doc/za_data_provenance.md
```

Every later module must append source path, source hash, extraction date, filter
logic, and unresolved warnings for any external data it consumes.

## Acceptance Gates

- PyPSA-Earth and PyPSA-RSA paths exist; branch, commit hash, and dirty status
  are recorded.
- Local ZA directories and config overlays exist.
- ZA overlay composition is recorded via the Snakefile configfile block or the
  exact `--configfile` invocation.
- Solver and CDS availability are recorded.
- Gurobi and CDS/prebuilt-cutout pre-flight gates are recorded before dependent
  modules proceed.
- Gurobi trivial-LP smoke test passes in the locked Python environment.
- Provenance skeleton exists and includes at least the PyPSA-Earth/PyPSA-RSA
  repo commits.
- No upstream default config has been changed for a South Africa-only assumption.
- `snakemake --configfile configs/za/za_2023_fixed_validation.yaml --dry-run` executes without
  errors, confirming the ZA overlay is syntactically valid and all rule inputs resolve.
