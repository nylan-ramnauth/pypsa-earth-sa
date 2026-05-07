# 06 Demand Import Export Model Inputs

## Goal

Produce the 8760 demand, import, export, load-allocation, sign-convention, and
bus-attachment artifacts consumed by the fixed 2023 PyPSA-Earth network build.

## Inputs

Use outputs from `02_eskom_validation_data_pipeline.md`:

```text
data/za_validation/eskom_2023_hourly_clean.csv
data/za_validation/eskom_2023_targets_by_carrier.csv
```

Use spatial artifacts from `04_source_data_audits.md`. This module writes
allocation tables for the national node and candidate `10`/`34` supply-region
layers. `09_grid_spatial_and_transmission_model.md` later binds those
allocation tables to actual PyPSA-Earth buses or custom busmaps.

## Demand Profile Contract

Write:

```text
data/za_validation/za_2023_demand_profile.csv
data/za_audit/za_2023_load_allocation_weights.csv
data/za_audit/pypsa_rsa_gva_pop_load_weight_comparison.csv
doc/za_demand_import_export_model_inputs.md
```

## Integration Contract

The Eskom 8760 demand profile must enter upstream PyPSA-Earth through the GEGIS
load-data route unless this module is explicitly reopened. Export the cleaned
Eskom hourly demand to:

```text
data/ssp2-2.6/2030/era5_2023_custom/Africa.csv
```

using the GEGIS schema required by
`build_demand_profiles.py:get_load_paths_gegis`. The ZA overlay must set:

```yaml
load_options:
  weather_year: 2023_custom
  prediction_year: 2030
```

The single-node case is controlled by `scenario.clusters: [1]`; with
`clusters: 1`, the GEGIS allocation collapses to one bus by construction. No
separate national-bus demand hook is needed.

Bus attachment tables written here must use this schema:

```text
layer_key
attachment_type
source_id
target_region_id
weight
source_file
source_hash
notes
```

`attachment_type` is one of `demand`, `import`, `export`, or `other_re`.
Weights must sum to `1.0` within each `(layer_key, attachment_type,
source_id)` group. Module `09` resolves final PyPSA-Earth bus IDs; it must not
invent a different schema.

Demand rules:

- Model demand is `RSA Contracted Demand`.
- The demand profile has exactly 8760 hourly rows.
- Single-node runs attach all demand to the national ZA bus.
- In the GEGIS route, single-node runs are represented by `clusters: 1`, which
  collapses allocation to one bus by construction.
- Multi-node runs allocate demand with documented weights for candidate `10`
  and `34` region layers.
- V1 multi-node default is PyPSA-Earth demand allocation.
- PyPSA-RSA population/GVA supply-region logic is a diagnostic comparison only;
  switching V1 to PyPSA-RSA weights requires reopening this module for review.
- Static load allocation weights must sum to 1.0 for each spatial layer and are
  applied to the 8760 national demand profile.
- The diagnostic comparison must consume
  `data/za_audit/pypsa_rsa_load_weight_audit.csv` from `04` and report GVA_2016
  and POP_2016 deviations from PyPSA-Earth allocation.

## Import Export Contract

Write:

```text
data/za_validation/za_2023_import_export_timeseries.csv
data/za_validation/za_2023_other_re_timeseries.csv
data/za_audit/za_2023_import_export_attachment.csv
data/za_audit/za_2023_other_re_attachment.csv
```

Sign convention:

- `International Imports` is a positive supply injection into South Africa.
- `International Exports` is a positive withdrawal from South Africa.
- Net import may be reported as `imports - exports`, but model inputs must keep
  gross imports and gross exports separate.

Attachment rules:

- Single-node runs attach imports and exports to the national ZA bus.
- Multi-node runs define candidate border/proxy bus attachment tables for `10`
  and `34` region layers. `09` resolves the final bus IDs after grid clustering
  or custom busmap construction.
- For V1, gross Eskom `International Imports` are attributed to the
  `hydro_import` exogenous import series by default. If source data expose a
  non-hydro residual, report it separately but do not split the model input
  without reopening this module.
- `Other RE` is written as a separate 8760 exogenous series for the local
  `other_re` carrier locked in `05`; it is not folded into demand.
- `Other RE` enters the network as a non-extendable `Generator` with carrier
  `other_re`, `p_nom` equal to the reconciled Other RE installed-capacity
  anchor, `p_min_pu = p_max_pu` derived from the Eskom Other RE profile divided
  by `p_nom`, and `marginal_cost = 0`. Module `10` writes the generator, carrier
  row, and fixed dispatch time series.
- `Other RE` ratios are clipped with the locked rule: values `< 0` become `0`,
  values `> p_nom` become `1`, and the parser logs a warning whenever the
  daily maximum `Other RE / p_nom` ratio exceeds `1.05`.

## Acceptance Gates

- Demand, import, export, and `Other RE` files have exactly 8760 hourly
  snapshots aligned to the cleaned Eskom time index; multi-node files use
  columns per bus/carrier rather than extra rows.
- Sign convention is documented in CSV metadata or report text.
- Single-node and multi-node attachment policies are explicit.
- Bus attachment files use the schema above and pass the sum-to-one checks for
  every layer and attachment type.
- `Other RE` attachment is fixed as a non-extendable Generator with fixed
  dispatch, not a negative Load or Link.
- Load-allocation weights exist and pass sum/coverage checks.
- PyPSA-RSA GVA_2016/POP_2016 load-weight comparison exists and is marked
  diagnostic-only.
- Provenance records the cleaned Eskom input and any spatial weighting inputs.
