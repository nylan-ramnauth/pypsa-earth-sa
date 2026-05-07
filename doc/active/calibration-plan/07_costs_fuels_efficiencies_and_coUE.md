# 07 Costs Fuels Efficiencies And COUE

## Goal

Lock dispatch-cost, fuel, efficiency, emissions, and load-shedding-cost inputs
before fixed network build and dispatch calibration. Dispatch validation must not
depend on implicit PyPSA-Earth defaults for South Africa-specific local carriers.

## Cost Source Policy

V1 default:

- Lock `costs.year: 2030` for the 2023 fixed-validation baseline because the
  repo provides `costs.csv`, `costs_2025.csv`, and `costs_2030.csv`, but no
  `costs_2023.csv`. This is a known limitation to document in the validation
  report.
- Use PyPSA-Earth/technology-data costs where the carrier maps cleanly.
- Add South Africa local cost rows only for local carriers locked in
  `05_system_boundary_and_carrier_taxonomy.md`.
- Use PyPSA-RSA costs and operational assumptions as reference evidence, not as
  a wholesale replacement for PyPSA-Earth cost processing.
- Consume `data/za_audit/pypsa_rsa_cost_fuel_emissions_audit.csv` from `04`
  before generating any local carrier row.
- Record currency year, units, and conversion assumptions for every local row.

## Required Outputs

```text
data/za_audit/za_costs_fuels_efficiencies_audit.csv
data/za_audit/za_local_carrier_cost_rows.csv
doc/za_costs_fuels_efficiencies_and_coUE.md
```

Required PyPSA-RSA evidence inputs from `04`:

```text
data/za_audit/pypsa_rsa_cost_fuel_emissions_audit.csv
scenarios/Coal_Flexibilisation/sub_scenarios/fuel_prices.xlsx
scenarios/Coal_Flexibilisation/sub_scenarios/emissions.xlsx
scenarios/ME IRP 2024/sub_scenarios/fixed_technologies.xlsx
scenarios/ME IRP 2024/sub_scenarios/extendable_technologies.xlsx
```

This module consumes the `04` audit CSV. Raw workbook paths above are
traceability references and must not be re-parsed here unless module `04` is
reopened.

The audit must cover:

```text
coal
nuclear
ocgt_diesel
ocgt_gas
sasol_gas
sasol_coal
biomass
other_re as zero-cost fixed exogenous accounting generation with CO2 emissions
factor = 0 for V1 under biogenic-neutral accounting; reporting metadata must
flag that Eskom `Other RE` is an aggregate category
hydro
pumped storage
battery if included
csp
load shedding
imports/exports as zero-cost exogenous accounting flows for V1
```

## Local Carrier Requirements

For every local carrier, define:

```text
capital_cost or documented fixed-validation placeholder
marginal_cost
fuel price
efficiency / heat rate
emissions factor
lifetime only if the carrier flows into `13` future-asset or retirement policy
carrier color/nice-name for reporting
validation target
source and unit conversion
```

Mine PyPSA-RSA fixed and extendable technology workbooks for heat rates,
efficiencies, VOM, FOM, fuel mapping, and carrier assumptions before writing
local rows. If PyPSA-Earth defaults are retained instead, the report must state
why the PyPSA-RSA value was not adopted. `za_local_carrier_cost_rows.csv` must
include `pypsa_earth_default_retained_reason` for this decision.

Local carrier cost rows are written to the sidecar file
`data/za_audit/za_local_carrier_cost_rows.csv` and consumed by Module `10`
through the `apply_za_local_carriers` hook. The hook adds local carrier metadata
and generator marginal-cost overrides after `add_electricity`; it does not
modify upstream `costs.csv`.

All costs are stored in EUR. Any ZAR source values must be converted using a
documented 2023 exchange rate recorded in
`data/za_audit/za_costs_fuels_efficiencies_audit.csv`.

### Cost currency policy

**Internal solver:** All costs passed to the solver remain in EUR. This is the upstream PyPSA-Earth
contract. Changing solver-internal units would break `process_cost_data.py` and `solve_network.py`.
Do not change internal units.

**Output / reporting:** All cost outputs presented to the user are converted to ZAR.
Mechanism: the `output_currency: ZAR` key in the ZA overlay config is read by the local hook
`apply_za_local_carriers`. The hook applies a post-processing EUR→ZAR conversion to all cost
outputs (capacity costs, marginal costs, load-shedding costs) before writing to validation CSVs
and notebooks. This hook is implemented as part of Module 07.

**Frozen exchange rate:** Use the 2023-12-31 closing EUR/ZAR rate from:
```
https://github.com/alexprengere/currencyconverter/blob/master/currency_converter/eurofxref.csv
```
Take the rate for the row dated 2023-12-29 (last ECB trading day of 2023) or 2023-12-31 if
present. Record the exact date and rate used in:
```
data/za_audit/za_eur_zar_fxrate_2023.csv
```
with columns: `date, eur_zar_rate, source, note`.

**Source values in ZAR:** For any cost source already in ZAR (e.g., from pypsa-rsa), convert
to EUR using the source's own base year rate, not the 2023 rate. Record the base-year rate
per row in `za_costs_fuels_efficiencies_audit.csv`.

### Cost of Load Shedding (CoLS) reference values

Two distinct uses of CoLS exist in this model. They must not be confused.

#### 1. Solver safety-valve marginal cost (numerical sentinel)

This is the cost assigned to load-shedding in the dispatch/expansion solver. Its purpose is to
ensure the solver only sheds load when physically unavoidable. It is NOT the policy CoLS.

Value: `solving.options.load_shedding: 100` (EUR/kWh = 100,000 EUR/MWh, upstream default).
This value is approximately 200× Nova Economics CoLS and 17× CSIR CoLS — intentionally extreme.
Do not change this unless infeasibility debugging requires it.

#### 2. Policy CoLS (used in reporting and reliability handoff)

This is the economically grounded value used to:
- Calculate the monetary cost of modelled load-shedding in validation reports
- Set the reliability slack penalty in Module 13's handoff to the Reliability Plan

**Primary value: CSIR R116,570/MWh** (2024 ZAR)
Source: Council for Scientific and Industrial Research, Utility-scale power generation statistics
in South Africa 2024, cited by FTI Consulting (2025) and National Treasury.
Canonical reference: `3-wiki/reference/web-clips/2026-05-07-fti-consulting-out-of-darkness-economic-costs.md`

**Sensitivity lower bound: Nova Economics R9,530/MWh** (2018/19 ZAR, GDP-loss only)
Source: Nova Economics, commissioned by Eskom, c. 2020.
Canonical reference: `3-wiki/reference/web-clips/2026-05-07-nova-economics-cost-of-load-shedding-sa.md`

**Deloitte 2009 Eskom: R8,950/MWh** (2009 ZAR) — historical reference only.

All three values must appear in `za_costs_fuels_efficiencies_audit.csv` with their base year, ZAR
value, converted EUR value, and source. Module 12 validation reports must present load-shedding
costs in both the solver-safety-valve frame (EUR) and the policy-CoLS frame (ZAR).

#### 3. `electricity_grid_connection` cost (upstream PR `f8eab87a`)

Upstream added a per-generator grid-connection cost in commit `f8eab87a`. The ZA overlay must
explicitly decide how to handle this for ZA local carriers:

Decision: **disable `electricity_grid_connection` for ZA local carriers** by setting
`costs.electricity_grid_connection: 0` in the ZA overlay, or by removing the component from
`apply_za_local_carriers`. Rationale: ZA local carriers (`custom_powerplants.csv` rows) already
have reconciled capex values that include grid-connection components per Module 08.
Applying the upstream formula again would double-count.

Document this decision in `doc/za_implementation_log.md`.

## COUE And Load-Shedding Cost

Load shedding must have a high marginal cost for dispatch validation, but the
value must be unit-checked.

PyPSA-RSA `COUE: 100000` with the comment equivalent to R100/kWh is reference
evidence only. The implementation must verify:

```text
currency
base year
whether value is R/MWh, R/kWh, EUR/MWh, or another unit
conversion to PyPSA-Earth cost units
relationship to reliability slack penalty in the separate reliability plan
```

This module owns the baseline load-shedding cost. It does not change the
reliability slack penalty owned by `doc/active/reliability-plan/`.

V1 baseline value: `solving.options.load_shedding: 100` in EUR/kWh, inherited
from the upstream PyPSA-Earth default. `scripts/solve_network.py` multiplies
this value by `1000` when assigning load-shedding marginal cost, so the modeled
safety-valve marginal cost is `100,000 EUR/MWh`. The separate reliability slack
penalty must use the same unit reconciliation.

## Acceptance Gates

- Every carrier in `05` has a cost/emissions/efficiency treatment.
- Local carrier rows are generated or documented as config overlays.
- `other_re` is documented as zero-cost fixed exogenous accounting generation
  for V1 with CO2 emissions factor = 0 under biogenic-neutral accounting, and
  reporting metadata explicitly records the aggregate-category limitation.
- Coal Flex `fuel_prices.xlsx` and `emissions.xlsx` have been audited through
  `04` and considered in the local carrier rows.
- Fixed/extendable technology heat rates, VOM/FOM, and efficiencies have been
  audited before local rows are finalized.
- COUE/load-shedding cost units are verified and reported.
- Dispatch-cost assumptions are ready before `10_fixed_capacity_network_build.md`
  and `11_dispatch_calibration_and_availability.md`.
