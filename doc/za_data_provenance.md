# South Africa Baseline Data Provenance

**Created:** 2026-05-08 11:22 CEST  
**Workstream:** ZA Baseline Calibration  
**Modules:** 00 Governance and Scope; 01 Repo Bootstrap and Config; 02 Eskom Validation Data Pipeline; 03 Weather Cutout And Profiles; 04 Source Data Audits; 05 System Boundary And Carrier Taxonomy; 06 Demand Import Export Model Inputs

## Repository Inputs

| Input | Path | Branch | Commit | Status |
|---|---|---|---|---|
| PyPSA-Earth target | `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth` | `main` | `dacf37804e8d78f5a9a4b97d08958e22a747a839` | Present; pre-existing untracked `doc/za_pypsa_rsa_mining_plan.md` left untouched |
| PyPSA-RSA reference | `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-rsa` | `master` | `89872c1ea703af3d8a3f198706d1ab7958f50a5f` | Present; pre-existing untracked local files left untouched |

The upstream PyPSA-Earth plan pin `e18bea540e0742ea978e00338df143fa01e78553` is an ancestor of the current PyPSA-Earth HEAD. No upstream rebase decision was required for module 01.

## Runtime Environment

The usable environment is `/opt/anaconda3/envs/pypsa-earth` managed by conda at `/opt/anaconda3/bin/conda`.

| Package | Version |
|---|---|
| Python | 3.11.13 |
| PyPSA | 0.30.3 |
| atlite | 0.4.1 |
| powerplantmatching | 0.8.0 |
| linopy | 0.5.5 |
| gurobipy | 12.0.3 |
| numpy | 1.26.4 |
| pandas | 2.3.1 |
| geopandas | 1.1.1 |
| snakemake | 7.32.4 |

Gurobi CLI is available at `/usr/local/bin/gurobi_cl` and reports version 13.0.0. The Python package in the locked environment is `gurobipy=12.0.3`.

## Weather and CDS Preflight

- CDS API configuration detected: `~/.cdsapirc` present.
- Prebuilt fixed-validation cutout detected: `cutouts/cutout-2023-era5.nc`.
- Cutout SHA256: `0c6b22fa6b8a0a469cc24460df2014fdb9c041035985dfb3b1aa7d6608e19076`.
- No live CDS retrieval or cutout rebuild was attempted during modules 00/01.

## Bootstrap Outputs

The first-pass manifest and source hashes are stored in:

- `data/za_audit/input_file_manifest.csv`
- `data/za_audit/source_hashes.csv`
- `data/za_audit/za_runtime_preflight.csv`

Later modules must append source path, source hash, extraction date, filter logic, and unresolved warnings for any external data they consume.

## Bootstrap Demand Setting

Module 01 keeps `load_options` on the existing PyPSA-Earth demand dataset (`ssp2-2.6`, `weather_year=2013`, `prediction_year=2030`) so dry-run DAG checks resolve before the South Africa-specific 2023 demand pipeline exists. Module 06 owns replacement with validated 2023 demand, import, export, load-allocation, and bus-attachment inputs.

## Eskom 2023 Validation Data

Module 02 stages the raw Eskom 2023 CSV at `data/za_audit/raw/eskom_data_2023_full.csv`.

| Artifact | Path | SHA256 | Notes |
|---|---|---|---|
| Raw Eskom CSV | `data/za_audit/raw/eskom_data_2023_full.csv` | `8c2220f114ba60d5ae823f5116368cc2a664ec625d70f4d52bdf26caffc29869` | 10,272 raw rows; 10,263 rows require `Total UCLF+OCLF` comma-decimal repair |
| Clean hourly validation data | `data/za_validation/eskom_2023_hourly_clean.csv` | `bab73ee6b46d4c147d64b9e0b8d88a01eff2d49229e4688729b180aa1ca4221a` | 8,760 hourly rows from 2023-01-01 00:00 to 2023-12-31 23:00 |
| Annual validation targets | `data/za_validation/eskom_2023_targets_by_carrier.csv` | `dc0bba6c28d5dc0f1fb4004eee3a476f6c371f0bfe13316d5ec6c7204e508ec3` | Energy targets, capacity anchors, source labels, and warning statuses |
| Parser report | `data/za_audit/eskom_2023_parser_report.csv` | `90b65f372759f000f2e04e287c8c492644b252eff2feccfcf2b0c39df66c7bfd` | Parser accounting diagnostics and raw column-header printout |

The resolved residual-demand accounting identity is `Residual Demand = Dispatchable Generation + Manual Load_Reduction(MLR) + ILS Usage + IOS Excl ILS and MLR`. The raw Eskom data also leaves a source discrepancy of `0.444123395 TWh` for `RSA Contracted Demand - Residual Demand - Total RE`; this is recorded as a warning rather than adjusted away. Eskom Gas Generation totals `0.00711849 TWh` in the 2023 raw data despite the preliminary plan note that zero was expected; the raw value is retained and flagged as nonzero.

## Weather Cutout And Renewable Profiles

Module 03 reuses the existing 2023 ERA5 cutout because the file hash, module metadata, 0.3-degree resolution, and 8,760 hourly 2023 coverage match the module 01 provenance record. No full CDS rebuild was attempted.

| Artifact | Path | SHA256 | Notes |
|---|---|---|---|
| ERA5 cutout | `cutouts/cutout-2023-era5.nc` | `0c6b22fa6b8a0a469cc24460df2014fdb9c041035985dfb3b1aa7d6608e19076` | 1.3 GB; git-ignored; 2023-01-01 00:00 to 2023-12-31 23:00 |
| Solar profile | `resources/za_2023_fixed_validation/renewable_profiles/profile_solar.nc` | `ae900f83a9358fa5ee10f74612da7c2806d144637655718671651dda9090535e` | 8,760 hours; 1,291 buses; git-ignored large output |
| Onwind profile | `resources/za_2023_fixed_validation/renewable_profiles/profile_onwind.nc` | `2a1ae2591ad757e71eb08e8315644787fb95814c57add311e0c1b3c0a0b9ed91` | 8,760 hours; 1,291 buses; git-ignored large output |
| Hydro profile | `resources/za_2023_fixed_validation/renewable_profiles/profile_hydro.nc` | `25cf8e94bddf03c67302ebe049ed45c2b540814f7c1c7025f849e2847c6e8057` | Upstream output exists but is empty because pre-module-08 powerplant matching found no known ZA plants |
| CSP profile | `resources/za_2023_fixed_validation/renewable_profiles/profile_csp.nc` | `2051d6c6720542eb004374cdfa09a18b7187f1dabf23d9f80d43aeb61d0bc310` | Native atlite CSP profile; not merged with PV; git-ignored large output |
| Gate A validation | `data/za_audit/za_atlite_renewable_profile_validation.csv` | `c7abdadfbb8a6b2892942e93077c5acecee6bb792b354c43412be372b2beca16` | 33 checks; 29 pass and 4 hydro warnings |
| Technical potential | `data/za_audit/za_atlite_technical_potential.csv` | `f4fb24588237d17f73c33164c4ad413ff80ece14da7b47a634e0a38a22242f05` | Technical-potential and full-load-hour diagnostics only |
| Markdown report | `doc/za_renewable_profile_validation.md` | `afa795c322c6e8408481fced4842e47891eea1b209df4b61a509106faf014120` | Documents cutout reuse, GEGIS check, technical potential, and hydro warnings |
| Notebook | `notebooks/za_validation/03_profiles/profile_validation.ipynb` | `f725da18f8d198cd1979efb6d92d6bfe8eeb8a14102abfd12aaebcf5cdef5e95` | Presentation notebook for module 03 |
| Notebook HTML | `doc/za_validation/figures/03_profiles/profile_validation.html` | `06b01887b608d937dd32b786aedd4e9cbfce03885562e12651bc80b9351d3505` | Executed static HTML export |

The ZA overlay sets `atlite.default: cutout-2023-era5`, `enable.retrieve_cutout: false`, and `enable.build_cutout: false`. The `csp` carrier remains separate from `solar`; PyPSA-Earth resolves the `csp` cutout to `cutout-2023-era5` and uses the default `csp_model: advanced`. The GEGIS demand-path preflight confirms `build_demand_profiles.py:get_load_paths_gegis` accepts `weather_year: 2023_custom`, resolving to `data/ssp2-2.6/2030/era5_2023_custom/Africa.csv`.

Technical-potential diagnostics are intentionally not correction factors. Module 03 applies no availability scaling and no resource-mask changes. Hydro remains a warning for later modules because the current upstream pre-fleet-reconciliation powerplant data does not provide ZA hydro plants; module 08 owns fleet reconciliation.

## Source Data Audits (Module 04)

Module 04 builds the PyPSA-RSA + South Africa source registry plus 22 audit
artefacts under `data/za_audit/`. PyPSA-RSA is read-only; the pinned commit
`89872c1ea703af3d8a3f198706d1ab7958f50a5f` is matched by both the local HEAD
and `origin/main`, so no no-silent-rebase review was required. Powerplantmatching
runs the upstream `from_url=False, update=True` matching pipeline restricted to
South Africa, mirroring `scripts/build_powerplants.py`, and is allowed to fail
gracefully. The supply-region layer resolution table independently identifies
the canonical PyPSA-RSA 1/10/27/34/159 layers. The existing-line GeoJSON
filters `DESIGN_VOL >= 220 kV`. Future assets (Redstone CSP, 2024–2027 BESS,
fixed-tech rows with `Commissioning Date > 2023`) remain in the candidate
files but with `included_2023 = false`.

| Artifact | Path | SHA256 |
|---|---|---|
| Source registry | `data/za_audit/pypsa_rsa_source_registry.csv` | `a4e0165e360d19c52f371bcfb1561f1aa7b7dc9a6b9dab9df0822ec3e147d94f` |
| Discovery sweep (>=10 KB) | `data/za_audit/pypsa_rsa_discovery_sweep.csv` | `31fc7e86be567b8524eb3bbc21bbcb250870ec75ffd8ef2e9fac702bf92cb154` |
| Powerplantmatching ZA full | `data/za_audit/powerplants_pm_za_full.csv` | `eaa77c38f72f6f527db68891877d77a4b72312482c60844b0c06dc80aaf54d57` |
| Powerplantmatching ZA audit subset | `data/za_audit/powerplants_pm_za_audit.csv` | `772fa8bb889a3cdd197c0350f079485f024df2f747e8a078da86c1f792cd0f33` |
| Scenario workbook inventory | `data/za_audit/pypsa_rsa_scenario_workbook_inventory.csv` | `c70b12cb6e98b580afd7692cac9635028fa96cb7b282eafa60c832cdde85ee17` |
| Fixed technologies 2023 candidates | `data/za_audit/pypsa_rsa_fixed_technologies_2023_candidates.csv` | `81c19dce89803c375e1616323ffd86c999c87a085e3a98b3ff34de74ec8e5d03` |
| REIPPPP solar 2023 candidates | `data/za_audit/reipppp_solar_2023_candidates.csv` | `9833b61ab47a8cc58aa3202b4b83af96b67bb371c7b7c479540d4a90a2c4c2c3` |
| REIPPPP wind 2023 candidates | `data/za_audit/reipppp_wind_2023_candidates.csv` | `7ba1fdb00b89234019c53f6fb7297ca5fb09f8ed532747619e78f826b9c919d6` |
| Plant availability audit | `data/za_audit/pypsa_rsa_availability_audit.csv` | `2b9695d752d669be03394a59661a96ce7e8a70447477eda6f3d33298c50b59de` |
| Operational constraints audit | `data/za_audit/pypsa_rsa_operational_constraints_audit.csv` | `05e4497d7318ca3d01437d5f01244cc18b55233f54d489fc102b4b8afa235948` |
| Reserve margin audit | `data/za_audit/pypsa_rsa_reserve_margin_audit.csv` | `e37b1299e3894fbb6dad95360903a1213d3bdc4bdb5ea2871464598e006c4216` |
| Eskom pu profiles audit | `data/za_audit/pypsa_rsa_eskom_pu_profiles_audit.csv` | `434cf2e5592d43cf9240ab152fd20ea3cd596dab3211d55987ce9824dfcd0a83` |
| Cost / fuel / emissions audit | `data/za_audit/pypsa_rsa_cost_fuel_emissions_audit.csv` | `42648462daa9c6bec30ac41ce5886132b0321d355d21917aa230dfb23e311e03` |
| Load weight audit (GVA/POP + Mesozones) | `data/za_audit/pypsa_rsa_load_weight_audit.csv` | `062ebea9897af3499735cf0286ed1c3fb4e0421541006594af67303f319c3e8c` |
| External bundle inventory | `data/za_audit/pypsa_rsa_external_bundle_inventory.csv` | `610b45c3dfeb60d1ae8b511b8628fcf7e79fcdd2817d1cb7d9de9cc868f62da4` |
| Supply regions GeoJSON (27-region) | `data/za_audit/za_rsa_supply_regions.geojson` | `c78b161c06ff3bc67a0cbc0b6275ca6f8788411cb3bdfe91e51c53fcdee63de9` |
| Supply-region layer resolution check (1/10/27/34/159) | `data/za_audit/za_rsa_supply_region_layer_resolution.csv` | `6c5bd083a658fd84aaae4ed1fad78ff76ab8359bb18fad97ac3b96689842f28b` |
| Existing lines GeoJSON (>=220 kV) | `data/za_audit/za_rsa_existing_lines_220kv_plus.geojson` | `4fb775abd47ed5e94bda1de4c4070d38a3f7bbe1f2c44db0a1e09834cbe58eaa` |
| Planned TDP lines GeoJSON | `data/za_audit/za_rsa_planned_tdp_lines.geojson` | `1fcd8a607bad7790b264d7882ef103e7e8a096e19f142f3c85cd0c2b81d74375` |
| Supply-area connection limits | `data/za_audit/za_rsa_supply_area_connection_limits.csv` | `a5f1ec2c36bbf26aecb51cdec900c2bc87cd2bc687974c9ed40a9c48a41fdc00` |
| MTS hosting limits | `data/za_audit/za_rsa_mts_hosting_limits.csv` | `19d94b53a5fdc0b31282271607f6f8acd0035849d4de5a73d34efafc69784c3c` |
| Transmission expansion audit | `data/za_audit/pypsa_rsa_transmission_expansion_audit.csv` | `15cc37299e73f4d4a353f847281857d24a83b13408ba6b7a3de3780dc193fbbc` |
| Resource siting audit | `data/za_audit/pypsa_rsa_resource_siting_audit.csv` | `537e57a9a7280bd76fdbde3027b3b90398c3bfca662e2a5f38ec0e9cc2bccf74` |

The supply-region layer resolution table confirms canonical 1/10/27/34/159
layers are present in `data/bundle/supply_regions/rsa_supply_regions.gpkg`,
`rsa_supply_regions2.gpkg`, and the GCCA 2025 GIS bundle. The 27-region layer
is exported as `za_rsa_supply_regions.geojson` for downstream consumption by
modules 06 (load allocation context only) and 09 (grid build).

## System Boundary And Carrier Taxonomy (Module 05)

PyPSA-RSA pin re-confirmed: `89872c1ea703af3d8a3f198706d1ab7958f50a5f`
(HEAD = origin/main). PyPSA-Earth HEAD at module entry:
`f5422d8f384a86117bbc18b3048784e265808669`.

Module 05 is doc/config/spec — no fleet/cost/grid override is written. The
configuration file `configs/za/za_2023_fixed_validation.yaml` was extended
in-place with `za_system_boundary`, `za_local_carriers`, and locked
`electricity.{conventional,renewable,extendable}_carriers`.

| artifact | sha256 |
|---|---|
| `doc/za_carrier_taxonomy.md` | `d38790645475bdb9c1f246e5978701adf74349fc689cdaa15e50895a5d4c6418` |
| `data/za_audit/za_carrier_taxonomy.csv` | `6df50b77665f79f7b740931030f895ca5368219176aaed3e7a81f145a7abfb1a` |
| `data/za_audit/za_carrier_taxonomy_crosscheck.csv` | `b4e5253f5d7ebee62af1ba60a8699844e0e274e60a1dd45a3feb758603651b79` |
| `scripts/build_za_carrier_taxonomy.py` | `91eab10d0560d45575d3f948d1c84556ce7af710692194ac8cf56fda2969ed91` |
| `scripts/za_validation/smoke_carrier_taxonomy.py` | `63f354b9285ef82b6ba2cb8f886380c4aee47627b0ecffcee7ed7bcded15e109` |
| `notebooks/za_validation/05_carrier_taxonomy/carrier_taxonomy_overview.ipynb` | `2eeb3bb49a0030a9aa62b1ec3358223dad0461ea2466f9e3d7f5b77889e44d8a` |
| `doc/za_validation/figures/05_carrier_taxonomy/carrier_taxonomy_overview.html` | `5cb7a611bcc508a9d8a5ce681d58c09455d8e87a06f0cebaf411741de9acacf1` |
| `doc/za_validation/figures/05_carrier_taxonomy/mw_by_v1_carrier.png` | `aa045dc7b1a1189cad9eade47673f42f580b8bd700d89adbdcaabe8e91c39e44` |

The crosscheck CSV resolves 15 of 17 RSA carriers from the module 04
fixed-tech audit; one row is `excluded_by_boundary` (`solar_pv_rooftop`,
embedded PV per `za_system_boundary.embedded_pv_treatment`) and one is
`pending_module_08` (`rmippp` — Risk Mitigation IPP procurement-program
label, not a carrier; module 08 will reconcile per-plant carrier during
fleet build).

The CSP/solar acceptance smoke test
(`scripts/za_validation/smoke_carrier_taxonomy.py`) is shipped but deferred
to fire when module 10's `apply_za_local_carriers` hook produces a network.

## Demand Import Export Model Inputs (Module 06)

Module 06 replaces the bootstrap demand route with the validated Eskom 2023
contracted-demand profile. The ZA overlay now sets
`load_options.weather_year: 2023_custom` and keeps
`load_options.prediction_year: 2030`, so upstream
`build_demand_profiles.py:get_load_paths_gegis` resolves to
`data/ssp2-2.6/2030/era5_2023_custom/Africa.csv` once the generated CSV exists.

Demand uses Eskom `RSA Contracted Demand` without subtracting load shedding.
Gross `International Imports` and gross `International Exports` remain separate:
imports are positive supply injections and exports are positive withdrawals.
`Other RE` is not folded into demand; it is prepared as a curtailable local
`other_re` generator profile for module 10, with `p_min_pu = 0` and
`p_max_pu = Other RE / p_nom`.

Candidate layer `1`, `10`, and `34` demand weights use PyPSA-Earth-style
GADM GDP/population allocation (`0.6 * gdp + 0.4 * pop`). PyPSA-RSA
`GVA_2016`/`POP_2016` remains diagnostic-only. The actual PyPSA-RSA 10- and
34-region layers do not carry regional `GVA_2016`/`POP_2016` columns, so the
diagnostic comparison records one available national row and 44 unavailable
candidate-region rows rather than substituting PyPSA-RSA weights. Conservative
proxy attachments are used for non-demand series: imports attach to `ZA`,
`Gauteng`, and `Pretoria`; exports and `Other RE` use demand-weight proxies
until module 09 resolves final bus IDs.

| Artifact | Path | SHA256 |
|---|---|---|
| Builder script | `scripts/build_za_demand_import_export_inputs.py` | `0f63bdc30a46d6192b8cf49ab6457cdb3e3a4a47cd76685b4f7d427e0cfe19be` |
| Demand profile | `data/za_validation/za_2023_demand_profile.csv` | `536ec5659b70723aa9bb9b49aa196085435a11ae9c4bd79032247b3334aca847` |
| GEGIS Africa demand CSV | `data/ssp2-2.6/2030/era5_2023_custom/Africa.csv` | `9de919b6229de94ad2dbea91fbec9a41dae397c31dc4b5def608538af4fb9a1f` |
| Import/export time series | `data/za_validation/za_2023_import_export_timeseries.csv` | `33f7ee12ca4e076cdba8ea482ffb64b3235ab3caa56e961cfb23bb42d5758579` |
| Other RE time series | `data/za_validation/za_2023_other_re_timeseries.csv` | `e4112c5b16437c83dad722071a965eee413f857842c8fbc56178d66b91aed24a` |
| Load allocation weights | `data/za_audit/za_2023_load_allocation_weights.csv` | `d1b0060e25d065a1ea1d96e9561e50db1169b5f1df5bcba1065f756a80b886b3` |
| PyPSA-RSA GVA/POP comparison | `data/za_audit/pypsa_rsa_gva_pop_load_weight_comparison.csv` | `552e663abcdf72d96df75a3576ebcd06f62e21ebe745b7d4ecf3605e46797dcc` |
| Import/export attachment | `data/za_audit/za_2023_import_export_attachment.csv` | `9066189c6adfbbd735870148d71b96d5dd4f1e267b9657870cd094ed28c2107a` |
| Other RE attachment | `data/za_audit/za_2023_other_re_attachment.csv` | `fef2ad3e86122166527b87cc3a13839b4f9d60e4d7d384f6105135e574c8e379` |
| Markdown report | `doc/za_demand_import_export_model_inputs.md` | `d3bd22fa52ff330cbaea165733a55b382fe6da5eac6caabbf4beaab6a8c07a72` |
| Notebook | `notebooks/za_validation/06_demand_import_export/demand_import_export_overview.ipynb` | `c61c6f1ed1b5cf8d471fcd65fd9783f8813598907c5e5af5726aa84d6310865e` |
| Notebook HTML | `doc/za_validation/figures/06_demand_import_export/demand_import_export_overview.html` | `d3171aba589232465761c063ba5562e7292b26370dbcdb197272b1cda5cfc157` |

## Module 07 — Costs, Fuels, Efficiencies, and CoUE — 2026-05-11

| Artifact | Path | SHA256 |
|---|---|---|
| Builder script | `scripts/build_za_costs_fuels_efficiencies.py` | `a4c95c342f24ee5eb6ef9948ac3e4679987b2c84b8a66fb0ff020e1549a3ed95` |
| `za_costs` package — `__init__.py` | `scripts/za_costs/__init__.py` | `203ef1888f05b960e57bdb633120bf596925577189a4bf0b279406e647e017c0` |
| `za_costs` package — `fxrate.py` | `scripts/za_costs/fxrate.py` | `15f8d7069e7c8fd93845abf53f421ec01db1a982f9e2c639239040a5fbfae774` |
| `za_costs` package — `currency.py` | `scripts/za_costs/currency.py` | `99e789361c0601ad31d8ddd8b0abf8e6a8c9dd99440349cf2959070d4032a424` |
| `za_costs` package — `audit_builder.py` | `scripts/za_costs/audit_builder.py` | `d1d10b27df417a80879368d30d1d560af835d159196fdfa7cbbd69e3da0e7816` |
| `za_costs` package — `local_rows.py` | `scripts/za_costs/local_rows.py` | `952aee049ca247c2f534cae57cfef4d6b492f7f83c052ccf55dcac757a7086a5` |
| Cost/fuel/emissions audit CSV | `data/za_audit/za_costs_fuels_efficiencies_audit.csv` | `91c649984e3f605305bfb17d45a4a7beaad0357b5b9c8ecb05cd1be878ae54e7` |
| Local-carrier cost rows | `data/za_audit/za_local_carrier_cost_rows.csv` | `c5e3c5e74021175776851d1d68b9368232fa3f7cc2d82934132126f9d410b4da` |
| Frozen 2023 EUR/ZAR rate | `data/za_audit/za_eur_zar_fxrate_2023.csv` | `9d6fe1ec0d5d5f16ac2507214ccb45a5db6359a6c3b54ff76199c3b5a3a79c91` |
| Policy CoLS reference values | `data/za_audit/za_cols_reference_values.csv` | `3024a998f4b6292a83fd8debdaa936f06d01a4e900e4361463732dc75e2cc75d` |
| Canonical doc | `doc/za_costs_fuels_efficiencies_and_coUE.md` | `257328fd70e50b3e8dd21bd3768c1dad19992a7b5775710b43f8370a3e9e707f` |
| Notebook | `notebooks/za_validation/07_costs_fuels/cost_fuel_overview.ipynb` | `beb7be393ce651119fe642e381fc1a2ed49d6443c3cf8bfd5fa237502e48e88a` |
| Notebook HTML | `doc/za_validation/figures/07_costs_fuels/cost_fuel_overview.html` | `f0a586c40721c63104c763d20336fb97a8e5d6c13202dda1a29185ad1c0a7ec4` |

### Module 04 audit consumed by Module 07

- `data/za_audit/pypsa_rsa_cost_fuel_emissions_audit.csv` (SHA256
  `42648462daa9c6bec30ac41ce5886132b0321d355d21917aa230dfb23e311e03`)
- `data/costs_2030.csv` (SHA256
  `8a412a1d32c1f43fba1aa46295a67eab13345758eb5f5bffef415ca743b4d7b7`)

### External source

- ECB historical EUR FX reference rates archive
  `eurofxref-hist.zip`, mirrored at
  `https://raw.githubusercontent.com/alexprengere/currencyconverter/master/currency_converter/eurofxref-hist.zip`,
  archive SHA256
  `9dea72fbf8116f2d76106d78f9875f2aa8157f39ed3cf728a1602f2a5445d199`,
  member `eurofxref-hist.csv`. Frozen 2023 row used: date `2023-12-29`,
  EUR/ZAR `20.3477`. PyPSA-RSA base-year (2018) average rate used for
  ZAR → EUR conversion of audited values: `15.6186`.

PyPSA-Earth HEAD at Module 07 completion: `2d76ba3569689817dc0c8bda99719670ec292f08`.
PyPSA-RSA HEAD: `89872c1ea703af3d8a3f198706d1ab7958f50a5f`.

## Module 08 — Fleet Reconciliation And Custom Powerplants

| Artifact | Path | SHA256 |
|---|---|---|
| Module 08 builder | `scripts/build_za_fleet_reconciliation.py` | `60dbdb4754a74c246603e244b4aad4e019b6c596e6038357e075499860cbb855` |
| `za_fleet` package — `__init__.py` | `scripts/za_fleet/__init__.py` | `c3dbea19c5abd17db2bb3f1ebabc79338356b416edae90eeefae811cd72aa910` |
| `za_fleet` package — `reconciliation.py` | `scripts/za_fleet/reconciliation.py` | `416c379579d244e0c342e859b395cf837504a1675fd389c502dc3fb83350b78c` |
| `za_fleet` package — `custom_powerplants.py` | `scripts/za_fleet/custom_powerplants.py` | `da7fbcb8a44701d55175114ce152fc4726640f1771ad4b79ef006290051ebbe7` |
| `za_fleet` package — `named_inventory.py` | `scripts/za_fleet/named_inventory.py` | `5f596a7168e4cc8d66a5856898e8f464d350a9c56b728fe76ce6d08f7133d88b` |
| `za_fleet` package — `eskom_anchors.py` | `scripts/za_fleet/eskom_anchors.py` | `4bc7ce338fce90a947d521180a016c073d6586707d976069890ce9102695d771` |
| `za_fleet` package — `normalization_smoke.py` | `scripts/za_fleet/normalization_smoke.py` | `2cb0d6da409c9826e6d0b0a4fcf4355ad4b15bda4e7f4a8954d9f889c972bd4f` |
| Frozen 2023 ZA fleet | `data/custom_powerplants.csv` | `082c5ef44c298993c3ccaa603346e49a39371e2edad305689894c880ba16d43e` |
| Reconciliation audit | `data/za_audit/za_powerplant_reconciliation.csv` | `ec6ee617280c599f11eee98b9c0755e2d89c004050adeb2fa69937535ddda238` |
| Named-plant inventory | `data/za_audit/za_named_plant_inventory.csv` | `74c67f7cef4cae03ded2cae4af63346648456acff06d17b28ac762fc8780c146` |
| Eskom 2023 capacity anchors | `data/za_audit/za_eskom_2023_capacity_anchors.csv` | `a78b905a1c88dfac1e70981f292d5cfca5543c5f425cfa64b8e50fc21cb6d93b` |
| PHS storage hours audit | `data/za_audit/za_phs_storage_hours.csv` | `c8aa6d0ea7c9159082c7b02af62db9a2fd6e61fd39c311be173dd409b46c712d` |
| Normalization smoke diff | `data/za_audit/za_powerplants_normalization_diff.csv` | `145fc7943e80a20ec7358b4d6d9b772a8f153e9ad941395ea65e3d7908f87b7d` |
| Canonical doc | `doc/za_powerplant_reconciliation.md` | `7717a21689b8b961249ce3f1ddc23e7745146c5a79b4dfa9acaf73e20617f66f` |
| Notebook | `notebooks/za_validation/08_fleet/fleet_overview.ipynb` | `678c015edcf711a53cec01fcf561f1a3d4a821ea15c23388a8435b4a1cd8e34c` |
| Notebook HTML | `doc/za_validation/figures/08_fleet/fleet_overview.html` | `4a921355446dad6b02b77d84fe142d29a8f03024852dc61374719ba7de93dde8` |

### Module 04 audits consumed by Module 08

- `data/za_audit/pypsa_rsa_fixed_technologies_2023_candidates.csv` (SHA256 `81c19dce89803c375e1616323ffd86c999c87a085e3a98b3ff34de74ec8e5d03`)
- `data/za_audit/reipppp_wind_2023_candidates.csv` (SHA256 `7ba1fdb00b89234019c53f6fb7297ca5fb09f8ed532747619e78f826b9c919d6`)
- `data/za_audit/reipppp_solar_2023_candidates.csv` (SHA256 `9833b61ab47a8cc58aa3202b4b83af96b67bb371c7b7c479540d4a90a2c4c2c3`)

### Module 02 raw input consumed by Module 08 anchor builder

- `data/za_audit/raw/eskom_data_2023_full.csv` (SHA256 `8c2220f114ba60d5ae823f5116368cc2a664ec625d70f4d52bdf26caffc29869`)

PyPSA-Earth HEAD at Module 08 completion: `2d76ba3569689817dc0c8bda99719670ec292f08`.
PyPSA-RSA HEAD: `89872c1ea703af3d8a3f198706d1ab7958f50a5f`.

## Module 13 — Validation Evidence Package

**Date:** 2026-05-13. Accepted solve: `EAF-OPC-CAP`. Network:
`results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc`.

| artifact_path | hash (sha256) | source | owner | extraction_date | unresolved_warnings |
|---|---|---|---|---|---|
| `scripts/za_validation/build_module13_validation.py` | `75a910826900f9a1aa29fcdceb0c2e9cac449d9a2aabb9a67ed230bd8b630479` | author (Module 13) | nylan-ramnauth, opus | 2026-05-13 | none |
| `data/za_validation/za_2023_validation_annual.csv` | `ab16fdb598a4e5b05d86a934acf365820e3fdca4ffa73a21d061085a7f0fcdba` | derived from `...EAF-OPC-CAP.nc` + `eskom_2023_targets_by_carrier.csv` | nylan-ramnauth | 2026-05-13 | per-carrier band fails — classified into `za_model_limitations.md` §1–8 |
| `data/za_validation/za_2023_validation_monthly.csv` | `c7d56222bb1a1163d886255a61298eab27630a4d38916b95e15730b14da63efe` | derived from `...EAF-OPC-CAP.nc` + `eskom_2023_hourly_clean.csv` | nylan-ramnauth | 2026-05-13 | VRE monthly levels fail (carrier-shape OK) |
| `data/za_validation/za_2023_validation_hourly_metrics.csv` | `cf065068a9f691b641cd5d993f457e92c60880f357f34b983b68f7b0bccca88a` | derived | nylan-ramnauth | 2026-05-13 | Stage 3 diagnostic only |
| `data/za_validation/za_2023_validation_capacity.csv` | `55e7b5ef382c3f6272a9e231067f473d2ee623087b1d41e5c0b7759f2aea12e9` | derived | nylan-ramnauth | 2026-05-13 | onwind -2.02% vs end-2023 anchor (matches §2 limitation) |
| `data/za_validation/za_2023_load_shedding_validation.csv` | `4dfdf016b15441b0fe5ae149cf46022b30bf3f2470225f8491b851b086d9a949` | derived | nylan-ramnauth | 2026-05-13 | LS -35.9%; downstream of §1+§2 per §7 |
| `data/za_validation/za_2023_validation_secondary_sources.csv` | `7d204b47bbbaec08e1cf210a088c6af703d106a0961136f6cac1a1a4566bdc54` | author + IRENA / OWID / IEA published anchors | nylan-ramnauth | 2026-05-13 | none |
| `data/za_validation/za_2023_irena_carrier_harmonization.csv` | `b3be9c1c538e67fcc78c274283d25aa6993389e1364c0229ac4ddeff5a6113bb` | author per spec §"Carrier harmonization table" | nylan-ramnauth | 2026-05-13 | none |
| `data/za_validation/za_2023_uncalibrated_vs_calibrated.csv` | `23d5e9572681a0e192c9d8ceb9714fcb5f5775c0e33037045c4991135f7c662f` | derived from baseline `...NoCO2-1H.nc` + accepted `...EAF-OPC-CAP.nc` | nylan-ramnauth | 2026-05-13 | PHS worsens under calibration; documented in §1 |
| `data/za_validation/za_2023_validation_plant_identity.csv` | `3b24c2a04164e261c68a9fb19aaff80d0e3951db9b62cf1bc168c8fdf6a5df6e` | derived from `za_named_plant_inventory.csv` + `custom_powerplants.csv` + network | nylan-ramnauth | 2026-05-13 | 27/27 operating pass; gate interpreted at station→bus mapping level due to elec_s_34 aggregation |
| `data/za_validation/za_2023_validation_cost_dual_frame.csv` | `104727d7197fc36046b100bc83fbaa23bd86b2d2d2f1a8af11aecc501d1718fa` | derived; CSIR + Nova CoLS from `za_cols_reference_values.csv`; EUR/ZAR from `za_eur_zar_fxrate_2023.csv` | nylan-ramnauth | 2026-05-13 | LS solver MC is 1000 EUR/MWh, not spec 100k; policy frame uses CSIR/Nova rates |
| `data/za_validation/za_2023_validation_manifest.json` | `c3dc190dd0f036da2ca928bc023afd0e5fedd41e93188ec33030e5d10e5d858e` | derived by builder | nylan-ramnauth | 2026-05-13 | none |
| `doc/za_2023_validation_report.md` | `aa5612029cd3e76cd52ba5efad6bf5f23df107aebc4beaaf08b347131f56870f` | author | nylan-ramnauth, opus | 2026-05-13 | none |
| `notebooks/za_validation/12_acceptance/before_after_comparison.ipynb` | `9a188cee6890308aa7dc0e0a4213a5d1d64555af4fd7a5d58a7c1e269c38da23` | author; executed with pypsa-earth kernel | nylan-ramnauth | 2026-05-13 | none |
| `doc/za_validation/figures/12_acceptance/before_after_comparison.html` | `32a453bf4d64894f8bea1d9da575adb15a5cab2b39cf797f836261375fd0f305` | nbconvert HTML export | nylan-ramnauth | 2026-05-13 | none |

PyPSA-Earth HEAD at Module 13 completion: `git rev-parse HEAD` in the
`6-codebases/repos/pypsa-earth` worktree at the time the report was published.
PyPSA-RSA HEAD: `89872c1ea703af3d8a3f198706d1ab7958f50a5f`.

## Module 13b — Stock Baseline Solve

**Date:** 2026-05-13. Completed stock solve:
`results/za_2023_stock_baseline/networks/elec_s_34_ec_lc1_NoCO2-1H-STOCK.nc`.

| artifact_path | hash (sha256) | source | owner | extraction_date | unresolved_warnings |
|---|---|---|---|---|---|
| `configs/za/za_2023_stock_baseline.yaml` | `a19db84a3db81215875cf09fca65ba2adf5d8d29bbc094eb3c035bbbca6e8979` | author (Module 13b); stock PPM/EUR/no-dispatch-calibration settings with IRENA RE scaling and upstream thermal carriers | nylan-ramnauth, codex | 2026-05-13 | none |
| `scripts/add_electricity.py` | `698d6de7487bbebc647721829c6cd403974604310cd595bacdd02fa8fad082e7` | author (Module 13b fix); skips `data/nuclear_p_max_pu.csv` overlay for `za_stock_baseline` runs | nylan-ramnauth, codex | 2026-05-13 | none |
| `scripts/za_validation/build_module13_validation.py` | `677b7d9af565d5d4a104eeaffd1804803f716b9ff62f4952e8ce6cd20b13506e` | author (Module 13b extension to Module 13 validation builder) | nylan-ramnauth, codex | 2026-05-13 | none |
| `results/za_2023_stock_baseline/networks/elec_s_34_ec_lc1_NoCO2-1H-STOCK.nc` | `7c4cd5279fcbdb9bb21066696177a27248286052afda142cdf9dc29ce7bd2a1a` | PyPSA-Earth stock solve: PPM fleet, EUR costs, IRENA-scaled RE, upstream thermal carriers, Eskom 2023 demand, 34-region busmap | Module 13b | 2026-05-13 | expected to deviate substantially from Eskom 2023; not an acceptance failure |
| `data/za_validation/za_2023_stock_vs_calibrated.csv` | `d9de619cf9ae7426d783aa46315e3c2939c499b9da734ed8dc76a6d5fb0b1c50` | `scripts/za_validation/build_module13_validation.py`; produced conditionally when STOCK network exists | Module 13b | 2026-05-13 | zero-denominator percentage deltas reported as `n/a` in narrative table |
| `data/za_validation/za_2023_validation_manifest.json` | `26fb4dc1ea85498d01f59ec0bea81397cced9cb93e9b3a30df44811219ce2214` | `scripts/za_validation/build_module13_validation.py`; manifest includes the conditional Module 13b stock CSV | Module 13b | 2026-05-13 | none |
| `notebooks/za_validation/12_dispatch_calibration/dispatch_calibration_validation.ipynb` | `939ac7e435b117cfe39ca652eef8a8ebe8657c988c7aba1bce2af9c5e83ad1ce` | notebook extended and re-executed with STOCK as fifth scenario in existing Module 12 diagnostics | nylan-ramnauth, codex | 2026-05-13 | none |
| `doc/za_2023_validation_report.md` | `0ed60e307af4aa8ccc6e0d13b62176812e7cb27be332a6b080cfdd2c476f10f6` | §6b inserted between §6 and §7 and populated from `za_2023_stock_vs_calibrated.csv` | nylan-ramnauth, codex | 2026-05-13 | none |
