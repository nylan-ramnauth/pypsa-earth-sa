# Module 13i/13j Source Findings - RSA OPC and UC Provenance

**Date:** 2026-05-15  
**Scope:** PyPSA-RSA `Benchmark_2023`, scenario `S_2023BM`, model year 2023  
**Earth context:** Modules 13h, 13i, 13j  
**RSA reference checkout:** `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-rsa`

## Bottom Line

The RSA benchmark scenario used for comparison is a 2023 model-year scenario:

- `scenario = S_2023BM`
- `simulation_years = list(range(2023,2024))`
- `load_trajectory = 2023_ACTUAL`
- `outage_profiles = BASE`
- `annual_availability = EAF_48`
- `unit_committment = True`
- `operational_limits = NO_MIN_GAS`

There is no evidence from the scenario selection that PyPSA-RSA is applying future-year OPC or UC values to the 2023 benchmark solve.

Important nuance: not every technical parameter is an independently dated measured 2023 observation. Some values are scenario assumptions used in the 2023 benchmark, for example coal ramp rates, minimum stable levels, startup costs, and operational-limit policy settings. The defensible wording is therefore:

> The model uses PyPSA-RSA `Benchmark_2023` inputs selected for model year 2023. Observed 2023 data are used where specified, while plant technical and operational parameters are 2023 benchmark scenario assumptions rather than necessarily measured 2023 observations.

## Main Source Workbooks

| Workbook | Role | SHA-256 |
|---|---|---|
| `scenarios/Benchmark_2023/scenarios_to_run.xlsx` | Selects `S_2023BM` scenario settings | `8c93af02d52ac2db005fd91700480965c261bef5eb87182f17a54c0317cc840a` |
| `scenarios/Benchmark_2023/sub_scenarios/operational_constraints.xlsx` | Defines operational-limit rows selected by `operational_limits` | `1951cc8c57a811f92d81eafd95a53c83562743637945eb7948e6be1a55719a06` |
| `scenarios/Benchmark_2023/sub_scenarios/fixed_technologies.xlsx` | Defines fixed plant fleet and UC technical fields | `27e0cb58d1db16a99d397956ec2588f65ce319ef08355c20fa1eadfb013ad4a8` |
| `scenarios/Benchmark_2023/sub_scenarios/plant_availability.xlsx` | Defines BASE outage profiles and EAF_48 annual availability | `da2079af787f03f643d90cc5302dce332815232fd96da64d39519645a2a93d95` |

These Benchmark_2023 scenario workbooks are local inputs in the RSA checkout. Treat them as local PyPSA-RSA benchmark inputs and preserve hashes when citing or reusing them.

## Scenario Row Findings

From `scenarios_to_run.xlsx`, sheet `scenario_definition`, row `S_2023BM`:

| Field | Value | Interpretation |
|---|---:|---|
| `simulation_years` | `list(range(2023,2024))` | The solve is for model year 2023 only |
| `fixed_conventional` | `VAR_HR` | Fixed conventional fleet comes from the VAR_HR workbook scenario |
| `unit_committment` | `True` | Linearised UC behavior is active |
| `override_coal_msl` | `0.7` | Coal MSL is overridden to 70% of available capacity |
| `coal_ramp_rate_multiplier` | `1.5` | Coal ramp up/down rates are multiplied by 1.5 |
| `operational_limits` | `NO_MIN_GAS` | OPC rows are selected from the `NO_MIN_GAS` scenario |
| `operational_reserves` | `BASE` | Reserve workbook scenario selected, though operating-reserve call is commented in the current solve path |
| `outage_profiles` | `BASE` | BASE planned/unplanned outage profiles |
| `annual_availability` | `EAF_48` | Annual coal availability target is 0.48 where applicable |
| `load_trajectory` | `2023_ACTUAL` | 2023 actual load trajectory |

## Unit Commitment Source Path

The coal UC behavior comes from both workbook fields and RSA scripts.

### Workbook Fields

Source workbook:

- `scenarios/Benchmark_2023/sub_scenarios/fixed_technologies.xlsx`
- sheet: `conventional`
- scenario selected by `fixed_conventional = VAR_HR`

Relevant columns:

- `dispatch_committable`
- `max_ramp_up (%/h)`
- `max_ramp_down (%/h)`
- `max_ramp_start_up (%/h)`
- `max_ramp_shut_down (%/h)`
- `min_stable_level (%)`
- `min_up_time (h)`
- `min_down_time (h)`
- `start_up_cost (R)`
- `shut_down_cost (R)`

For the coal rows inspected, `dispatch_committable = True`. The 13h implementation should therefore treat the coal UC fields as 2023 benchmark scenario assumptions.

### Script Path

Relevant RSA files and behavior:

- `scripts/_helpers.py`
  - maps workbook columns such as `max_ramp_up (%/h)`, `min_stable_level (%)`, `start_up_cost (R)`, and `shut_down_cost (R)` into PyPSA generator fields.

- `scripts/add_electricity.py`
  - enables committable carriers when `SCENARIO_SETUP["unit_committment"] == True`.
  - applies `override_coal_msl = 0.7`.
  - converts committable `p_min_pu` into hourly `p_min_pu * p_max_pu`.
  - applies `coal_ramp_rate_multiplier = 1.5`.

- `scripts/prepare_and_solve_network.py`
  - creates the optimization model with `linearized_unit_commitment=True`.
  - removes min-up/down constraints when UC is active in this solve path.

## OPC / Operational-Limits Source Path

The RSA "OPC" layer is not a single hard-coded OCGT cap. It is the generic operational-limits mechanism driven by `operational_constraints.xlsx`.

### Scenario Selection

For `S_2023BM`:

- `operational_limits = NO_MIN_GAS`

This matters because the workbook also contains `HIGH_GAS`, but `S_2023BM` does not select `HIGH_GAS`.

### `NO_MIN_GAS` Rows Relevant to 2023

From `operational_constraints.xlsx`, sheet `operational_constraints`, scenario `NO_MIN_GAS`, the 2023-relevant rows include:

| Carrier/resource | Constraint | Period | Apply to | Unit | 2023 value |
|---|---|---|---|---|---:|
| `ccgt_steam` | minimum capacity factor | month | all | `%` | `0.3` |
| `nuclear` | minimum capacity factor | hour | all | `%` | `1.0` |
| `rmippp` | minimum capacity factor | month | fixed | `%` | `0.5` |
| `sasol_coal` | maximum output energy | year | fixed | `TWh` | `5.5` |
| `sasol_gas` | maximum output energy | year | fixed | `TWh` | `2.8` |

The `NO_MIN_GAS` 2023 rows do not include an annual OCGT diesel cap.

### `HIGH_GAS` Is Different

The workbook's `HIGH_GAS` scenario does include an `ocgt_diesel` annual maximum output-energy row:

- `ocgt_diesel`
- `output_energy`
- `year`
- `max`
- `all`
- `TWh`
- 2023 value: `5.5`

However, this row belongs to `HIGH_GAS`, not `NO_MIN_GAS`. Since `S_2023BM` selects `NO_MIN_GAS`, the 5.5 TWh OCGT diesel cap is not part of the RSA `S_2023BM` operational-limit selection unless the scenario is deliberately changed.

This is important for Module 13j: an OCGT cap may still be a useful PyPSA-Earth diagnostic, but it should not be described as RSA `S_2023BM` parity unless the selected RSA scenario is changed or further evidence shows the cap is applied elsewhere.

### Script Path

Relevant RSA files and behavior:

- `scripts/custom_constraints.py`
  - `apply_operational_constraints(...)` converts workbook rows into model constraints.
  - handles energy-unit conversion for `GWh`, `TWh`, `PJ`, etc.
  - filters generators by carrier and bus.
  - uses snapshot weightings for energy-style constraints.

- `scripts/custom_constraints.py`
  - `set_operational_limits(...)` reads `operational_constraints.xlsx`, selects `scenario_setup["operational_limits"]`, and applies each row.

- `scripts/prepare_and_solve_network.py`
  - calls `set_operational_limits(...)` before solving.

## Answer to the Data-Year Mismatch Question

For the current 2023 calibration comparison, there is no evidence that the RSA benchmark scenario is mixing in future-year OPC or UC rows by mistake.

The active scenario is explicitly model year 2023, and the operational-limit mechanism selects the 2023 column for the selected `NO_MIN_GAS` rows. UC behavior uses the 2023 benchmark fleet and scenario settings, including `VAR_HR`, `EAF_48`, `override_coal_msl = 0.7`, and `coal_ramp_rate_multiplier = 1.5`.

The careful caveat is:

- **No mismatch found:** the scenario selection is 2023 and the active workbook columns are 2023.
- **Not all inputs are measured 2023 observations:** plant technical parameters and operational-policy constraints are benchmark assumptions used for the 2023 model year.
- **Do not cite local file modification dates as source years:** workbook metadata shows edits in 2025/2026 for some files, but the scenario content is a 2023 benchmark setup.

## Implications for Modules 13i and 13j

### Module 13i OPC

Module 13i should copy the RSA operational-limits mechanism for the selected 2023 scenario, especially `NO_MIN_GAS`, rather than assuming OPC means an OCGT cap.

It should also check whether the existing PyPSA-Earth `EAF-OPC` case actually matched `NO_MIN_GAS` or accidentally copied `HIGH_GAS` behavior.

### Module 13j CAP

Module 13j should treat an OCGT annual cap as a separate configurable diagnostic unless xhigh finds a direct RSA parity basis for applying it to `S_2023BM`.

The `HIGH_GAS` workbook row can be cited as an RSA workbook precedent for an OCGT diesel annual cap, but not as the active `S_2023BM` setting.

## Recommended Citation Language

Use language like:

> The 2023 benchmark calibration uses PyPSA-RSA `Benchmark_2023`, scenario `S_2023BM`, with `simulation_years = list(range(2023,2024))`. Coal UC parameters are taken from the `VAR_HR` fixed-conventional workbook scenario and applied through PyPSA-RSA's linearised UC solve path. Operational limits are selected from the `NO_MIN_GAS` rows in `operational_constraints.xlsx` for the 2023 model year.

Avoid language like:

> All UC and OPC parameters are measured 2023 data.

That stronger claim is not supported by the inspected files.
