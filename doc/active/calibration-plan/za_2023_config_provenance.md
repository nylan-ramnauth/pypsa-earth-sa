# ZA 2023 Fixed-Validation Config Provenance

Date: 2026-06-01  
Scope: `configs/za/za_2023_fixed_validation.yaml`

This note preserves rationale moved out of the active YAML overlay during the
baseline config cleanup. The active config is now limited to runtime values and
short selector comments.

## Reference Copy

- Pre-cleanup config: `configs/za/archive/za_2023_fixed_validation_pre_cleanup.yaml`
- Active config: `configs/za/za_2023_fixed_validation.yaml`

## Packaged PyPSA-RSA Reference Inputs

Normal ZA baseline reruns use packaged files inside this repo:

- `data/za_reference/pypsa_rsa_benchmark_2023/sub_scenarios/operational_constraints.xlsx`
- `data/za_reference/pypsa_rsa_benchmark_2023/sub_scenarios/plant_availability.xlsx`
- `data/za_reference/pypsa_rsa_benchmark_2023/sub_scenarios/fixed_technologies.xlsx`
- `data/za_reference/pypsa_rsa_benchmark_2023/sub_scenarios/fuel_prices.xlsx`
- `data/za_reference/pypsa_rsa_coal_flexibilisation/sub_scenarios/plant_availability.xlsx`
- `data/za_reference/supply_regions/rsa_supply_regions.gpkg`

The sibling `pypsa-rsa` checkout is now an audit/provenance input only, exposed
through `za_source_audits.pypsa_rsa_root`.

## Cost, Currency, And CoLS

The config keeps only runtime cost selectors:

- `costs.year: 2030`
- `costs.output_currency: ZAR`
- `costs.electricity_grid_connection: 0`

Detailed EUR/ZAR and policy Cost of Load Shedding reference values are owned by
the generated audit outputs:

- `data/za_audit/za_eur_zar_fxrate_2023.csv`
- `data/za_audit/za_cols_reference_values.csv`
- `doc/za_costs_fuels_efficiencies_and_coUE.md`

The solver load-shedding value remains a numerical safety-valve setting, not a
policy CoLS estimate.

## Operational Constraints And Annual Caps

`za_operational_constraints` is disabled in the baseline overlay. Labelled
diagnostics can enable `NO_MIN_GAS`, `LOW_GAS`, or `HIGH_GAS` explicitly.

Annual generation caps moved from `za_scarcity_cap` to the generic block:

```yaml
za_generation_constraints:
  annual_generation_caps:
    enable: false
    unit: TWh
    carriers: {}
```

The Eskom 2023 OCGT cap (`ocgt_diesel: 5.243`) is a diagnostic counterfactual,
not a hidden baseline setting.

## Hydro Multiplier

`renewable.hydro.multiplier: 1.20` is retained as a runtime value. Its rationale
is a structural correction rather than a 2023 residual-fit parameter:

- Eskom-vs-IRENA hydropower accounting scope correction.
- PyPSA-Earth hydro dispatch efficiency double-count correction.

The remaining 2023 hydro residual is treated as a year-conditioned ERA5/runoff
limitation and is not absorbed into the multiplier.

## Fleet Calibration

The active fleet selector is now generic:

```yaml
za_fleet:
  source: calibrated_2023
  exclude_powerplants: [Kelvin, Sasol coal, Sasol gas]
```

`calibrated_2023` aliases the Eskom nominal 2023 coal fleet used by Module 13m.
Kelvin and Sasol remain excluded from the baseline and can be reintroduced only
by changing `exclude_powerplants`.

## System Boundary And Local Carriers

Long system-boundary prose moved out of YAML. The current boundary remains:

- National South Africa 2023 electricity system.
- Demand target: Eskom RSA Contracted Demand.
- Load-shedding validation target: MLR + ILS + IOS.
- Gross imports/exports are exogenous time series from Module 06.
- Embedded/rooftop PV is excluded as explicit plant capacity in V1.
- CSP keeps the 2023 500 MW / 1.375 TWh anchor.

The YAML keeps only `za_local_carriers` metadata consumed by carrier-taxonomy and
local-cost tooling.

## Grid Spatial Provenance

`za_grid_spatial` remains in config because grid-build scripts consume the
values. Rationale and reconciliation details are documented in:

- `doc/za_grid_reconciliation.md`
- `data/za_audit/za_grid_reconciliation.csv`
- `data/za_audit/za_spatial_level_lock.csv`

The 34-region layer reflects the Stage 4b local-area decision. St Clair
coefficients and thermal/SIL ratings are pinned to the PyPSA-RSA-derived audit
bundle and packaged reference layer.
