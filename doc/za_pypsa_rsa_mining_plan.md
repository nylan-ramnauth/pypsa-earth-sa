# Roadmap: Mine PyPSA-RSA Into a Reproducible PyPSA-Earth South Africa Baseline

## Brief

- Keep PyPSA-Earth as the implementation target for a clean South Africa baseline.
- Mine PyPSA-RSA only for South Africa-specific data, assumptions, validation structure, and audit benchmarks.
- Build a fixed-capacity 2023 validation model before any reliability-index or expansion work.
- Use Eskom 2023 hourly data as the validation authority.
- Use PyPSA-Earth/atlite as the first-choice route for wind, PV, hydro, and CSP availability profiles.
- Freeze the reconciled plant fleet in `data/custom_powerplants.csv`, with all manual decisions documented.
- Treat PyPSA-RSA grid, supply-region, and outage data as benchmark layers before changing PyPSA-Earth behavior.

## Scope And Repository Context

This roadmap is for a future Codex instance with access to both repositories:

- PyPSA-Earth target repo: `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth`
- PyPSA-RSA reference repo: `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-rsa`

The goal is to stay on current PyPSA-Earth while improving the South Africa model with selected data, assumptions, and validation patterns from the Meridian Economics PyPSA-RSA model.

PyPSA-RSA is South Africa-specific and highly useful as a reference, but it is older, less maintained, and less directly reproducible than PyPSA-Earth. Do not port the PyPSA-RSA workflow wholesale. Re-implement only selected concepts using current PyPSA-Earth conventions.

## Guardrails

- Keep PyPSA-Earth as the implementation target.
- Do not modify upstream defaults unless the change is generic, narrow, and acceptable upstream.
- Keep South Africa-specific assumptions local, documented, and testable.
- Do not start reliability-index implementation until the baseline, demand preprocessing, and Eskom validation workflow exist.
- Use short-snapshot smoke tests during development; full-year South Africa runs are heavy.
- Treat PyPSA-RSA code as design reference only. Do not blindly copy implementation code.
- Do not include future contracted assets in the 2023 baseline unless explicitly modeled as future expansion.

Recommended local outputs in PyPSA-Earth:

```text
data/custom_powerplants.csv
data/za_validation/
data/za_audit/
resources/<run>/...
doc/za_*.md
```

## Core Decision Rules

1. Use `eskom_data_2023_full.csv` as the validation source of truth.
2. Use `powerplantmatching` as a broad candidate inventory, not the final authority.
3. Use PyPSA-RSA as a South Africa-specific reconciliation and assumptions source, not an implementation target.
4. Freeze the final plant inventory in `data/custom_powerplants.csv`.
5. Document every manual adjustment in a reconciliation table.
6. Validate the final PyPSA network and solved outputs, not only CSV inputs.
7. Keep CSP separate from PV.
8. Use atlite first for wind, PV, hydro, and CSP availability profiles.
9. Use Eskom/PyPSA-RSA renewable profiles only as validation and calibration references unless an atlite route is infeasible.
10. Do not trust a custom plant row until its normalized PyPSA-Earth carrier has been checked in `networks/elec.nc`.
11. Keep PyPSA-Earth conventions and limit South Africa-specific code to local documented hooks.

## PyPSA-Earth Power Plant Workflow

Relevant PyPSA-Earth files:

```text
Snakefile
scripts/build_powerplants.py
scripts/add_electricity.py
configs/powerplantmatching_config.yaml
config.default.yaml
data/custom_powerplants.csv
```

PyPSA-Earth builds `resources/<run>/powerplants.csv` through rule `build_powerplants`, which calls:

```python
pm.powerplants(from_url=False, update=True, config_update=config)
```

with `configs/powerplantmatching_config.yaml`.

The configured sources are:

| Code | Likely source |
|---|---|
| `GEO` | Global Energy Observatory |
| `GPD` | Global Power Plant Database / WRI |
| `GBPT` | GEM Global Bioenergy Power Tracker |
| `GGPT` | GEM Global Gas Power Tracker |
| `GCPT` | GEM Global Coal Plant Tracker |
| `GGTPT` | GEM Global Geothermal Power Tracker |
| `GNPT` | GEM Global Nuclear Power Tracker |
| `GSPT` | GEM Global Solar Power Tracker |
| `GWPT` | GEM Global Wind Power Tracker |
| `GHPT` | GEM Global Hydropower Tracker |

PyPSA-Earth currently drops solar and wind from the default `powerplantmatching` output:

```python
.query('Fueltype not in ["Solar", "Wind"] and Country in @countries_names')
```

This means the default `powerplants.csv` is not a complete South African plant inventory. It mainly represents conventional, hydro, and storage-like assets. Wind and solar are usually handled through renewable profile rules and aggregate capacity estimation.

`scripts/add_electricity.py` can attach existing wind and solar plants if they are present in `powerplants.csv`:

```text
Technology == "Onshore"  -> onwind
Technology == "Offshore" -> offwind-ac
Fueltype/Carrier Solar   -> solar
```

CSP must not silently become normal PV. It needs explicit handling and validation.

## Renewable Profile Strategy

Use PyPSA-Earth's native atlite workflow for wind, solar PV, hydro inflow, and CSP unless a specific PyPSA-Earth/atlite route is proven infeasible.

Rationale:

- PyPSA-Earth builds renewable profiles through `scripts/build_renewable_profiles.py`.
- The rule produces `resources/<run>/renewable_profiles/profile_{technology}.nc`.
- `scripts/add_electricity.py` consumes those profile files and attaches `p_max_pu`, `p_nom_max`, and existing renewable capacity to generators.
- Atlite converts weather data into power-system time series, which is the right physical basis for a weather-dependent 2023 dispatch validation.
- Eskom observed wind/PV/CSP generation includes curtailment, outages, dispatch behavior, grid constraints, commissioning timing, and metering/accounting boundaries. It is not pure resource availability.

### 2023 Cutout Requirement

The default PyPSA-Earth configuration uses `cutout-2013-era5` and `build_cutout: false`. That is not acceptable for validation against Eskom hourly 2023 data. The validation run needs a South Africa 2023 weather cutout.

Required local configuration concept:

```yaml
enable:
  retrieve_cutout: false
  build_cutout: true

snapshots:
  start: "2023-01-01"
  end: "2024-01-01"

atlite:
  cutouts:
    cutout-2023-za-era5:
      module: era5
      dx: 0.3
      dy: 0.3
  default: cutout-2023-za-era5
```

This requires a working Copernicus Climate Data Store API setup. If the full-year cutout is too heavy during development, first build a short-snapshot smoke cutout for the same South Africa extent, then run the full 2023 cutout once the workflow is stable.

## Custom Power Plant Strategy

PyPSA-Earth supports custom power plants through:

```yaml
electricity:
  custom_powerplants: false  # default
```

Supported modes:

| Mode | Meaning |
|---|---|
| `false` | Use only `powerplantmatching` output. |
| `merge` | Concatenate `powerplantmatching` output with `data/custom_powerplants.csv`. |
| `replace` | Skip `powerplantmatching`; use only `data/custom_powerplants.csv`. |

For a calibrated South Africa baseline, target:

```yaml
electricity:
  custom_powerplants: replace
```

with a curated, frozen `data/custom_powerplants.csv`.

Feasibility notes from PyPSA-Earth docs and local code:

- `custom_powerplants: replace` is supported and avoids running `powerplantmatching`.
- The custom file is read with `index_col=0`; the first column should be an explicit stable `id`. Do not let `Name` become the index.
- `Country` should be alpha-2 code `ZA`, not `South Africa`, because `build_powerplants.py` assigns buses by comparing custom rows to base-network country codes.
- The default `powerplants_filter` is applied after reading custom plants and uses uppercase columns such as `DateIn` and `DateOut`. Keep these columns numeric or blank, and test the query explicitly.
- `add_electricity.py` later normalizes columns to PyPSA names using the `powerplantmatching` accessor and lower-case column names. The custom CSV must use powerplantmatching-style values, not arbitrary local labels.
- For fixed 2023 validation, disable renewable capacity estimation from IRENA and capacity expansion. Otherwise PyPSA-Earth may add residual country-level renewable capacity to extendable generators.

Recommended fixed-validation configuration concept:

```yaml
electricity:
  custom_powerplants: replace
  estimate_renewable_capacities:
    stats: false
  extendable_carriers:
    Generator: []
    StorageUnit: []
    Store: []
    Link: []
```

If `extendable_carriers` must remain populated for workflow compatibility, ensure the validation run fixes or disables expansion before solving.

## Eskom 2023 Validation Data

Relevant file already present in PyPSA-Earth:

```text
eskom_data_2023_full.csv
```

This file should become the validation authority for the 2023 fixed-capacity dispatch model.

Observed columns include:

```text
Date Time Hour Beginning
RSA Contracted Demand
Residual Demand
Dispatchable Generation
Thermal Generation
Nuclear Generation
Eskom Gas Generation
Eskom OCGT Generation
Hydro Water Generation
Pumped Water Generation
Pumped Water SCO Pumping
Dispatchable IPP OCGT
Wind
PV
CSP
Other RE
Total RE
Wind Installed Capacity
PV Installed Capacity
CSP Installed Capacity
Other RE Installed Capacity
Total RE Installed Capacity
Installed Eskom Capacity
Total PCLF
Total UCLF
Total OCLF
Total UCLF+OCLF
Manual Load_Reduction(MLR)
ILS Usage
IOS Excl ILS and MLR
International Imports
International Exports
```

Parsing issue: most data rows have 43 fields but the header has 42. `Total UCLF+OCLF` is sometimes written with a comma decimal separator, for example `17953,568`, which splits it into two CSV fields. A parser must repair this before use.

After repair, the file spans:

```text
2022-12-01 00:00 to 2024-02-01 23:00
```

The 2023 validation period is:

```text
2023-01-01 00:00 to 2023-12-31 23:00
8760 hourly rows
```

Key 2023 totals from the repaired file:

| Quantity | 2023 total |
|---|---:|
| RSA Contracted Demand | 225.875 TWh |
| Residual Demand | 207.190 TWh |
| Dispatchable Generation | 190.434 TWh |
| Thermal Generation | 165.627 TWh |
| Nuclear Generation | 8.127 TWh |
| Eskom OCGT Generation | 3.566 TWh |
| Dispatchable IPP OCGT | 1.677 TWh |
| Hydro Water Generation | 1.992 TWh |
| Pumped Water Generation | 4.294 TWh |
| Pumped Water SCO Pumping | -5.658 TWh |
| Wind | 11.613 TWh |
| PV | 5.015 TWh |
| CSP | 1.375 TWh |
| Other RE | 0.238 TWh |
| Total RE | 18.241 TWh |
| Manual Load Reduction | 16.562 TWh |

Installed renewable capacity in 2023:

| Carrier | Eskom 2023 target |
|---|---:|
| Wind | 3442.57 MW |
| PV | 2212.09 MW at start, 2287.09 MW by end |
| CSP | 500.00 MW |
| Other RE | 50.58 MW |
| Total RE | 6205.24 MW at start, 6280.24 MW by end |
| Installed Eskom Capacity | 46686 MW |

Useful accounting identities:

```text
Total RE = Wind + PV + CSP + Other RE

Residual Demand = Dispatchable Generation
                + Manual Load_Reduction(MLR)
                + ILS Usage
                + IOS Excl ILS and MLR

RSA Contracted Demand ~= Residual Demand + Total RE
```

Validation choices:

- Use `RSA Contracted Demand` as the demand target.
- Do not subtract load shedding from demand before modeling.
- Treat `MLR + ILS + IOS` as observed reduced/unserved demand.
- Validate against final `networks/elec.nc` or solved network outputs, not only `powerplants.csv`.

## PyPSA-RSA Reference Findings

PyPSA-RSA is a South Africa-specific PyPSA model developed by Meridian Economics. It is marked under development and appears less maintained, but its data and scenario design are highly relevant.

Main PyPSA-RSA files previously inspected for this roadmap:

```text
README.md
config.yaml
Snakefile
docs/data_workflow.rst
docs/workflow.rst
scripts/build_topology.py
scripts/base_network.py
scripts/add_electricity.py
scripts/custom_constraints.py
data/eskom_data.csv
data/eskom_pu_profiles.csv
data/ambitions_validation.xlsx
pre_processing/resource_processing/reipppp_solar_data.csv
pre_processing/resource_processing/reipppp_wind_data.csv
scenarios/ME IRP 2024/scenarios_to_run.xlsx
scenarios/ME IRP 2024/sub_scenarios/
```

### Scenario Pack

Relevant folder:

```text
/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-rsa/scenarios/ME IRP 2024/sub_scenarios
```

Files:

```text
annual_load.xlsx
carbon_constraints.xlsx
extendable_technologies.xlsx
fixed_technologies.xlsx
operational_constraints.xlsx
plant_availability.xlsx
reserve_margin.xlsx
transmission_expansion.xlsx
```

Important: in `scenarios/ME IRP 2024/scenarios_to_run.xlsx`, all 48 scenarios were marked `run_scenario=False` when inspected. Treat the scenario pack as a reference dataset, not an active validated run configuration.

### Main Config Assumptions

Relevant file:

```text
config.yaml
```

Use `config.yaml` as an assumptions index. Do not port it wholesale.

| Config area | RSA assumption | How to use in PyPSA-Earth |
|---|---|---|
| GIS CRS | `geo_crs: EPSG:4326`, `distance_crs: EPSG:2049`, `area_crs: ESRI:54009` | Reference for South Africa distance/area calculations in grid and region audits. |
| Demand split | `electricity.load_disaggregation: GVA_2016` | Compare PyPSA-Earth load allocation against RSA GVA/population-weighted allocation for multi-node ZA runs. |
| Reference load year | `years.reference_load_year: 2017` | Do not use for 2023 validation; inspect `SystemEnergy2009_22.csv` only for alternative historical profiles. |
| Renewable profile datasets | wind = `wasa`, PV = `sarah`, hydro/bioenergy/CSP/hydro_import = `eskom` | Validation context only; keep PyPSA-Earth atlite-first for 2023. |
| Existing generator granularity | `renewable_generators.apply_grouping: false`, `conventional_generators.apply_grouping: False`, `storage.apply_grouping: false` | Supports plant-level assets where data quality allows. |
| Renewable degradation | wind = 1%, PV = 3% lifetime capacity-factor adjustment | Candidate later sensitivity, not first 2023 fixed dispatch. |
| Conventional availability | `implement_availability: True`, `share_partial_outages.coal: 0.5` | Template for applying Eskom `PCLF/UCLF/OCLF` and `plant_availability.xlsx`. |
| CCGT representation | `ccgt_st_to_gt_ratio: 0.427` | Useful if modeling CCGT as gas turbines plus auxiliary steam turbine; likely later. |
| Unit commitment | `linearised_unit_committment: ["coal"]` | Candidate dispatch realism improvement after the baseline solves. |
| Outage-dependent ramping | `adjust_by_p_max_pu: coal/nuclear -> ramp_limit_up/down` | Useful if station-level availability profiles are applied. |
| Operating reserve carriers | coal, nuclear, OCGTs, CCGT steam, biomass, hydro | Reference for later reserve/reliability work. |
| Overgeneration | `allow_over_generation: True` | Diagnostic if early fixed dispatch is infeasible; document if used. |
| Load shedding cost | `COUE: 100000`, comment says R100/kWh | Candidate cost of unserved energy; verify units/currency before use. |
| Emission externalities | CO2, SOx, NOx, mercury, particulate prices | Later policy sensitivity, not first baseline. |

Prefer `eskom_data_2023_full.csv` and PyPSA-Earth-native inputs for the first validation baseline. Treat RSA config assumptions as candidate constraints and sensitivities only after the baseline plant fleet, demand, profiles, and grid are reproducible.

### Fixed Technologies

Relevant file:

```text
scenarios/ME IRP 2024/sub_scenarios/fixed_technologies.xlsx
```

Sheets:

```text
conventional
renewables
storage
```

This file is useful for plant names, capacities, coordinates, technology types, operating parameters, and commissioning/decommissioning assumptions. Do not copy scenario totals blindly into a 2023 baseline; some scenarios include future or contracted assets.

`BASE` conventional totals:

| Carrier | Capacity |
|---|---:|
| coal | 41530 MW |
| hydro | 600 MW |
| nuclear | 1854 MW |
| ocgt_avf | 342 MW |
| ocgt_diesel | 3077 MW |
| rmippp | 578 MW |
| sasol_coal | 728.04 MW |
| sasol_gas | 424.60 MW |

`BASE` renewable totals:

| Carrier | Capacity |
|---|---:|
| bioenergy | 313.06 MW |
| hydro | 83.02 MW |
| hydro_import | 1764 MW |
| solar_csp | 600 MW |
| solar_pv | 3821.81 MW |
| solar_pv_rooftop | 5439 MW |
| wind | 4242.08 MW |

These renewable totals exceed the 2023 Eskom validation capacities, so filter by commissioning date and reconcile against Eskom 2023 targets.

Important CSP detail:

| Plant | Capacity | COD | Storage |
|---|---:|---:|---:|
| Kaxu Solar One | 100 MW | 2015 | 3 h |
| Khi Solar One | 50 MW | 2015 | 6 h |
| Bokpoort CSP project | 50 MW | 2016 | 9 h |
| !XiNa Solar One | 100 MW | 2017 | 6 h |
| Karoshoek Solar One | 100 MW | 2019 | 6 h |
| Kathu Solar Park | 100 MW | 2019 | 6 h |
| Redstone Solar Thermal Power Plant | 100 MW | 2024 | 9 h |

For 2023 validation, Eskom reports CSP installed capacity of 500 MW. Exclude Redstone from the 2023 baseline.

Existing PHS rows:

| Plant | Capacity | Storage energy |
|---|---:|---:|
| Drakensberg | 1000 MW | 21.7 GWh |
| Ingula | 1324 MW in `BASE`, 1332 MW in `AMBITIONS` | 27.4 GWh |
| Palmiet | 400 MW | 10.0 GWh |
| Steenbras | 180 MW | 2.7 GWh |

Some BESS rows have commissioning years 2024-2027. Do not include them in a 2023 baseline unless independently justified.

### REIPPPP Wind And Solar Data

Useful files:

```text
pre_processing/resource_processing/reipppp_solar_data.csv
pre_processing/resource_processing/reipppp_wind_data.csv
```

Solar fields:

```text
Name
Key
latitude
longitude
capacity
BW
status
COD
Type
dc_ac_ratio
capacity_peak
yield
cf_dc
cf_ac
Comment
```

Wind fields:

```text
Name
latitude
longitude
capacity
BW
COD
status
hub_height
turbine
turbine_size
```

Use these as the main South Africa-specific reconciliation layer for wind/PV alongside `powerplantmatching` and Eskom aggregate targets.

### Eskom Profiles

Useful files:

```text
data/eskom_data.csv
data/eskom_pu_profiles.csv
```

`data/eskom_pu_profiles.csv` has normalized hourly profiles for:

```text
wind
solar_pv
solar_csp
hydro
hydro_import
bioenergy
```

Use these as validation profile references, comparison targets for PyPSA-Earth atlite profiles, and diagnostics when plant metadata or resource profiles appear biased.

Do not use these normalized profiles as first-choice model drivers for wind or solar PV. For CSP, they may be useful as a temporary diagnostic or fallback, but the preferred target remains a PyPSA-Earth/atlite CSP profile plus explicit CSP plant/storage treatment.

### Plant Availability

Relevant file:

```text
scenarios/ME IRP 2024/sub_scenarios/plant_availability.xlsx
```

Sheets:

```text
annual_availability
outage_profiles
min_station_hrly_cap_fact
```

This is one of the highest-value sources to mine. It contains annual EAF trajectories by station/carrier, weekly planned outage profiles, weekly unplanned outage profiles, and minimum hourly capacity-factor assumptions for coal.

For `BASE`, coal station EAF in 2023 is approximately `0.481`, matching the stressed 2023 Eskom system.

Example `BASE` EAF values:

| Group | 2023 | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|---:|
| Coal mean | 0.481 | 0.4076 | 0.3943 | 0.5016 | 0.5146 |
| Koeberg | 0.5083 | 0.9333 | 0.9000 | 0.9000 | 0.9000 |

Alternative EAF scenarios:

```text
BASE
EAF_50
EAF_55
EAF_60
EAF_70
EAF_REC
AMBITIONS
AMBITIONS_2
```

Use this as the first template for mapping Eskom `PCLF/UCLF/OCLF` to PyPSA-Earth `p_max_pu` time series.

### Operational Constraints

Relevant file:

```text
scenarios/ME IRP 2024/sub_scenarios/operational_constraints.xlsx
```

Scenario labels include:

```text
AMBITIONS
BASE
FUEL_SWITCH
FUEL_SWITCH_ST40
FUEL_SWITCH_ST50
IRP23
UNC_GAS
```

Useful assumptions:

| Constraint type | Example |
|---|---|
| OCGT annual use | `ocgt_diesel + ocgt_avf` max annual CF = 20% |
| OCGT weekly use | `ocgt_diesel + ocgt_avf` max weekly CF = 50% |
| VRE hourly cap | `wind + solar_pv + solar_csp` max output = 13145 MW until 2034 in some scenarios |
| Coal minimum annual use | coal min annual CF in some scenarios |
| Sasol energy cap | `sasol_coal` max 5.5 TWh/year, `sasol_gas` max 2.8 TWh/year |
| RMIPPPP | minimum capacity factor assumptions |

Do not impose all constraints immediately. Use them only if the 2023 fixed dispatch becomes unrealistic or infeasible.

### Reserve Margin And Capacity Credits

Relevant file:

```text
scenarios/ME IRP 2024/sub_scenarios/reserve_margin.xlsx
```

Capacity credits include:

| Technology | Capacity credit examples |
|---|---:|
| battery_1h | 0.25 |
| battery_3h | 0.50 |
| battery_4h | 0.50 |
| battery_8h | 0.50 or 0.75 |
| coal | 0.53 or 1.00 |
| nuclear | 1.00 |
| OCGT | 1.00 |
| PHS | 1.00 |
| solar PV | 0.00 |
| CSP | 0.50 |
| wind | 0.10 |

Reserve margin scenarios:

```text
RES_MRGN_0
RES_MRGN_5
RES_MRGN_10
RES_MRGN_10_31
```

Use this later for expansion/reliability planning, not the first 2023 baseline.

### Spatial And Grid Model

Relevant files:

```text
README.md
scripts/build_topology.py
scripts/base_network.py
config.yaml
data/bundle/supply_regions/rsa_supply_regions.gpkg
data/bundle/GCCA 2025 GIS/
data/bundle/Shapefiles/
data/bundle/transmission_grid/
data/bundle/Shapefiles/Existing_Lines.shp
data/bundle/Shapefiles/Planned_Lines.shp
data/bundle/transmission_grid/tdp_digitised/TDP_2023_32.shp
data/bundle/Shapefiles/Supply_Areas2022_Steady_State_Limit.shp
scenarios/ME IRP 2024/sub_scenarios/transmission_expansion.xlsx
```

PyPSA-RSA supports South Africa-specific spatial resolutions:

```text
1-supply
10-supply
27-supply
34-supply
159-supply
```

`data/bundle/supply_regions/rsa_supply_regions.gpkg` contains layers useful as alternative PyPSA-Earth clustering targets:

| Layer | Interpretation | Useful fields |
|---|---|---|
| `1` | RSA single node | `id`, `name`, `GVA2016`, `POP2016` |
| `10` | GCCA supply areas | `SupplyArea`, `name`, `Shape_Leng`, `Shape_Area` |
| `27` | local/supply regions | `id`, `name`, `POP2016`, `GVA2016` |
| `34` | local areas | `SupplyArea`, `LocalArea`, `name` |
| `159` | MTS zones | `MTS_1`, `SupplyArea`, `LocalArea`, `Substation`, `name` |

Recommended comparison levels:

- `1`: smoke test and national validation.
- `10`: first practical multi-node South Africa validation model.
- `27` or `34`: richer regional dispatch and transmission validation.
- `159`: reference/detail layer for MTS-level hosting capacity, probably too detailed for the first thesis baseline.

PyPSA-RSA's grid workflow is closer to a regional transfer-capacity model than a detailed AC line model. It:

1. Reads Eskom/NTCSA regional polygons from `rsa_supply_regions.gpkg`.
2. Joins population and GVA to those regions using mesozones.
3. Reads existing line shapefiles and, depending on scenario, TDP planned lines.
4. Maps each line's start/end point to supply regions.
5. Aggregates physical lines into inter-regional corridors.
6. Computes corridor limits using thermal, SIL, and St Clair limits.
7. Applies an N-1 approximation.
8. Converts inter-regional corridors into directed PyPSA `Link` components with distance-based losses.

Transmission assumptions in `config.yaml`:

```yaml
lines:
  threshold: 220
  v_nom: 400
  s_max_pu: 0.7
  n1_approx_single_lines: 0.7
  losses: 0.06  # per 1000 km AC line
```

Voltage-specific transfer assumptions:

| Voltage | Thermal limit | SIL limit |
|---:|---:|---:|
| 220 kV | 492 MW | 122 MW |
| 275 kV | 921 MW | 245 MW |
| 400 kV | 1788 MW | 602 MW |
| 765 kV | 5512 MW | 2280 MW |

Important RSA formulas and choices:

```text
Only voltages >= 220 kV are considered in network capacity calculations.
St_Clair_limit = min(thermal_limit, SIL_limit * 53.736 * length_km^-0.65)
If only one line exists between a region pair, multiply limit by n1_approx_single_lines = 0.7.
If multiple lines exist between a region pair, drop the line with the highest St Clair limit for the N-1 case.
Final base network uses St_Clair_limit_n1 as link p_nom.
Directional links are duplicated in both directions.
Link efficiency = 1 - losses * length_km / 1000, with losses = 0.06 per 1000 km.
```

Grid constraints to mine:

| Constraint | RSA value | PyPSA-Earth action |
|---|---:|---|
| Backbone voltage threshold | `>= 220 kV` | Use for RSA benchmark grid extraction and OSM coverage comparison. |
| Nominal regional voltage | `400 kV` | Default regional/corridor voltage for RSA-style benchmark links. |
| Operational transfer margin | `s_max_pu = 0.7` | Keep PyPSA-Earth's matching default `lines.s_max_pu: 0.7` unless a ZA-specific audit justifies a change. |
| Single-circuit N-1 derate | `n1_approx_single_lines = 0.7` | Apply when deriving RSA-style interregional corridor caps. |
| Multi-circuit N-1 derate | drop strongest line in corridor | Apply when deriving corridor caps from physical line shapefiles. |
| AC corridor losses | `0.06` per 1000 km | Use only for RSA-style transport `Link`s or transfer-model loss validation. |
| Length factor | `1.25` | Keep aligned with PyPSA-Earth's line length factor unless the grid audit shows systematic mismatch. |
| Under-construction treatment | `zero` by default | For 2023 validation, exclude future TDP capability or include it with zero capacity unless explicitly testing future network expansion. |

Do not overwrite PyPSA-Earth line electrical parameters with these values by default. First build an independent corridor benchmark:

```text
RSA physical lines -> RSA supply-region corridors -> St Clair limits -> N-1 corridor limits
```

Then compare it to:

```text
PyPSA-Earth OSM lines -> PyPSA-Earth clustered corridors -> effective s_nom after s_max_pu
```

Only add a local cap/override if the comparison shows PyPSA-Earth materially over- or under-estimates South African transfer capability.

Line source details:

| File | Use | Key fields / details |
|---|---|---|
| `data/bundle/Shapefiles/Existing_Lines.shp` | Existing Eskom transmission lines | fields include `LINE_START`, `LINE_END`, `DESIGN_VOL`, `NOMINAL_VO`, `LINE_STATU`, `SUB_CAT`, `LABEL`; 348 rows; voltage counts include 400 kV = 155, 275 kV = 141, 220 kV = 17, 765 kV = 8, plus lower/odd voltages. |
| `data/bundle/transmission_grid/tdp_digitised/TDP_2023_32.shp` | Digitised planned TDP lines | fields include `LINE_START`, `LINE_END`, `DESIGN_VOL`, `LINE_STATU`, `BUILD_YEAR`, `CHECK`, `Length`; 102 rows; 400 kV = 68, 765 kV = 23, 275 kV = 11. |
| `data/bundle/Shapefiles/Planned_Lines.shp` | Alternative planned-line source | Use for cross-checking TDP line geometry/status. |
| `scenarios/ME IRP 2024/sub_scenarios/transmission_expansion.xlsx` | User-defined candidate corridors | 16 candidate 400 kV corridors; current yearly build values sum to zero. Use as a candidate corridor list, not active expansion data. |

Hosting/connection capacity data:

| File | Use | Key fields / details |
|---|---|---|
| `data/bundle/Shapefiles/Supply_Areas2022_Steady_State_Limit.shp` | Supply-area steady-state connection limits | fields include `Name`, `Supply_Are`, `CLNLimit`, `CLNLimitMD`; 30 rows. Use to validate regional hosting/connection constraints. |
| `data/bundle/Shapefiles/MTS_Subs2022.shp` | MTS/substation-level transformer and hosting capacity | fields include `Supply_Are`, `Substation`, `Transforme`, `NoOfTrfrs`, `TrfrSizeMV`, `InstalledT`, `LightLoad`, `GxAtLightL`, `YearOfTrfr`, `UpgradeSta`, `MVLimitLL2`, `HVLimitLL2`, `HVAreaLimi`, `CLNLimitLL`, `HVLimitMDL`, `CLNLimitMD`, `Status`. Use later for MTS-level renewable hosting/build-limit validation. |

These connection-limit datasets are probably more useful for expansion constraints than for the first fixed 2023 dispatch baseline. For the baseline, first use them as plausibility checks on regional renewable capacity and corridor stress.

PyPSA-Earth grid integration hooks:

| Hook | Relevant PyPSA-Earth setting/file | Use for South Africa |
|---|---|---|
| OSM/custom line ingestion | `clean_osm_data_options.use_custom_lines`, `path_custom_lines` | Add or replace OSM raw lines with cleaned Eskom/NTCSA line geometries after converting to the expected schema. |
| Custom substations | `clean_osm_data_options.use_custom_substations`, `path_custom_substations` | Add Eskom/MTS substations if OSM substations are incomplete. |
| Custom subregions | `subregion.method: custom`, `path_custom_shapes` | Use Eskom supply regions as labels/boundaries during simplification/clustering. |
| Custom busmap | `enable.custom_busmap: true`, `data/custom_busmap_elec_s{simpl}_{clusters}.csv` | Force PyPSA-Earth OSM buses into RSA supply-region clusters. |
| Post-clustering branch constraints | custom local rule after `cluster_network` or before `solve_network` | Overwrite or cap inter-regional transfer capacities using RSA-derived St Clair/N-1 corridor limits. |

Recommended interpretation:

- Use PyPSA-Earth OSM as the first physical network build.
- Use PyPSA-RSA/Eskom line and supply-region data as audit and benchmark layers.
- If OSM misses major corridors or substations, add cleaned custom line/substation inputs.
- If regional transfer limits are materially wrong after clustering, add a South Africa-specific post-processing step to cap clustered line/link capacities by RSA-derived transfer corridors.
- Do not use PyPSA-RSA's directed-link transfer model as the default replacement for PyPSA-Earth's detailed network unless the model is intentionally moved to a supply-region transport representation.

### Demand Disaggregation

PyPSA-RSA disaggregates demand across regions using socioeconomic weights:

```yaml
electricity:
  load_disaggregation: "GVA_2016"
```

`scripts/build_topology.py` computes regional:

```text
POP_2016
GVA_2016
SIC sector GVA columns
```

Use this to compare or improve PyPSA-Earth demand spatial allocation for multi-node South Africa runs.

Do not use PyPSA-RSA `annual_load.xlsx` for the 2023 validation baseline. It gives `IRP2023 = 243 TWh` for 2023, while the Eskom hourly validation file gives `RSA Contracted Demand = 225.875 TWh`.

### Renewable Siting

Relevant files/directories:

```text
pre_processing/resource_processing/_helpers.py
pre_processing/resource_processing/prepare_availability_matrix.ipynb
data/bundle/Power_corridors/
data/bundle/REDZ_DEA_Unpublished_Draft_2015/
data/bundle/Phase2_REDZs/
data/bundle/SAPAD_OR_2023_Q3.*
data/bundle/SACAD_OR_2023_Q3.*
data/bundle/ZAF_wind-speed_100m.tif
```

PyPSA-RSA references South Africa-specific renewable siting constraints:

- REDZ.
- Strategic transmission corridors.
- EIA applications.
- SAPAD protected areas.
- SACAD conservation areas.
- SKA exclusion.
- South African land cover.
- Global Wind Atlas correction.

Use these for capacity expansion after the 2023 fixed model is calibrated.

## Implementation Milestones

### Milestone 0: Create Audit And Validation Directories

Create local folders:

```text
data/za_validation/
data/za_audit/
doc/
```

Suggested files:

```text
data/za_validation/eskom_2023_hourly_clean.csv
data/za_validation/eskom_2023_targets_by_carrier.csv
data/za_audit/powerplants_pm_za_full.csv
data/za_audit/powerplants_pm_za_audit.csv
data/za_audit/pypsa_rsa_fixed_technologies_2023_candidates.csv
data/za_audit/za_powerplant_reconciliation.csv
data/za_audit/za_atlite_renewable_profile_validation.csv
doc/za_powerplant_reconciliation.md
doc/za_renewable_profile_validation.md
```

### Milestone 1: Clean Eskom 2023 Validation Data

Implement a preprocessing script or notebook that:

1. Reads `eskom_data_2023_full.csv`.
2. Repairs the `Total UCLF+OCLF` comma-decimal split issue.
3. Parses timestamps.
4. Filters exactly `2023-01-01 00:00` to `2023-12-31 23:00`.
5. Writes a clean CSV.
6. Writes annual validation targets.
7. Checks the accounting identities listed in this document.

Use the cleaned output as the validation source of truth.

### Milestone 1A: Build A 2023 South Africa Atlite Cutout

Required choices:

```text
Weather year: 2023
Spatial extent: South Africa country shape plus PyPSA-Earth cutout margin
Dataset: ERA5
Resolution: start with PyPSA-Earth default dx/dy = 0.3 unless runtime or accuracy requires adjustment
Snapshots: 2023-01-01 00:00 to 2023-12-31 23:00
```

Implementation notes:

- Set `enable.build_cutout: true`.
- Set `enable.retrieve_cutout: false` for the 2023 validation run.
- Name the cutout clearly, for example `cutout-2023-za-era5`.
- Keep the cutout configuration in a South Africa-specific config overlay, not in global defaults.
- Use a short-snapshot smoke test first if full-year cutout generation is slow.

Validation checks:

- Confirm the cutout covers South Africa.
- Confirm the cutout time index has 8760 hourly snapshots for 2023.
- Confirm `build_renewable_profiles` can produce `profile_solar.nc`, `profile_onwind.nc`, `profile_hydro.nc`, and, if enabled, `profile_csp.nc`.
- Confirm each profile has non-empty bus coordinates, plausible `p_nom_max`, and plausible hourly `profile` values.

### Milestone 2: Generate Full South Africa Powerplantmatching Candidate Inventory

Build a dedicated audit extraction from PyPSA-Earth/powerplantmatching that keeps solar and wind. Do not use the default `build_powerplants.py` filtered output for this audit.

Target:

```python
config["target_countries"] = ["South Africa"]
```

Keep:

```text
Coal
Nuclear
Natural Gas
Oil / Diesel
Hydro
Pumped Storage
Battery
Wind
Solar PV
CSP
Bioenergy
Waste
Other
```

Outputs should preserve:

```text
Name
Fueltype
Technology
Set
Country
Capacity
DateIn
DateOut
lat
lon
projectID
source_count
has_GEO
has_GPD
has_GCPT
has_GGPT
has_GNPT
has_GSPT
has_GWPT
has_GHPT
raw_project_ids
```

The current `projectID` column gives partial provenance, for example:

```text
{'GNPT': {'...'}, 'GPD': {'...'}, 'GEO': {'...'}}
```

Parse it into source flags. It indicates matched source membership, not field-level provenance.

### Milestone 3: Extract PyPSA-RSA Candidate Fleet For 2023

Read PyPSA-RSA:

```text
scenarios/ME IRP 2024/sub_scenarios/fixed_technologies.xlsx
pre_processing/resource_processing/reipppp_solar_data.csv
pre_processing/resource_processing/reipppp_wind_data.csv
```

Filter candidate plants to 2023:

```text
Commissioning Date <= 2023
and
Decommissioning Date > 2023 or "beyond 2050" or missing
```

Use PyPSA-RSA for plant names, capacities, coordinates, fuel/carrier classification, CSP storage hours, PHS storage hours, REIPPPP metadata, and coal ramp/MSL/heat-rate candidate assumptions.

Do not directly adopt:

- Redstone CSP, COD 2024, for the 2023 baseline.
- BESS rows with COD 2024-2027.
- Future RMIPPPP or Karpowership rows unless independently justified for the target year.

### Milestone 4: Reconcile PPM, PyPSA-RSA, REIPPPP, And Eskom Targets

Create one reconciliation row per candidate plant:

```text
canonical_name
carrier
technology
capacity_mw_final
capacity_mw_ppm
capacity_mw_rsa
capacity_mw_reipppp
date_in_final
date_out_final
lat_final
lon_final
source_ppm
source_rsa
source_reipppp
status_2023
included_2023
decision
decision_reason
notes
```

Carrier totals must be checked against Eskom 2023:

| Carrier | Target |
|---|---:|
| Wind | 3442.57 MW |
| PV | 2212.09-2287.09 MW |
| CSP | 500 MW |
| Total RE | 6205.24-6280.24 MW |
| Installed Eskom Capacity | 46686 MW |

For conventional carriers, compare PyPSA-RSA fleet totals, powerplantmatching totals, Eskom installed capacity, and generation plausibility from Eskom 2023 dispatch.

### Milestone 5: Build `data/custom_powerplants.csv`

After reconciliation, write a frozen PyPSA-Earth-compatible file:

```text
data/custom_powerplants.csv
```

Use:

```yaml
electricity:
  custom_powerplants: replace
```

Required columns should follow PyPSA-Earth/powerplantmatching style:

```text
id
Name
Fueltype
Technology
Set
Country
Capacity
Efficiency
Duration
Volume_Mm3
DamHeight_m
StorageCapacity_MWh
DateIn
DateRetrofit
DateOut
lat
lon
EIC
projectID
bus
```

Column and tagging rules:

- Put `id` first so `read_csv(..., index_col=0)` does not consume `Name`.
- Use `Country = ZA` for every South Africa row.
- Provide explicit `DateIn` for every plant. Avoid relying on mean build-year filling.
- Keep `DateOut` blank only when the plant should remain available beyond the validation year.
- Use `Capacity` in MW.
- Preserve `projectID` as provenance, for example `RSA_FIXED_TECHNOLOGIES|REIPPPP|PPM_GSPT`.
- Do not rely on `bus` in the initial curated file unless bus assignment has been audited. `build_powerplants.py` can assign the nearest base-network substation from `lat/lon`.

Mapping considerations:

| RSA concept | PyPSA-Earth treatment |
|---|---|
| coal | conventional generator, likely `Hard Coal` -> `coal` |
| nuclear | conventional generator |
| ocgt_diesel / ocgt_avf / sasol_gas | decide mapping to `OCGT`, `oil`, `Natural Gas`, or local carriers |
| PHS | `Hydro` + `Pumped Storage` |
| reservoir hydro | `Hydro` + `Reservoir` |
| wind | `Wind` + `Onshore` |
| solar_pv | `Solar` + `PV` |
| solar_csp | do not collapse into PV; add explicit CSP handling |
| battery | `Battery` / storage |

Carrier-specific feasibility notes:

| Carrier | Feasibility in PyPSA-Earth | Required custom tagging / caveat |
|---|---|---|
| Coal | Feasible through conventional generator attachment | Use `Fueltype = Hard Coal`; provide plant capacity and date fields. |
| Nuclear | Feasible through conventional generator attachment | Use nuclear-compatible powerplantmatching tags; verify Koeberg normalizes to carrier `nuclear`. |
| OCGT / CCGT | Feasible, but gas tags must normalize cleanly | Tag technology explicitly as `OCGT` or `CCGT`; verify normalized carrier. |
| Diesel / oil peakers | Feasible if mapped to an existing cost carrier | Decide whether to map to `oil`, `OCGT`, or a local carrier with matching cost rows. |
| Wind | Feasible; existing wind from custom powerplants is supported | Use `Fueltype = Wind`, `Technology = Onshore`; existing capacity uses `profile_onwind.nc`. |
| Solar PV | Feasible; existing solar from custom powerplants is supported | Use `Fueltype = Solar`, `Technology = PV`/`Pv`; verify normalized carrier is `solar`. |
| Hydro ROR / reservoir / PHS | Feasible but profile-dependent | Use exact technologies `Run-Of-River`, `Reservoir`, `Pumped Storage`; ROR/reservoir need matching hydro inflow in `profile_hydro.nc`; PHS does not need natural inflow. |
| Battery | Existing battery support exists | Current code uses `electricity.max_hours.battery`; verify plant-specific duration/storage-energy handling before relying on BESS duration. |
| CSP | Partly feasible; requires explicit validation | PyPSA-Earth has `renewable.csp`, `profile_csp.nc`, and advanced CSP handling in `add_extra_components.py`, but custom CSP rows must normalize to carrier `csp`. Do not assume `Fueltype = Solar` plus CSP-like technology works without a smoke test. |

### Milestone 5A: Smoke-Test Custom Powerplant Normalization

Before building the full fleet, create a tiny `data/custom_powerplants.csv` fixture with one row per difficult carrier:

```text
coal
nuclear
OCGT
CCGT
oil/diesel peaker
onwind
solar PV
run-of-river hydro
reservoir hydro
pumped storage
battery
CSP
```

Run the workflow only through:

```text
resources/<run>/powerplants.csv
networks/<run>/elec.nc
```

Check:

```text
resources/<run>/powerplants.csv has non-null bus assignments
load_powerplants() normalizes carriers as expected
wind rows become carrier onwind in the network
PV rows become carrier solar in the network
hydro rows become ror/PHS/hydro as expected
CSP rows become carrier csp, or else the CSP mapping needs a local fix
no unintended IRENA renewable capacity is added during fixed validation
no extendable capacity appears in the fixed 2023 network unless explicitly intended
```

This smoke test is the feasibility gate for using `custom_powerplants: replace` as the authoritative 2023 plant inventory.

### Milestone 6: Add Explicit CSP Handling

PyPSA-Earth has a `renewable.csp` configuration block, but `csp` is not currently included in the default `electricity.renewable_carriers` list.

For South Africa, CSP must be explicit:

```text
CSP installed capacity = 500 MW in 2023
CSP generation = 1.375 TWh in 2023
```

Preferred route:

1. Add `csp` to the South Africa-specific `electricity.renewable_carriers`.
2. Confirm the Snakefile includes `profile_csp.nc` as an input to `add_electricity`.
3. Confirm `build_renewable_profiles` can build `profile_csp.nc` from the 2023 cutout.
4. Confirm `add_electricity.py` treats `csp` correctly instead of collapsing it into PV.
5. Represent the six 2023 CSP plants as 500 MW total, excluding Redstone.
6. Preserve storage-hour metadata from PyPSA-RSA for later explicit CSP storage modeling.

Modeling options:

| Option | Treatment | Tradeoff |
|---|---|---|
| Simplified CSP generator | Fixed `p_nom`, hourly `p_max_pu` from atlite CSP profile, no explicit thermal storage | Faster first validation. |
| CSP with storage | Model `solar_csp` with storage hours from PyPSA-RSA | More work and more realistic. |

Recommendation: for the first 2023 validation baseline, use the PyPSA-Earth/atlite CSP route if it works with limited code changes. If it fails, use a documented temporary simplified CSP profile as an isolated fallback. Do not use observed Eskom CSP generation directly as unconstrained availability except for a diagnostic run.

### Milestone 7: Calibrate Fixed-Capacity Dispatch

Build a fixed-capacity 2023 model:

```text
no new capacity expansion
hourly 2023 demand
existing fleet fixed
renewable profiles from the 2023 atlite cutout
renewable generation validated against Eskom
load shedding variable enabled with high cost
imports/exports represented or documented
```

Validate annual and hourly:

```text
RSA Contracted Demand
Thermal Generation
Nuclear Generation
Eskom OCGT Generation
Dispatchable IPP OCGT
Hydro Water Generation
Pumped Water Generation
Pumped Water SCO Pumping
Wind
PV
CSP
Total RE
Manual Load_Reduction(MLR)
ILS Usage
IOS Excl ILS and MLR
International Imports
International Exports
```

Do not proceed to expansion until the fixed model reproduces major 2023 quantities within documented tolerances.

Renewable validation order:

1. Check reconciled installed capacities against Eskom 2023 targets.
2. Check atlite full-load hours by carrier and region.
3. Compare modeled wind/PV/CSP generation against Eskom annual totals.
4. Compare hourly and monthly shape against Eskom generation and PyPSA-RSA `eskom_pu_profiles.csv`.
5. Diagnose gaps as capacity error, profile/weather bias, curtailment/grid constraint, outage, or commissioning-timing issue.
6. Apply correction factors only when the bias is persistent, physical, and documented.

### Milestone 8: Add Availability And Outage Constraints

Start simple:

1. Use Eskom aggregate `Total PCLF`, `Total UCLF`, and `Total OCLF` to derive a national thermal availability limit.
2. Compare with PyPSA-RSA station EAF assumptions in `plant_availability.xlsx`.
3. Move toward station-level `p_max_pu` only if needed.

Use PyPSA-RSA outage logic as a template:

```text
planned outage profile
unplanned outage profile
annual EAF target
scale unplanned outages to hit annual EAF while preserving planned outage shape
```

First target:

```text
2023 coal EAF / available capacity consistent with Eskom dispatch and load reduction
```

### Milestone 9: Compare Spatial And Transmission Assumptions

Before expansion, assess whether PyPSA-Earth's South Africa network is credible against PyPSA-RSA/Eskom geography.

Compare:

- PyPSA-Earth buses/clusters.
- PyPSA-RSA 10/27/34/159 supply regions.
- Major generation locations.
- Major load centers.
- Inter-regional transfer capacities.
- OSM-derived grid vs Eskom/NTCSA shapefiles.

Potential tasks:

1. Export PyPSA-Earth ZA bus regions and overlay with PyPSA-RSA supply regions.
2. Assign custom plants to both PyPSA-Earth buses and PyPSA-RSA supply regions.
3. Compare installed capacity by region.
4. Compare transmission corridors and bottlenecks.
5. Compare PyPSA-Earth line `s_nom` and clustered corridor capacities against RSA `St_Clair_limit_n1`.
6. Compare OSM line coverage against Eskom existing line shapefiles for 220/275/400/765 kV corridors.
7. Compare OSM substations against Eskom/MTS substation shapefiles.

Recommended grid audit outputs:

```text
data/za_audit/za_rsa_supply_regions.geojson
data/za_audit/za_rsa_existing_lines_220kv_plus.geojson
data/za_audit/za_rsa_planned_tdp_lines.geojson
data/za_audit/za_rsa_interregional_transfer_limits.csv
data/za_audit/za_rsa_supply_area_connection_limits.csv
data/za_audit/za_rsa_mts_hosting_limits.csv
data/za_audit/za_pypsa_earth_osm_grid_summary.csv
data/za_audit/za_grid_reconciliation.csv
doc/za_grid_reconciliation.md
```

The reconciliation table should include:

```text
corridor_id
rsa_region_0
rsa_region_1
voltage_classes
line_count_existing
line_count_tdp
rsa_thermal_limit_mw
rsa_sil_limit_mw
rsa_st_clair_limit_mw
rsa_st_clair_limit_n1_mw
earth_bus_or_cluster_0
earth_bus_or_cluster_1
earth_s_nom_mw
earth_s_nom_effective_mw
length_km_rsa
length_km_earth
connection_limit_light_load_mw
connection_limit_max_demand_mw
decision
decision_reason
```

Integration order:

1. Run PyPSA-Earth's default OSM network for South Africa and save grid statistics.
2. Build the RSA benchmark corridor table from `scripts/build_topology.py` logic.
3. Compare OSM line coverage and capacities to the RSA benchmark before changing the model.
4. If OSM is missing physical assets, convert RSA/Eskom shapefiles into PyPSA-Earth custom line/substation GeoJSON inputs.
5. If clustering distorts transfer capacity, create a local post-clustering capacity cap/override using RSA corridor limits.
6. Compare supply-area and MTS hosting limits to renewable build potentials before capacity expansion.
7. Use a pure RSA supply-region directed-link network only as an explicit alternative model variant, not the baseline.

### Milestone 10: Mine Renewable Siting For Expansion

After 2023 calibration, integrate South Africa-specific renewable eligibility:

- REDZ.
- Power corridors.
- EIA areas.
- SAPAD.
- SACAD.
- SKA exclusions.
- SA land cover.
- Global Wind Atlas correction.

Implement using PyPSA-Earth renewable profile conventions. This is a later milestone, not part of the first fixed-capacity validation.

## Remaining Design Work

The plan above covers the main data-mining work from PyPSA-Earth, PyPSA-RSA, powerplantmatching, REIPPPP, Eskom validation data, atlite, and grid/transmission sources. The following items still need explicit design before implementation is complete.

### Costs, Fuels, Efficiencies, And Emissions

Dispatch validation will depend strongly on operating costs and efficiencies.

TODO:

- Define South Africa-specific fuel prices for coal, diesel, gas, nuclear, biomass, and imports if modeled.
- Decide whether to use PyPSA-Earth default technology-data costs, PyPSA-RSA cost assumptions, Eskom/IRP assumptions, or a documented hybrid.
- Validate OCGT/diesel marginal costs against 2023 dispatch behavior.
- Check heat rates and efficiencies for coal, OCGT, CCGT, Sasol gas, Sasol coal, and nuclear.
- Define emissions factors for coal, diesel, gas, biomass, and Sasol carriers.
- Decide whether to use RSA config externality prices only for later policy scenarios.
- Verify the load-shedding cost / COUE assumption. PyPSA-RSA uses `COUE: 100000` with a comment equivalent to R100/kWh; units and currency must be verified before use.

Candidate files/sources:

```text
PyPSA-Earth:
data/costs.csv
resources/<run>/costs_<year>_elec.csv
config.default.yaml

PyPSA-RSA:
config.yaml
scenarios/*/sub_scenarios/extendable_technologies.xlsx
scenarios/*/sub_scenarios/operational_constraints.xlsx
```

### Final Carrier Taxonomy

The following carriers do not map cleanly to upstream PyPSA-Earth defaults and must be finalized before the full custom fleet is built:

```text
ocgt_diesel
ocgt_avf
ocgt_gas
sasol_gas
sasol_coal
rmippp
hydro_import
bioenergy
battery
solar_csp / csp
embedded or rooftop PV
```

For each carrier, decide:

```text
PyPSA component type: Generator, StorageUnit, Store/Link, Link
Fueltype / Technology tags in custom_powerplants.csv
cost row required
emissions factor
availability treatment
validation target in Eskom 2023 data
```

Add missing carrier colors/nice names only in a local South Africa config overlay. Avoid local carriers unless they materially improve validation or later expansion logic.

### System Boundary

Before validation, define exactly what the modeled system represents:

```text
Eskom system only
South African national power system
South African system including imports/exports
South African system excluding embedded/behind-the-meter PV
```

Clarify how Eskom `RSA Contracted Demand`, `Residual Demand`, `PV`, `Wind`, `CSP`, `Other RE`, imports, exports, `MLR`, `ILS`, and `IOS` map into PyPSA components and validation targets.

Decide whether international imports/exports are:

```text
fixed generators/loads
links to external buses
time-series constraints
excluded with documented residual adjustment
```

Decide whether embedded/rooftop PV is:

```text
explicit generator
negative load
excluded from first baseline
included only in expansion
```

This is a prerequisite for meaningful validation against Eskom hourly data.

### Validation Metrics And Tolerances

Define annual tolerance bands for:

```text
RSA Contracted Demand
Thermal Generation
Nuclear Generation
Eskom OCGT Generation
Dispatchable IPP OCGT
Hydro Water Generation
Pumped Water Generation
Pumped Water SCO Pumping
Wind
PV
CSP
Total RE
MLR + ILS + IOS / modeled unserved energy
Imports
Exports
```

Define hourly/monthly metrics:

```text
monthly energy error by carrier
hourly RMSE / MAE
correlation by renewable carrier
peak demand error
peak residual demand error
load-shedding hours and energy
curtailment hours and energy
capacity factor by carrier
```

Use a staged validation standard:

```text
Stage 1: annual energy and capacity totals
Stage 2: monthly renewable and demand shape
Stage 3: hourly dispatch and load shedding
Stage 4: regional congestion / transmission plausibility
```

### Reproducible South Africa Config Overlays

Define local config overlays so South Africa assumptions do not leak into upstream defaults, for example:

```text
config/za/za_2023_fixed_validation.yaml
config/za/za_2023_grid_audit.yaml
config/za/za_expansion_base.yaml
```

Each overlay should specify:

```text
countries: [ZA]
snapshots for 2023
atlite cutout name
custom_powerplants mode
renewable carriers, including whether csp is enabled
extendable carriers disabled/enabled
solver and options
cluster count / spatial mode
grid options
validation output paths
```

Add data provenance outputs:

```text
data/za_audit/input_file_manifest.csv
data/za_audit/source_hashes.csv
doc/za_data_provenance.md
```

### Dispatch Constraints Beyond Availability

Decide when to add:

```text
ramp limits
minimum stable levels
linearized unit commitment
coal minimum generation
nuclear must-run assumptions
OCGT annual fuel/energy caps
OCGT weekly capacity-factor caps
Sasol annual energy caps
RMIPPPP minimum capacity factor
operating reserve constraints
overgeneration / curtailment slack
```

Start with the minimum constraints needed for a feasible and interpretable fixed 2023 validation run. Mine PyPSA-RSA `operational_constraints.xlsx`, `plant_availability.xlsx`, and `config.yaml`, but implement constraints locally and incrementally.

### Validation-To-Expansion Transition

Define how the calibrated 2023 model becomes a brownfield expansion model:

- Brownfield starting fleet and retirement assumptions.
- Whether TDP planned lines enter automatically by build year or only under expansion scenarios.
- Whether transmission expansion is allowed and under what corridor constraints.
- How REDZ, power corridors, EIA areas, SAPAD/SACAD, SKA exclusions, and MTS hosting limits constrain renewable expansion.
- Whether future contracted projects are fixed exogenous builds, candidate builds, excluded, or scenario-dependent.
- How 2023 calibration parameters carry forward into future years without overfitting the expansion model to one historical year.

## Recommended Priority Order

1. Clean Eskom 2023 validation data.
2. Build or smoke-test a South Africa 2023 atlite cutout.
3. Generate atlite renewable profiles for 2023 and validate that profile files are usable.
4. Generate full South Africa `powerplantmatching` audit including wind, PV, CSP.
5. Extract 2023-active PyPSA-RSA plant candidates.
6. Reconcile plant inventory and write `custom_powerplants.csv`.
7. Smoke-test custom powerplant normalization through `build_powerplants` and `add_electricity`.
8. Add explicit CSP handling through the PyPSA-Earth/atlite route where feasible.
9. Build fixed-capacity 2023 PyPSA-Earth dispatch model.
10. Validate generation, demand, load reduction, and renewable output.
11. Add outage/availability constraints.
12. Compare and improve spatial/load/grid representation.
13. Only then start capacity expansion.

## Open Questions

1. What exact PyPSA-Earth carrier taxonomy should be used for South Africa diesel OCGT, gas OCGT, Sasol gas, Sasol coal, RMIPPPP, CSP, hydro imports, and batteries?
2. Should embedded/rooftop PV be modeled as generation, negative load, or excluded from the first Eskom-boundary baseline?
3. Should international imports/exports be modeled as links, fixed time series, or excluded with demand adjustment?
4. Should the first baseline be single-node, PyPSA-Earth clustered, or aligned to PyPSA-RSA 10-supply regions?
5. Can PyPSA-Earth's `build_powerplants.py` be extended with an optional `include_wind_solar` flag, or should the full renewable-inclusive PPM extraction remain an audit-only script?
6. What is the cleanest PyPSA-Earth-native way to model CSP in the first baseline?
7. Should station-level coal availability be applied at plant level or as an aggregate thermal availability constraint for the first smoke model?
8. What correction factors, if any, are justified after comparing 2023 atlite wind/PV/CSP profiles to Eskom observed generation?
9. Should rooftop/embedded PV be represented separately from utility PV when validating against Eskom `PV` and `RSA Contracted Demand`?
