# ZA Demand Import Export Model Inputs

## Summary

Module 06 converts the cleaned Eskom 2023 hourly data into model-facing demand,
gross import/export, and `other_re` input artifacts for the fixed 2023 South
Africa validation build.

## Demand

- Demand target: `RSA Contracted Demand`.
- Output rows: 8760.
- Annual demand: 225.874862263 TWh.
- Module 02 target: 225.874862263 TWh.
- GEGIS export: `data/ssp2-2.6/2030/era5_2023_custom/Africa.csv`.

The ZA overlay must use `load_options.weather_year: 2023_custom` and
`load_options.prediction_year: 2030`, which makes upstream
`build_demand_profiles.py:get_load_paths_gegis` resolve the South Africa demand
input through the GEGIS CSV route.

## Import Export Sign Convention

- `International Imports` is a positive supply injection into South Africa.
- `International Exports` is a positive withdrawal from South Africa.
- Net import is reported only as `imports - exports`; model inputs keep gross
  imports and gross exports separate.

Annual gross imports: 10.841729721 TWh.
Annual gross exports: 11.250298267 TWh.
Annual net import: -0.408568546 TWh.

## Other RE

`Other RE` is an exogenous local carrier input, not negative demand. Module 10
must add it as a non-extendable `Generator` with carrier `other_re`, `p_nom =
50.580000 MW`, `p_min_pu = 0`, and `p_max_pu` from
`data/za_validation/za_2023_other_re_timeseries.csv`.

- Annual Other RE energy: 0.237644992 TWh.
- Maximum raw `Other RE / p_nom`: 0.874199.
- Clipped hours: 0.
- Daily maximum ratio exceeded 1.05 warning threshold: no.

## Spatial Attachments

Demand weights for candidate layers `1`, `10`, and `34` use PyPSA-Earth-style
allocation: area-overlay GADM GDP/population components with normalized
`0.6 * gdp + 0.4 * pop`. PyPSA-RSA `GVA_2016` and `POP_2016` are diagnostic
only and are not used as V1 allocation weights.

Conservative proxy attachments are used for non-demand series:

- imports: national `ZA`, `Gauteng` for layer `10`, `Pretoria` for layer `34`.
- exports: demand-weight proxy because the Eskom source has no border split.
- Other RE: demand-weight proxy because the Eskom hourly source has no plant
  locations.

PyPSA-RSA diagnostic rows available: 1; unavailable:
44. Module 09 resolves final PyPSA-Earth bus IDs and may
replace proxy attachments with stronger grid evidence.

## Artifacts

- `data/za_validation/za_2023_demand_profile.csv`
- `data/ssp2-2.6/2030/era5_2023_custom/Africa.csv`
- `data/za_validation/za_2023_import_export_timeseries.csv`
- `data/za_validation/za_2023_other_re_timeseries.csv`
- `data/za_audit/za_2023_load_allocation_weights.csv`
- `data/za_audit/pypsa_rsa_gva_pop_load_weight_comparison.csv`
- `data/za_audit/za_2023_import_export_attachment.csv`
- `data/za_audit/za_2023_other_re_attachment.csv`
