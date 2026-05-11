# ZA Costs, Fuels, Efficiencies, and CoUE

Module 07 locks dispatch-cost inputs — fuel prices, heat rates, VOM/FOM,
emissions factors, lifetimes, and load-shedding cost — for the 2023 fixed-
capacity validation baseline before Module 10 (network build) and Module 11
(dispatch calibration).

## Cost Source Policy

- Upstream PyPSA-Earth `costs.year` locked to **2030** because the repo
  ships `data/costs.csv`, `data/costs_2025.csv`, and `data/costs_2030.csv`
  but no `costs_2023.csv`. This is a known V1 limitation reported by
  Module 12.
- PyPSA-Earth/technology-data defaults are used where the carrier maps
  cleanly. PyPSA-RSA values from the Module 04 audit override defaults for
  ZA local carriers (`sasol_coal`, `sasol_gas`, `ocgt_diesel`, `ocgt_gas`,
  `other_re`) and are recorded for the other V1 carriers as evidence.
- PyPSA-RSA workbooks themselves are NOT re-parsed in this module — the
  Module 04 audit CSV (`pypsa_rsa_cost_fuel_emissions_audit.csv`) is the
  only allowed source.

## Currency Mechanics

- **Solver internal unit: EUR/MWh** (upstream contract; not changed).
- **Frozen 2023 EUR/ZAR rate:** `20.3477` ZAR per 1 EUR
  on `2023-12-29`.
- **Source:** https://raw.githubusercontent.com/alexprengere/currencyconverter/master/currency_converter/eurofxref-hist.zip (member `eurofxref-hist.csv`,
  SHA256 `9dea72fbf8116f2d76106d78f9875f2aa8157f39ed3cf728a1602f2a5445d199`).
- **PyPSA-RSA base-year rate (2018):** `15.6186`
  ZAR per 1 EUR. Used to convert all PyPSA-RSA-sourced ZAR values to EUR
  for solver-internal use.
- **Reporting output:** Module 10's `apply_za_local_carriers` hook will
  re-convert EUR solver outputs to ZAR using the 2023 frozen rate before
  writing validation CSVs. The helper `scripts/za_costs/currency.py`
  exports `eur_to_zar` and `zar_to_eur` for that consumer.

## Cost of Load Shedding (CoLS)

Two distinct frames exist; they must not be confused.

### 1. Solver safety-valve marginal cost

Value: `solving.options.load_shedding: 100` (EUR/kWh). The solver code
`scripts/solve_network.py:161` multiplies by 1000, so the safety-valve
marginal cost is **100,000 EUR/MWh**. This is a numerical sentinel that
keeps the solver from shedding load except where physically unavoidable;
it is intentionally extreme (about 200x the Nova CoLS and 17x the CSIR
CoLS). Module 07 does not change this value.

### 2. Policy CoLS for reporting + reliability handoff

Recorded in `data/za_audit/za_cols_reference_values.csv` with three rows
(CSIR primary, Nova lower-sensitivity, Deloitte historical). Module 12
validation reports must present load-shedding costs in both frames.

## electricity_grid_connection Decision

Upstream PyPSA-Earth PR `f8eab87a` added a per-generator grid-connection
cost. **Decision for ZA overlay: disable** — set
`costs.electricity_grid_connection: 0` in
`configs/za/za_2023_fixed_validation.yaml`. Rationale: Module 08 reconciles
full per-plant capex through `custom_powerplants.csv`, including grid-
connection components. Applying the upstream formula again would
double-count.

## Local Carrier Hook Boundary

Module 07 produces the data sidecar `za_local_carrier_cost_rows.csv` and
the importable EUR/ZAR helper. The `apply_za_local_carriers` hook itself —
which inserts these rows into the PyPSA network after `add_electricity` —
is implemented by Module 10. See `scripts/za_costs/currency.py` for the
EUR-to-ZAR helper that Module 10 imports.

## Artifacts

- `data/za_audit/za_costs_fuels_efficiencies_audit.csv` — 105 rows
- `data/za_audit/za_local_carrier_cost_rows.csv` — 5 rows ({sasol_coal, sasol_gas, ocgt_diesel, ocgt_gas, other_re})
- `data/za_audit/za_eur_zar_fxrate_2023.csv` — 1 row
- `data/za_audit/za_cols_reference_values.csv` — 3 rows ({CSIR, Nova, Deloitte})

## V1 Limitations (recorded for Module 12)

- `costs.year: 2030` (no `costs_2023.csv` upstream).
- `other_re` is an aggregate Eskom category; CO2 emissions factor = 0
  under biogenic-neutral V1 accounting; the aggregate-category limitation
  must be flagged in reporting metadata.
- PyPSA-RSA fuel-price base year is treated as **2018 ZAR** for the
  ME_IRP23 scenario set; Module 12 should sensitivity-check.
- Capital cost is left blank in the local-carrier sidecar; Module 08 owns
  per-plant capex reconciliation through `custom_powerplants.csv`.
