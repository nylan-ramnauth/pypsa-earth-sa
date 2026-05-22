# Module 13h Handoff - Coal Linearised UC After 13g.2

**Target agent:** Codex xhigh or equivalent standalone implementation agent  
**Working directory (Earth):** `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth`  
**Working directory (RSA reference, read-only):** `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-rsa`  
**Conda environment:** `pypsa-earth`  
**Solver:** Gurobi  
**Formulation:** LP relaxation / linearised UC only, not MILP

## Context

Module 13g.2 is complete and accepted structurally.

Current accepted 13g.2 raw-BASE no-UC result:

- 15 coal stations
- 16 generator rows because Hendrina is split
- total coal p_nom = 41.419 GW
- raw-BASE no-UC solve optimal
- coal = 185.203 TWh
- OCGT = 19.198 TWh
- load shedding = 0.059 TWh
- coal Pearson r = 0.329

The earlier bad 13g result was mainly bus-mapping to stranded `* csp` buses, not coal cost. 13g.2 fixed that.

Module 13h should now test PyPSA-RSA-style coal linearised UC using `rsa_eaf_projected`, not `raw_base`.

## Critical Corrections To Existing 13h Plan

### 1. Use 16 generator rows, not 15

The corrected 13g.2 network has:

- 15 coal stations
- 16 coal generator rows due to Hendrina split:
  - `Hendrina`
  - `Hendrina_2`

All 13h gates and code must use:

- station count = 15
- generator row count = 16

Do not reintroduce a "15 generator rows" gate.

### 2. Rebuild the coal CSVs in `rsa_eaf_projected` mode before UC

Current committed/generated CSVs are raw-base mode. For 13h, rebuild:

```bash
python scripts/build_za_coal_plants.py \
  --rsa-scenarios ../pypsa-rsa/scenarios/Benchmark_2023/sub_scenarios \
  --custom-powerplants data/custom_powerplants.csv \
  --availability-mode rsa_eaf_projected \
  --outage-profiles-scenario BASE \
  --annual-availability-scenario EAF_48 \
  --plants-out data/za_validation/za_coal_plants_2023.csv \
  --eaf-out data/za_validation/za_coal_eaf_hourly_2023.csv \
  --bus-out data/za_validation/za_coal_bus_assignment.csv
```

Expected sanity:

- Arnot annual mean = 0.480
- Arnot Jan mean approximately 0.448
- Arnot Jul mean approximately 0.524
- weighted fleet mean approximately 0.481

### 3. Fix ramp-limit units before applying UC

Important: PyPSA-RSA does **not** divide `max_ramp_up (%/h)` or `max_ramp_down (%/h)` by 100.

RSA maps these workbook values directly into PyPSA ramp limits, then applies:

```text
coal_ramp_rate_multiplier = 1.5
adjust_by_p_max_pu: coal [ramp_limit_up, ramp_limit_down]
```

So for 13h parity, update `scripts/build_za_coal_plants.py` or the UC application so ramp values are:

```text
ramp_limit_up = workbook max_ramp_up * 1.5
ramp_limit_down = workbook max_ramp_down * 1.5
then, for committable rows:
ramp_limit_* *= mean(p_max_pu)
```

Do **not** use the currently stored `/100` interpretation for UC. It would make coal ramps about 100x too tight and is not RSA parity.

Also add/pass through these RSA UC columns if missing from `za_coal_plants_2023.csv`:

- `ramp_limit_start_up_per_h` from `max_ramp_start_up (%/h)`; do not multiply by 1.5
- `ramp_limit_shut_down_per_h` from `max_ramp_shut_down (%/h)`; do not multiply by 1.5
- `shut_down_cost_eur` from `shut_down_cost (R) / 20`

Current PyPSA defaults are not fatal, but RSA parity is better if these are explicit.

## Implementation Scope

Modify only:

- `scripts/build_za_coal_plants.py`
- `scripts/za_fleet/build_za_coal_plants_network.py`
- `scripts/solve_network.py`
- `configs/za/za_2023_fixed_validation.yaml`
- continuity logs/status after validation

Do not edit `scripts/add_electricity.py`.
Do not edit `scripts/za_fleet/apply_coal_eaf.py`.

## Config

Extend the existing block only; do not add a top-level `za_coal_uc`.

```yaml
za_coal_disaggregation:
  enable: true
  availability_mode: rsa_eaf_projected
  outage_profiles_scenario: BASE
  annual_availability_scenario: EAF_48
  plants_csv: data/za_validation/za_coal_plants_2023.csv
  eaf_hourly_csv: data/za_validation/za_coal_eaf_hourly_2023.csv
  bus_assignment_csv: data/za_validation/za_coal_bus_assignment.csv

  uc:
    enable: true
    msl_mode: scale_by_p_max_pu
    p_min_pu_base: 0.7
    ramp_multiplier: 1.5
    apply_min_up_down_time: false
    clean_pu_profiles: true
    min_ramp_limit_threshold: 0.05
```

Fail fast if:

```yaml
za_coal_disaggregation.enable: false
za_coal_disaggregation.uc.enable: true
```

## UC Semantics To Implement

In `scripts/za_fleet/build_za_coal_plants_network.py`, after attaching the 16 coal generator rows:

For each coal generator row:

```python
committable = True
p_min_pu static = 0.0
generators_t.p_min_pu[g] = 0.7 * generators_t.p_max_pu[g]
ramp_limit_up = ramp_limit_up_per_h * mean(p_max_pu[g])
ramp_limit_down = ramp_limit_down_per_h * mean(p_max_pu[g])
ramp_limit_start_up = ramp_limit_start_up_per_h
ramp_limit_shut_down = ramp_limit_shut_down_per_h
start_up_cost = start_up_cost_eur
shut_down_cost = shut_down_cost_eur
min_up_time = min_up_time_h
min_down_time = min_down_time_h
```

For split rows like `Hendrina_2`, use the station-level UC parameters from `Hendrina`.

Apply the RSA clean-up behavior:

```python
p_min_pu(t) <= p_max_pu(t)
p_min_pu(t) values below 0.01 can be zeroed for numerical stability
ramp_limit_up/down below 0.05 should be raised to 0.05 if clean_pu_profiles is true
```

## LP Relaxation Requirement

In `scripts/solve_network.py`, before the solve branch:

```python
has_committable = bool(n.generators["committable"].fillna(False).any())
if has_committable:
    kwargs["linearized_unit_commitment"] = True
```

This is supported in the local PyPSA-Earth environment:

- PyPSA version: `0.30.3`
- `n.optimize(..., linearized_unit_commitment=True)` is supported
- iterative solve forwards `**kwargs`

Any MIP / branch-and-bound solve is a failure.

## Remove Min-Up / Min-Down Constraints

In `extra_functionality`, after the model exists and before solve, remove these constraints when UC is enabled and `apply_min_up_down_time: false`:

```python
drop = [
    "Generator-com-up-time",
    "Generator-com-down-time",
    "Generator-com-status-min_up_time_must_stay_up",
    "Generator-com-status-min_down_time_must_stay_up",
]
existing = [c for c in drop if c in n.model.constraints]
if existing:
    n.model.remove_constraints(existing)
```

PyPSA 0.30.3 confirmed constraint names include:

- `Generator-com-up-time`
- `Generator-com-down-time`
- `Generator-com-status-min_up_time_must_stay_up`

Use the guarded list to tolerate version differences.

PyPSA 0.30.3 variable name is `Generator-status`, not `Generator-com-status`.

## Validation Gates

Run both modes.

### A. No-UC control

```yaml
availability_mode: raw_base
uc.enable: false
```

Expected: reproduce accepted 13g.2 behavior approximately:

- 15 stations
- 16 generator rows
- all coal `committable=False`
- no `generators_t.p_min_pu` UC overlay
- coal around 185.2 TWh
- load shedding near 0.06 TWh

### B. 13h UC candidate

```yaml
availability_mode: rsa_eaf_projected
uc.enable: true
```

Check:

- 15 stations, 16 generator rows
- total coal p_nom = 41.419 GW
- all coal rows `committable=True`
- non-coal rows remain `committable=False`
- static coal `p_min_pu == 0`
- coal `generators_t.p_min_pu` exists for 8760 x 16
- median `p_min_pu(t) / p_max_pu(t)` approximately 0.7
- no `p_min_pu > p_max_pu` hours
- Gurobi log shows LP, not MIP
- no branch-and-bound / MIP gap output
- solve optimal

Dispatch metrics to report:

- coal TWh
- OCGT TWh
- load shedding TWh
- coal Pearson r vs Eskom thermal
- comparison against 13g.2 raw-base no-UC

Acceptance:

- UC solve must improve Pearson r over 13g.2 r = 0.329
- target direction is toward RSA reference r approximately 0.585
- if r is 0.50-0.55, document as partial success
- if r <= 13g.2, stop and diagnose before refreshing final validation exports

## Do Not Refresh Final Exports Yet

Do not refresh final notebook/HTML validation exports until 13h is accepted or explicitly rejected.

Write continuity artifacts after validation.

