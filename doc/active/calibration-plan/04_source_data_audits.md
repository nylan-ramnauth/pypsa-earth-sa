# 04 Source Data Audits

## Goal

Build the complete PyPSA-RSA and South Africa source registry before deciding
the final fleet, carrier taxonomy, costs, demand allocation, or grid
representation. This module produces audit tables only; it does not create the
final PyPSA-Earth model.

The local PyPSA-RSA reference commit for this registry is:

```text
89872c1ea703af3d8a3f198706d1ab7958f50a5f
```

On module entry, `git rev-parse HEAD` in the PyPSA-RSA repo must match this
commit. If it does not, rerun the source audit before locking any downstream
fleet, grid, cost, or availability assumptions.

### No-silent-rebase policy

The pypsa-rsa commit pin freezes a known reference state. If pypsa-rsa main has advanced beyond
the pinned commit at implementation time, the implementing agent must:
1. Verify the pinned commit still exists (not squashed/rebased away)
2. Review the diff between the pin and current HEAD
3. Determine whether any change affects fleet data, cost data, availability, or grid evidence
4. Accept or reject the upgrade explicitly in `doc/za_implementation_log.md`

Auto-following pypsa-rsa main without explicit review is not allowed.

PyPSA-RSA warns that important data may be external, original-source, or Google
Drive inputs. The registry must therefore include tracked files and required
external placeholders.

## Source Registry

Write the normative source registry:

```text
data/za_audit/pypsa_rsa_source_registry.csv
```

Required columns:

```text
source_path
tracked_or_external
hash
sheet_or_layer
row_count
port_policy
owning_module
baseline_use
expansion_use
notes
```

`port_policy` values:

```text
audit_only
candidate_input
validation_reference
baseline_input_after_review
expansion_input_after_review
do_not_port
external_required
```

Where flat and nested copies of the same PyPSA-RSA bundle file both exist,
record both paths and hashes. Designate the deeper scenario-tagged copy as
canonical unless the audit records a content diff and an explicit override.

## Core PyPSA-RSA Data Registry

At minimum, registry coverage must include:

```text
README.md
config.yaml
Snakefile
scripts/add_electricity.py
scripts/build_topology.py
scripts/base_network.py
data/eskom_data.csv
data/eskom_pu_profiles.csv
data/bundle/SystemEnergy2009_22.csv
data/bundle/Supply area normalised power feed-in for Wind.xlsx
data/bundle/Supply area normalised power feed-in for PV.xlsx
data/turbine_power_curves.csv
data/ambitions_validation.xlsx
data/bundle/renewable_profiles_updated.nc
```

`data/eskom_data.csv` and `data/eskom_pu_profiles.csv` are validation/profile
references, not first-choice South Africa 2023 model inputs.

### Candidate missing files — verify against pinned commit

The following files may exist in pypsa-rsa at the pinned commit and should be added to the
minimum registry coverage if present:

- `scripts/solve_network.py` — pypsa-rsa solve script with COUE/load-shedding handling
- `scripts/add_extra_components.py` — CSP and storage component handling
- `scripts/build_renewable_profiles.py` — RSA-specific renewable siting logic
- `scripts/prepare_and_solve_network.py` (if present) — workflow constraint logic
- `pre_processing/resource_processing/reipppp_phs_data.csv` (if present) — PHS reconciliation
- IRP coal retirement schedule files (any `.xlsx` under `scenarios/` matching IRP 2023)
- `envs/environment.yaml` — version pinning reference

### Discovery sweep (required)

Before sealing the registry, run:
```bash
find . -name '*.py' -o -name '*.xlsx' -o -name '*.csv' -o -name '*.gpkg' | grep -v '.git'
```
For every file ≥10 KB, reconcile against the registry as either `audit_only`, `do_not_port`, or
add it to the minimum coverage list. Record the sweep results in `doc/za_implementation_log.md`.

## Powerplantmatching Audit

Build a South Africa powerplantmatching extraction that retains conventional,
hydro, storage, wind, PV, CSP, bioenergy, waste, and other plants. The default
PyPSA-Earth `build_powerplants.py` output is not sufficient because it filters
out solar and wind.

Outputs:

```text
data/za_audit/powerplants_pm_za_full.csv
data/za_audit/powerplants_pm_za_audit.csv
```

Preserve at least:

```text
Name, Fueltype, Technology, Set, Country, Capacity, DateIn, DateOut,
lat, lon, projectID, source_count, source flags, raw_project_ids
```

## PyPSA-RSA Scenario Workbook Inventory

Audit all scenario workbooks that can influence fleet, costs, availability,
demand, transmission, emissions, or expansion assumptions.

Inputs include at minimum:

```text
scenarios/ME IRP 2024/scenarios_to_run.xlsx
scenarios/ME IRP 2024/sub_scenarios/annual_load.xlsx
scenarios/ME IRP 2024/sub_scenarios/carbon_constraints.xlsx
scenarios/ME IRP 2024/sub_scenarios/fixed_technologies.xlsx
scenarios/ME IRP 2024/sub_scenarios/extendable_technologies.xlsx
scenarios/ME IRP 2024/sub_scenarios/operational_constraints.xlsx
scenarios/ME IRP 2024/sub_scenarios/plant_availability.xlsx
scenarios/ME IRP 2024/sub_scenarios/reserve_margin.xlsx
scenarios/ME IRP 2024/sub_scenarios/transmission_expansion.xlsx
scenarios/Coal_Flexibilisation/scenarios_to_run.xlsx
scenarios/Coal_Flexibilisation/sub_scenarios/annual_load.xlsx
scenarios/Coal_Flexibilisation/sub_scenarios/aux_stg_feed.xlsx
scenarios/Coal_Flexibilisation/sub_scenarios/emissions.xlsx
scenarios/Coal_Flexibilisation/sub_scenarios/extendable_technologies.xlsx
scenarios/Coal_Flexibilisation/sub_scenarios/fixed_technologies.xlsx
scenarios/Coal_Flexibilisation/sub_scenarios/fuel_prices.xlsx
scenarios/Coal_Flexibilisation/sub_scenarios/operational_constraints.xlsx
scenarios/Coal_Flexibilisation/sub_scenarios/plant_availability.xlsx
scenarios/Coal_Flexibilisation/sub_scenarios/phased_decommissioning.xlsx
scenarios/Coal_Flexibilisation/sub_scenarios/reserve_margin.xlsx
scenarios/Coal_Flexibilisation/sub_scenarios/transmission_expansion.xlsx
scenarios/Coal_Flexibilisation/sub_scenarios/weather.xlsx
```

Output:

```text
data/za_audit/pypsa_rsa_scenario_workbook_inventory.csv
```

The inventory must record workbook sheets, row counts, relevant columns, active
scenario flags where present, and whether the file is baseline, validation, or
expansion evidence.

## Fleet, Availability, And REIPPPP Audits

Extract 2023-active candidates from:

```text
scenarios/ME IRP 2024/sub_scenarios/fixed_technologies.xlsx
pre_processing/resource_processing/reipppp_solar_data.csv
pre_processing/resource_processing/reipppp_wind_data.csv
scenarios/ME IRP 2024/sub_scenarios/plant_availability.xlsx
scenarios/ME IRP 2024/sub_scenarios/operational_constraints.xlsx
scenarios/ME IRP 2024/sub_scenarios/reserve_margin.xlsx
```

Outputs:

```text
data/za_audit/pypsa_rsa_fixed_technologies_2023_candidates.csv
data/za_audit/reipppp_solar_2023_candidates.csv
data/za_audit/reipppp_wind_2023_candidates.csv
data/za_audit/pypsa_rsa_availability_audit.csv
data/za_audit/pypsa_rsa_operational_constraints_audit.csv
data/za_audit/pypsa_rsa_reserve_margin_audit.csv
```

Filter rule:

```text
Commissioning Date <= 2023
and
Decommissioning Date > 2023 or beyond 2050 or missing
```

Rows with future CODs, including Redstone CSP and 2024-2027 BESS rows, remain in
audit files but must be marked `included_2023 = false`.

## Profile Reference Audit

Audit normalized PyPSA-RSA/Eskom profile references before module 03 Gate B
consumes them.

Inputs include:

```text
data/eskom_pu_profiles.csv
data/bundle/renewable_profiles_updated.nc
data/bundle/Supply area normalised power feed-in for Wind.xlsx
data/bundle/Supply area normalised power feed-in for PV.xlsx
```

Output:

```text
data/za_audit/pypsa_rsa_eskom_pu_profiles_audit.csv
```

## Cost Fuel Emissions Audit

Audit the actual PyPSA-RSA cost and emissions sources used by its workflow.

Inputs include at minimum:

```text
scenarios/Coal_Flexibilisation/sub_scenarios/fuel_prices.xlsx
scenarios/Coal_Flexibilisation/sub_scenarios/emissions.xlsx
scenarios/ME IRP 2024/sub_scenarios/fixed_technologies.xlsx
scenarios/ME IRP 2024/sub_scenarios/extendable_technologies.xlsx
config.yaml
scripts/add_electricity.py
```

Output:

```text
data/za_audit/pypsa_rsa_cost_fuel_emissions_audit.csv
```

The audit must capture fuel prices, emissions factors, heat rates,
efficiencies, VOM/FOM, COUE/load-shedding currency assumptions, and the code
paths in PyPSA-RSA that transform those inputs into generator costs.

## Load Weight Audit

PyPSA-RSA uses `load_disaggregation: GVA_2016`. This module extracts the raw
PyPSA-RSA GVA_2016 and POP_2016 weighting evidence only. The downstream
comparison against the PyPSA-Earth V1 load allocation is owned by
`06_demand_import_export_model_inputs.md`.

Inputs include:

```text
config.yaml
data/bundle/supply_regions/rsa_supply_regions.gpkg
data/bundle/supply_regions/rsa_supply_regions2.gpkg
data/bundle/CSIR/Mesozones/
```

`data/bundle/CSIR/Mesozones/` is a directory. The audit must traverse contained
shapefiles/GPKGs and record each discovered file/layer in the source registry.

Outputs:

```text
data/za_audit/pypsa_rsa_load_weight_audit.csv
```

The audit must expose GVA_2016 and POP_2016 weights by available supply-region
layer. The downstream comparison against PyPSA-Earth allocation is owned by
`06_demand_import_export_model_inputs.md`.

## Grid Spatial And External Bundle Inventory

Audit portable GIS/grid sources before `09_grid_spatial_and_transmission_model.md`
chooses custom subregions, custom busmaps, line/substation additions, or
corridor caps.

Inputs include at minimum:

```text
data/bundle/supply_regions/rsa_supply_regions.gpkg
data/bundle/supply_regions/rsa_supply_regions2.gpkg
data/bundle/GCCA 2025 GIS/AREAS_GCCA2025.gpkg
data/bundle/GCCA 2025 GIS/SUPPLY_AREA_GCCA2025.*
data/bundle/GCCA 2025 GIS/LOCAL_AREA_GCCA2025.*
data/bundle/GCCA 2025 GIS/MTS_ZONES_GCCA2025.*
data/bundle/Shapefiles/Existing_Lines.*
data/bundle/Shapefiles/Planned_Lines.*
data/bundle/Shapefiles/Existing_Substations.*
data/bundle/Shapefiles/Planned_Substations.*
data/bundle/Shapefiles/Supply_Areas2022_Steady_State_Limit.*
data/bundle/Shapefiles/MTS_Subs2022.*
data/bundle/transmission_grid/tdp_digitised/TDP_2023_32.*
data/bundle/transmission_grid/eskom_gcca_2022/Existing_Lines.*
```

Outputs:

```text
data/za_audit/pypsa_rsa_external_bundle_inventory.csv
data/za_audit/za_rsa_supply_regions.geojson
data/za_audit/za_rsa_existing_lines_220kv_plus.geojson
data/za_audit/za_rsa_planned_tdp_lines.geojson
data/za_audit/za_rsa_supply_area_connection_limits.csv
data/za_audit/za_rsa_mts_hosting_limits.csv
data/za_audit/pypsa_rsa_transmission_expansion_audit.csv
```

The registry must identify 1/10/27/34/159 supply-region layers where present.

## Resource Siting Audit

Catalog expansion-only renewable siting and resource evidence without activating
it for the fixed 2023 baseline.

Inputs include at minimum:

```text
data/bundle/Power_corridors/
data/bundle/REDZ_DEA_Unpublished_Draft_2015/
data/bundle/Phase2_REDZs/
data/bundle/SAPAD_OR_2023_Q3.*
data/bundle/SACAD_OR_2023_Q3.*
data/bundle/SALandCover_OriginalUTM35North_2013_GTI_72Classes/
data/bundle/ZAF_wind-speed_100m.tif
data/bundle/ZAF15adjv4.tif
data/bundle/Shapefiles/RE_IPP_1_to_4b.*
pre_processing/resource_processing/
```

Output:

```text
data/za_audit/pypsa_rsa_resource_siting_audit.csv
```

These sources are expansion/handoff evidence only unless another module is
explicitly reopened and reviewed.

## Acceptance Gates

- `pypsa_rsa_source_registry.csv` exists and covers every tracked/external
  source family listed above.
- Scenario workbook inventory includes ME IRP 2024 carbon constraints and Coal
  Flex fixed technologies, plant availability, reserve margin, operational
  constraints, and transmission expansion workbooks when present.
- Registry includes `SystemEnergy2009_22.csv`, the exact supply-area normalized
  wind/PV workbook inputs listed above, and portable
  `pre_processing/resource_processing/` inputs with `port_policy = audit_only`
  or `validation_reference`.
- Every registry row has source path, tracked/external status, hash or external
  placeholder, port policy, owning module, baseline use, and expansion use.
- Flat and nested duplicate bundle files are both hashed and one canonical copy
  is designated.
- All required audit outputs exist with row counts and source hashes recorded.
- Future assets are retained for audit but excluded from 2023 by flag.
- PPM source provenance is parsed into source flags.
- PyPSA-RSA `eskom_pu_profiles.csv` is cataloged in the audit inventory; the
  profile-reference audit used by renewable validation is owned by this module
  and consumed only by module 03 Gate B.
- `transmission_expansion.xlsx` is preserved as candidate corridor evidence for
  expansion handoff, not used as active 2023 build data.
- No final fleet, carrier, cost, demand, or grid override is written by this
  module.
