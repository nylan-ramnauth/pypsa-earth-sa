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
