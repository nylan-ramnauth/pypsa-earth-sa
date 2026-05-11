# South Africa Baseline Implementation Log

This append-only log records implementation decisions, deviations, source inputs, output artifacts, and follow-ups for the ZA baseline calibration plan.

## 00 Governance And Scope — 2026-05-08 11:22

- **Status:** complete
- **Decisions taken:**
  - Implemented modules 00 and 01 on the current `main` checkout, per user confirmation, because it contains the frozen active plans and latest `AGENTS.md`.
  - Created the repository-local implementation log as the binding module completion artifact.
- **Deviations from plan:**
  - None.
- **Source inputs used:**
  - `AGENTS.md`
  - `doc/active/calibration-plan/00_governance_and_scope.md`
  - `doc/active/calibration-plan/01_repo_bootstrap_and_config.md`
  - Vault plan files under `6-codebases/Plans/Calibration Plan/`
  - PyPSA-Earth HEAD `dacf37804e8d78f5a9a4b97d08958e22a747a839`
  - PyPSA-RSA HEAD `89872c1ea703af3d8a3f198706d1ab7958f50a5f`
- **Output artifacts produced:**
  - `doc/za_implementation_log.md`
- **Open follow-ups:**
  - Later modules must continue appending one structured log entry per completed module.
  - Workstream B reliability/myopic implementation remains out of scope until Workstream A Module 13 handoff artifacts exist and are accepted.

## 01 Repo Bootstrap And Config — 2026-05-08 11:22

- **Status:** complete
- **Decisions taken:**
  - Used explicit Snakemake invocation as the overlay composition contract: `snakemake --configfile configs/za/za_2023_fixed_validation.yaml --dry-run`.
  - Left the top-level `Snakefile`, `config.yaml`, and upstream defaults unchanged for South Africa-only settings.
  - Added narrow `.gitignore` exceptions so required ZA audit CSV skeletons are trackable despite the repo-wide `data/*` and `*.csv` ignore rules.
  - Recorded the local Gurobi version split: `/usr/local/bin/gurobi_cl` reports 13.0.0, while the locked Python environment contains `gurobipy=12.0.3`.
  - Kept bootstrap `load_options` on the existing PyPSA-Earth demand dataset (`ssp2-2.6`, `weather_year=2013`, `prediction_year=2030`) so DAG dry-runs resolve before Module 06 creates validated 2023 demand inputs.
- **Deviations from plan:**
  - `data/za_validation/.gitkeep` and `doc/za_validation/figures/.gitkeep` were added only to make empty bootstrap directories visible to git.
  - The overlay does not point `load_options` at `2023/era5_2023` during bootstrap because `data/ssp2-2.6/2023/era5_2023/Africa.nc` is absent and demand/input replacement is explicitly owned by Module 06.
- **Source inputs used:**
  - `doc/active/calibration-plan/01_repo_bootstrap_and_config.md`
  - `config.default.yaml`
  - `envs/environment.yaml`
  - `envs/osx-arm64.lock.yaml`
  - PyPSA-Earth HEAD `dacf37804e8d78f5a9a4b97d08958e22a747a839`
  - PyPSA-RSA HEAD `89872c1ea703af3d8a3f198706d1ab7958f50a5f`
  - Upstream plan pin `e18bea540e0742ea978e00338df143fa01e78553`
  - Prebuilt cutout `cutouts/cutout-2023-era5.nc`, SHA256 `0c6b22fa6b8a0a469cc24460df2014fdb9c041035985dfb3b1aa7d6608e19076`
- **Output artifacts produced:**
  - `.gitignore`
  - `configs/za/za_2023_fixed_validation.yaml`
  - `envs/za_environment.yaml`
  - `data/za_validation/.gitkeep`
  - `data/za_audit/input_file_manifest.csv`
  - `data/za_audit/source_hashes.csv`
  - `data/za_audit/za_runtime_preflight.csv`
  - `doc/za_data_provenance.md`
  - `doc/za_validation/figures/.gitkeep`
- **Verification completed:**
  - YAML parse passed for `configs/za/za_2023_fixed_validation.yaml` and `envs/za_environment.yaml`.
  - Package-version check passed in `/opt/anaconda3/envs/pypsa-earth`.
  - Gurobi trivial LP smoke test passed with `status=2` and objective `1.0`.
  - Required dry-run passed: `snakemake --configfile configs/za/za_2023_fixed_validation.yaml --dry-run`.
  - Stronger solve target DAG check passed: `snakemake solve_all_networks --configfile configs/za/za_2023_fixed_validation.yaml --dry-run`; DAG contains 24 jobs.
- **Open follow-ups:**
  - Module 06 must replace bootstrap demand settings with validated South Africa 2023 demand/import/export inputs.
  - Before Module 03, confirm whether the detected prebuilt cutout should remain the canonical fixed-validation weather input or be rebuilt from CDS.
  - Before Module 09, verify whether `add_electricity` auto-resolves `custom_powerplants.csv` bus assignment from lat/lon for ZA carriers after PR #1622.
  - Module 07 must decide how ZA local carriers handle `electricity_grid_connection`.

## 02 Eskom Validation Data Pipeline — 2026-05-08 11:48

- **Status:** complete
- **Decisions taken:**
  - Added a standalone parser script and explicit Snakemake rule `build_za_eskom_validation_data` so Eskom validation data can be regenerated without running the full model DAG.
  - Staged the raw Eskom CSV from the repo root to `data/za_audit/raw/eskom_data_2023_full.csv`.
  - Resolved the residual-demand identity from the inspected raw columns as `Residual Demand = Dispatchable Generation + Manual Load_Reduction(MLR) + ILS Usage + IOS Excl ILS and MLR`.
  - Used end-of-year 2023 PV and total RE installed capacities for the later capacity-validation reference.
- **Deviations from plan:**
  - The raw file gives Eskom Gas Generation as `0.00711849 TWh` in 2023, not exactly zero. The parser retains the raw value and records a warning, but does not classify it as a parser error.
  - `RSA Contracted Demand - Residual Demand - Total RE = 0.444123395 TWh`; this is recorded as a source/accounting warning rather than adjusted away.
- **Source inputs used:**
  - `doc/active/calibration-plan/02_eskom_validation_data_pipeline.md`
  - `6-codebases/Plans/Calibration Plan/90_Comments_Questions.md`
  - `data/za_audit/raw/eskom_data_2023_full.csv`, SHA256 `8c2220f114ba60d5ae823f5116368cc2a664ec625d70f4d52bdf26caffc29869`
  - Eskom glossary source `1-sources/web-clips/2026-05-07 WEB Glossary.md`
  - Canonical glossary reference `3-wiki/reference/web-clips/2026-05-07-eskom-dataportal-glossary.md`
- **Column inspection:**
  - Raw CSV header has 42 columns:
    `Date Time Hour Beginning`; `Original Res Forecast before Lockdown`; `Residual Forecast`; `RSA Contracted Forecast`; `Dispatchable Generation`; `Residual Demand`; `RSA Contracted Demand`; `International Exports`; `International Imports`; `Thermal Generation`; `Nuclear Generation`; `Eskom Gas Generation`; `Eskom OCGT Generation`; `Hydro Water Generation`; `Pumped Water Generation`; `ILS Usage`; `Manual Load_Reduction(MLR)`; `IOS Excl ILS and MLR`; `Dispatchable IPP OCGT`; `Eskom Gas SCO`; `Eskom OCGT SCO`; `Hydro Water SCO`; `Pumped Water SCO Pumping`; `Wind`; `PV`; `CSP`; `Other RE`; `Total RE`; `Wind Installed Capacity`; `PV Installed Capacity`; `CSP Installed Capacity`; `Other RE Installed Capacity`; `Total RE Installed Capacity`; `Installed Eskom Capacity`; `Total PCLF`; `Total UCLF`; `Total OCLF`; `Total UCLF+OCLF`; `Non Comm Sentout`; `Drakensberg Gen Unit Hours`; `Palmiet Gen Unit Hours`; `Ingula Gen Unit Hours`.
  - `ILS Usage`, `Manual Load_Reduction(MLR)`, and `IOS Excl ILS and MLR` are independent columns in the raw file.
- **Output artifacts produced:**
  - `scripts/build_za_eskom_validation_data.py`
  - `Snakefile`
  - `.gitignore`
  - `data/za_audit/raw/eskom_data_2023_full.csv`
  - `data/za_validation/eskom_2023_hourly_clean.csv`
  - `data/za_validation/eskom_2023_targets_by_carrier.csv`
  - `data/za_audit/eskom_2023_parser_report.csv`
  - `notebooks/za_validation/02_eskom_data/parser_report.ipynb`
  - `doc/za_validation/figures/02_eskom_data/parser_report.html`
  - `doc/za_data_provenance.md`
  - `data/za_audit/input_file_manifest.csv`
  - `data/za_audit/source_hashes.csv`
- **Verification completed:**
  - Direct parser execution passed in `/opt/anaconda3/envs/pypsa-earth`.
  - Snakemake dry-run passed for `build_za_eskom_validation_data`.
  - Snakemake execution passed for `build_za_eskom_validation_data`.
  - Notebook execution and HTML export passed for `notebooks/za_validation/02_eskom_data/parser_report.ipynb`.
  - Clean hourly output has exactly 8,760 rows and no missing hourly timestamps.
  - `Total RE = Wind + PV + CSP + Other RE` passes with maximum hourly difference `9.094947017729282e-13 MW`.
  - `Residual Demand = Dispatchable Generation + MLR + ILS + IOS` passes with maximum hourly difference `0.0010000000038417056 MW`, within tolerance after floating-point epsilon.
- **Open follow-ups:**
  - Primary external cross-checks for CSIR Utility Statistics Report 2024, Eskom Annual Report 2023, and System Adequacy Outlook remain pending where not present locally.
  - Module 06 should consume `RSA Contracted Demand` as the demand target and must not subtract load shedding before modeling.

## 03 Weather Cutout And Profiles — 2026-05-08 12:30

- **Status:** complete
- **Decisions taken:**
  - Kept the established run directory `za_2023_fixed_validation` from modules 00-02 rather than renaming outputs to `za_2023_fixed`.
  - Reused `cutouts/cutout-2023-era5.nc` because the SHA256 hash, ERA5 module metadata, 0.3-degree resolution, and 8,760-hour 2023 coverage match the module 01 provenance record. No full CDS rebuild was attempted.
  - Set the ZA overlay to `enable.retrieve_cutout: false`, `enable.build_cutout: false`, and `atlite.default: cutout-2023-era5`.
  - Verified that PyPSA-Earth resolves `renewable.csp.cutout: auto` to `cutout-2023-era5`; CSP is a separate `csp` carrier and is not merged into PV. The default CSP model remains `advanced`.
  - Added `validate_za_renewable_profiles` as a dedicated Snakemake target for module 03 Gate A validation.
  - Verified `build_demand_profiles.py:get_load_paths_gegis` accepts the `2023_custom` weather-year string; it resolves to `data/ssp2-2.6/2030/era5_2023_custom/Africa.csv`.
- **Deviations from plan:**
  - Hydro profile generation produced an upstream `profile_hydro.nc` file, but it is empty because `build_powerplants` reported no known South Africa plants before module 08 fleet reconciliation. This is recorded as a warning, not adjusted with a fallback profile.
  - Large cutout/profile NetCDF files remain git-ignored; their paths and hashes are recorded in `data/za_audit/input_file_manifest.csv`, `data/za_audit/source_hashes.csv`, and `doc/za_data_provenance.md`.
  - Notebook HTML export passed with a non-blocking nbconvert warning that two images lack alternative text.
- **Source inputs used:**
  - `doc/active/calibration-plan/03_weather_cutout_and_profiles.md`
  - `6-codebases/Plans/Calibration Plan/90_Comments_Questions.md`
  - `cutouts/cutout-2023-era5.nc`, SHA256 `0c6b22fa6b8a0a469cc24460df2014fdb9c041035985dfb3b1aa7d6608e19076`
  - `data/za_validation/eskom_2023_targets_by_carrier.csv`, SHA256 `dc0bba6c28d5dc0f1fb4004eee3a476f6c371f0bfe13316d5ec6c7204e508ec3`
  - PyPSA-Earth upstream `build_renewable_profiles`, `build_cutout`, and `get_load_paths_gegis` helpers in the current checkout.
- **Output artifacts produced:**
  - `configs/za/za_2023_fixed_validation.yaml`
  - `Snakefile`
  - `scripts/validate_za_renewable_profiles.py`
  - `resources/za_2023_fixed_validation/renewable_profiles/profile_solar.nc` (git-ignored, hash recorded)
  - `resources/za_2023_fixed_validation/renewable_profiles/profile_onwind.nc` (git-ignored, hash recorded)
  - `resources/za_2023_fixed_validation/renewable_profiles/profile_hydro.nc` (git-ignored, hash recorded)
  - `resources/za_2023_fixed_validation/renewable_profiles/profile_csp.nc` (git-ignored, hash recorded)
  - `data/za_audit/za_atlite_renewable_profile_validation.csv`
  - `data/za_audit/za_atlite_technical_potential.csv`
  - `doc/za_renewable_profile_validation.md`
  - `notebooks/za_validation/03_profiles/profile_validation.ipynb`
  - `doc/za_validation/figures/03_profiles/profile_validation.html`
  - `doc/za_data_provenance.md`
  - `data/za_audit/input_file_manifest.csv`
  - `data/za_audit/source_hashes.csv`
- **Verification completed:**
  - YAML parse passed for `configs/za/za_2023_fixed_validation.yaml`.
  - Cutout verification passed: 8,760 hours, ERA5 module, `dx=0.3`, `dy=0.3`, SHA256 `0c6b22fa6b8a0a469cc24460df2014fdb9c041035985dfb3b1aa7d6608e19076`.
  - Snakemake dry-run passed for `validate_za_renewable_profiles`.
  - Snakemake execution passed for `validate_za_renewable_profiles`; the DAG generated `profile_solar.nc`, `profile_onwind.nc`, `profile_hydro.nc`, and `profile_csp.nc`.
  - Direct validation script execution passed.
  - Notebook execution and HTML export passed for `notebooks/za_validation/03_profiles/profile_validation.ipynb`.
  - Gate A validation table reports 29 passing checks and 4 hydro warnings.
- **Open follow-ups:**
  - Module 04 should add public/literature sanity anchors and PyPSA-RSA profile-reference comparisons for Gate B.
  - Module 08 must reconcile the South Africa fleet so hydro plants are available to later hydro profile and dispatch validation.
  - Module 06 can use the accepted `2023_custom` GEGIS string, but it still owns demand/input replacement.

## 04 Source Data Audits — 2026-05-08 13:22

- **Status:** complete
- **Decisions taken:**
  - Re-confirmed PyPSA-RSA pin: local `HEAD` and `origin/main` both equal `89872c1ea703af3d8a3f198706d1ab7958f50a5f`. No no-silent-rebase review required.
  - PyPSA-Earth current HEAD recorded as `dacf37804e8d78f5a9a4b97d08958e22a747a839`.
  - Implemented Module 04 as a single Snakemake rule `build_za_source_audits` that orchestrates ten audit stages from the new `scripts/za_audits/` package; this mirrors the module 02/03 single-rule pattern.
  - Powerplantmatching uses `from_url=False, update=True` with `target_countries=['South Africa']` and the upstream matching/fully-included sources, matching the pattern in `scripts/build_powerplants.py`. The packaged `from_url=True` dataset is Europe-only and produced 0 ZA rows; the matching pipeline produced 276 SA plants including 147 solar and 52 wind. `EXTERNAL_DATABASE` was excluded so no ENTSOE token is required.
  - The 2023-active filter follows the plan verbatim: `Commissioning Date <= 2023 AND (Decommissioning Date > 2023 OR Decommissioning Date IS NULL)`. Future assets (Redstone CSP, 2024-2027 BESS, fixed-tech rows with later commissioning) remain in the audit candidates with `included_2023 = false`. Resulting fixed_tech split: 306 rows `included_2023 = true`, 905 rows `included_2023 = false`.
  - Existing-line GeoJSON filters `DESIGN_VOL >= 220 kV` (324 features retained out of 348 total).
  - Supply-region layer resolution check correctly identifies all canonical PyPSA-RSA layer counts: layers `1`, `10`, `27`, `34`, `159` are present in both `rsa_supply_regions.gpkg` and `rsa_supply_regions2.gpkg`, plus matching feature counts in `AREAS_GCCA2025.gpkg` (`SUPPLY_AREA_GCCA2025=10`, `LOCAL_AREA_GCCA2025=34`, `MTS_ZONES_GCCA2025=159`) and the corresponding shapefile copies.
  - Flat vs nested duplicate bundle copies (`Existing_Lines.shp`, `TDP_2023_32.shp`) are both recorded in the registry; the deeper scenario-tagged copies (`data/bundle/Shapefiles/Existing_Lines.shp`, `data/bundle/transmission_grid/tdp_digitised/TDP_2023_32.shp`) are canonical, the flat copies marked `do_not_port`.
  - Candidate-missing files at the pinned commit recorded explicitly in the registry: `scripts/solve_network.py`, `scripts/add_extra_components.py`, `scripts/build_renewable_profiles.py`, and `pre_processing/resource_processing/reipppp_phs_data.csv` are absent and tagged `do_not_port` with `notes="ABSENT at pin: ..."`. `scripts/prepare_and_solve_network.py`, `envs/environment.yaml`, and `scenarios/Coal_Flexibilisation/sub_scenarios/phased_decommissioning.xlsx` are present and tagged `audit_only` / `validation_reference`.
- **Deviations from plan:**
  - `data/bundle/renewable_profiles_updated.nc` opens as an empty xarray Dataset (no data_vars or dims). Audit records this as a single row in `pypsa_rsa_eskom_pu_profiles_audit.csv` with the file hash plus an explanatory note — no fallback applied.
  - `pypsa-rsa` PHS reconciliation file `reipppp_phs_data.csv` is absent at pin; recorded as `do_not_port` per plan §"Candidate missing files".
  - Notebook HTML export passed with one non-blocking nbconvert warning ("Alternative text is missing on 1 image(s)") for the supply-region/lines map — same pattern as module 03.
- **Source inputs used:**
  - `doc/active/calibration-plan/04_source_data_audits.md`
  - `6-codebases/Plans/Calibration Plan/90_Comments_Questions.md` (`# 04_source_data_audits`)
  - PyPSA-Earth HEAD `dacf37804e8d78f5a9a4b97d08958e22a747a839`
  - PyPSA-RSA HEAD/`origin/main` `89872c1ea703af3d8a3f198706d1ab7958f50a5f`
  - `configs/powerplantmatching_config.yaml`
  - All PyPSA-RSA scenario workbooks under `scenarios/ME IRP 2024/` and `scenarios/Coal_Flexibilisation/`
  - PyPSA-RSA bundle artefacts under `data/bundle/` (supply_regions, GCCA 2025 GIS, Shapefiles, transmission_grid)
  - `pre_processing/resource_processing/{reipppp_solar_data.csv, reipppp_wind_data.csv, csir_fise_SWA_data.xlsx}`
  - `data/eskom_pu_profiles.csv`
  - `data/bundle/SystemEnergy2009_22.csv`, `data/bundle/Supply area normalised power feed-in for {Wind,PV}.xlsx`, `data/bundle/renewable_profiles_updated.nc`
- **Output artifacts produced:**
  - `configs/za/za_2023_fixed_validation.yaml` (added `pypsa_rsa_root` + `pypsa_rsa_pinned_commit`)
  - `Snakefile` (added `build_za_source_audits` rule)
  - `scripts/build_za_source_audits.py` (master orchestrator)
  - `scripts/za_audits/__init__.py`
  - `scripts/za_audits/io.py`
  - `scripts/za_audits/registry.py`
  - `scripts/za_audits/scenario_workbooks.py`
  - `scripts/za_audits/powerplantmatching.py`
  - `scripts/za_audits/fleet_availability.py`
  - `scripts/za_audits/profiles.py`
  - `scripts/za_audits/cost_fuel_emissions.py`
  - `scripts/za_audits/load_weights.py`
  - `scripts/za_audits/grid_spatial.py`
  - `scripts/za_audits/resource_siting.py`
  - `data/za_audit/pypsa_rsa_source_registry.csv` (72 rows)
  - `data/za_audit/pypsa_rsa_discovery_sweep.csv` (77 rows)
  - `data/za_audit/powerplants_pm_za_full.csv` (276 rows)
  - `data/za_audit/powerplants_pm_za_audit.csv` (276 rows)
  - `data/za_audit/pypsa_rsa_scenario_workbook_inventory.csv` (55 rows)
  - `data/za_audit/pypsa_rsa_fixed_technologies_2023_candidates.csv` (1211 rows; 306 included_2023=true, 905 false)
  - `data/za_audit/reipppp_solar_2023_candidates.csv` (64 rows)
  - `data/za_audit/reipppp_wind_2023_candidates.csv` (70 rows)
  - `data/za_audit/pypsa_rsa_availability_audit.csv` (716 rows)
  - `data/za_audit/pypsa_rsa_operational_constraints_audit.csv` (262 rows)
  - `data/za_audit/pypsa_rsa_reserve_margin_audit.csv` (64 rows)
  - `data/za_audit/pypsa_rsa_eskom_pu_profiles_audit.csv` (15 rows)
  - `data/za_audit/pypsa_rsa_cost_fuel_emissions_audit.csv` (2554 rows)
  - `data/za_audit/pypsa_rsa_load_weight_audit.csv` (11 rows)
  - `data/za_audit/pypsa_rsa_external_bundle_inventory.csv` (15 rows)
  - `data/za_audit/za_rsa_supply_regions.geojson` (27 features)
  - `data/za_audit/za_rsa_supply_region_layer_resolution.csv` (17 rows; canonical 1/10/27/34/159 all matched)
  - `data/za_audit/za_rsa_existing_lines_220kv_plus.geojson` (324 features)
  - `data/za_audit/za_rsa_planned_tdp_lines.geojson` (102 features)
  - `data/za_audit/za_rsa_supply_area_connection_limits.csv` (30 rows)
  - `data/za_audit/za_rsa_mts_hosting_limits.csv` (198 rows)
  - `data/za_audit/pypsa_rsa_transmission_expansion_audit.csv` (134 rows)
  - `data/za_audit/pypsa_rsa_resource_siting_audit.csv` (10 rows)
  - `notebooks/za_validation/04_source_audits/source_audit_overview.ipynb`
  - `doc/za_validation/figures/04_source_audits/source_audit_overview.html`
  - `doc/za_validation/figures/04_source_audits/grid_overview.png`
  - `data/za_audit/source_hashes.csv` (Module 04 entries appended)
  - `data/za_audit/input_file_manifest.csv` (Module 04 entries appended)
  - `doc/za_data_provenance.md` (Module 04 section appended with full hash table)
- **Verification completed:**
  - YAML parse passed for `configs/za/za_2023_fixed_validation.yaml`.
  - Direct script execution passed: `python scripts/build_za_source_audits.py --configfile configs/za/za_2023_fixed_validation.yaml` (22 stages succeed; final summary `{registry: 72, discovery: 77, ppm: 276, scenario_workbooks: 55, fixed_tech: 1211, reipppp_solar: 64, reipppp_wind: 70, availability: 716, op_constraints: 262, reserve_margin: 64, eskom_pu: 15, cost_fuel: 2554, load_weights: 11, bundle_inv: 15, supply_layer_resolution: 17, supply_regions_geojson: 27, existing_lines_geojson: 324, planned_tdp_geojson: 102, supply_area_limits: 30, mts_limits: 198, transmission_expansion: 134, resource_siting: 10}`).
  - Snakemake dry-run passed: `snakemake --configfile configs/za/za_2023_fixed_validation.yaml --dry-run build_za_source_audits` (1 job).
  - Snakemake forced execution passed: `snakemake --configfile configs/za/za_2023_fixed_validation.yaml --cores 1 -F build_za_source_audits` finished with `1 of 1 steps (100%) done`.
  - Notebook execution and HTML export passed (`source_audit_overview.html`, 600,952 bytes).
  - Spot-check: `pypsa_rsa_source_registry.csv` row count = 72 (>= 50 minimum threshold).
  - Spot-check: `pypsa_rsa_fixed_technologies_2023_candidates.csv` contains rows with `included_2023 = false` (905 rows).
  - Spot-check: `za_rsa_supply_region_layer_resolution.csv` matches canonical 1/10/27/34/159 layers in `rsa_supply_regions.gpkg`, `rsa_supply_regions2.gpkg`, and the GCCA 2025 GIS bundle.
- **Open follow-ups:**
  - Module 03 Gate B can now consume the Eskom pu profile audit and the supply-area normalised PV/Wind workbooks for cross-validation.
  - Module 06 owns the downstream comparison of PyPSA-RSA `GVA_2016 + POP_2016` weights against the PyPSA-Earth V1 load allocation; this module exposes the weights but does not re-allocate load.
  - Module 08 owns fleet reconciliation; the `included_2023 = true` subset of `pypsa_rsa_fixed_technologies_2023_candidates.csv` plus REIPPPP audits are the canonical baseline candidate set.
  - Module 09 owns the supply-region selection between 1/10/27/34/159 layers and the busmap; module 04 only catalogs the available resolutions.
  - Module 13 owns expansion handoff; `pypsa_rsa_transmission_expansion_audit.csv`, `za_rsa_planned_tdp_lines.geojson`, and the resource-siting audit are expansion-only evidence.

## 05 System Boundary And Carrier Taxonomy — 2026-05-08 16:10

- **Status:** complete (network-level CSP/solar smoke-test gate pending module 10).
- **Decisions taken:**
  - Re-confirmed PyPSA-RSA pin: local `HEAD` and `origin/main` both equal `89872c1ea703af3d8a3f198706d1ab7958f50a5f`. PyPSA-earth HEAD at module entry = `f5422d8f384a86117bbc18b3048784e265808669`.
  - Locked V1 modeling boundary (`za_system_boundary` block): national SA 2023 electricity system, demand target = `RSA Contracted Demand`, load shedding target = `MLR + ILS + IOS`, imports/exports owned by module 06, embedded PV excluded as explicit plant capacity, IPP utility wind/PV/CSP included, CSP 2023 anchors = 500 MW / 1.375 TWh with Redstone excluded.
  - Locked V1 carrier set in `electricity.{conventional,renewable,extendable}_carriers`: `conventional_carriers = [coal, nuclear]`, `renewable_carriers = [solar, onwind, hydro, csp]`, all `extendable_carriers` lists empty (true V1 fixed-fleet).
  - Locked structural metadata for the five ZA local carriers (`sasol_coal`, `sasol_gas`, `ocgt_diesel`, `ocgt_gas`, `other_re`) under `za_local_carriers:` — names, color, nice_name, profile/emissions/validation/availability intent. Numeric cost rows are owned by module 07; the `apply_za_local_carriers` network hook is owned by module 10.
  - RSA → V1 carrier mapping is hand-coded inside `scripts/build_za_carrier_taxonomy.py` (the mapping itself is the lock). 17 distinct RSA carriers in module 04 fixed-tech audit: 15 `resolved`, 1 `excluded_by_boundary` (`solar_pv_rooftop`), 1 `pending_module_08` (`rmippp` — procurement program label).
  - CSP/solar acceptance smoke test deferred to module 10 via `scripts/za_validation/smoke_carrier_taxonomy.py` (exit codes: 0 pass, 1 fail, 2 skip-when-no-network).
- **Deviations from plan:**
  - Plan-time verification spec asserted "all `resolved`"; actual crosscheck has two non-`unresolved` non-`resolved` statuses (`excluded_by_boundary` for embedded PV per system boundary, `pending_module_08` for the RMIPPP procurement-program label). Verification gate updated to "no `unresolved` rows" — equivalent strength.
- **Source inputs used:**
  - `doc/active/calibration-plan/05_system_boundary_and_carrier_taxonomy.md`
  - `6-codebases/Plans/Calibration Plan/90_Comments_Questions.md` §`# 05_system_boundary_and_carrier_taxonomy` (= "None")
  - `data/za_audit/pypsa_rsa_fixed_technologies_2023_candidates.csv` (module 04)
  - `data/za_audit/pypsa_rsa_source_registry.csv` (module 04)
  - PyPSA-Earth HEAD `f5422d8f384a86117bbc18b3048784e265808669`
  - PyPSA-RSA HEAD `89872c1ea703af3d8a3f198706d1ab7958f50a5f`
- **Output artifacts produced:**
  - `configs/za/za_2023_fixed_validation.yaml` (added `za_system_boundary`, `za_local_carriers`, locked `electricity.conventional_carriers`)
  - `doc/za_carrier_taxonomy.md` (canonical taxonomy doc, 8 sections)
  - `data/za_audit/za_carrier_taxonomy.csv` (16 rows: 15 V1 + hydro_import supplemental)
  - `data/za_audit/za_carrier_taxonomy_crosscheck.csv` (17 rows; 15 resolved / 1 excluded / 1 pending)
  - `scripts/build_za_carrier_taxonomy.py` (dual-mode CLI/Snakemake generator)
  - `scripts/za_validation/__init__.py`, `scripts/za_validation/smoke_carrier_taxonomy.py` (deferred smoke test)
  - `Snakefile` rule `build_za_carrier_taxonomy`
  - `notebooks/za_validation/05_carrier_taxonomy/carrier_taxonomy_overview.ipynb` (+ `.executed.ipynb`)
  - `doc/za_validation/figures/05_carrier_taxonomy/carrier_taxonomy_overview.html` (355,140 bytes)
  - `doc/za_validation/figures/05_carrier_taxonomy/mw_by_v1_carrier.png`
  - `data/za_audit/source_hashes.csv` (Module 05 rows appended)
  - `data/za_audit/input_file_manifest.csv` (Module 05 rows appended)
  - `doc/za_data_provenance.md` (Module 05 section appended)
- **Verification completed:**
  - YAML parse passed for `configs/za/za_2023_fixed_validation.yaml`.
  - Direct script execution passed: `python scripts/build_za_carrier_taxonomy.py --configfile configs/za/za_2023_fixed_validation.yaml` → `taxonomy: 16 rows; crosscheck: 17 rows`.
  - Snakemake dry-run passed: `snakemake --configfile configs/za/za_2023_fixed_validation.yaml --dry-run build_za_carrier_taxonomy` (1 job).
  - Snakemake execution passed: `snakemake --configfile configs/za/za_2023_fixed_validation.yaml -j1 build_za_carrier_taxonomy` → `1 of 1 steps (100%) done`.
  - Crosscheck assertion passed: `python -c "import pandas as pd; df=pd.read_csv('data/za_audit/za_carrier_taxonomy_crosscheck.csv'); assert (df['status']!='unresolved').all()"`.
  - Smoke-test skip path verified: `python scripts/za_validation/smoke_carrier_taxonomy.py /nonexistent.nc; echo $?` → `2`.
  - Notebook execution + HTML export passed (`carrier_taxonomy_overview.html`, 355,140 bytes; `mw_by_v1_carrier.png` rendered).
  - Cross-module DAG dry-run passed: `snakemake --configfile configs/za/za_2023_fixed_validation.yaml --dry-run build_za_carrier_taxonomy build_za_source_audits` → `Nothing to be done`.
- **Open follow-ups:**
  - Module 06 must consume `za_system_boundary` (demand target, imports/exports note, embedded PV exclusion) when building load and import/export model inputs.
  - Module 07 owns `data/za_audit/za_local_carrier_cost_rows.csv` for the 5 local carriers; cost numeric values must be filled per `za_local_carriers` validation/emissions intent.
  - Module 08 owns the active-2023 biomass decision and the `rmippp` per-plant carrier reconciliation flagged by the crosscheck `pending_module_08` rows.
  - Module 10 owns the `apply_za_local_carriers` network hook; once it produces a network, run `python scripts/za_validation/smoke_carrier_taxonomy.py <net.nc>` to fire the deferred CSP/solar acceptance gate.
  - Module 11 dispatch must respect the V1 carrier set and not silently extend it.

## 06 Demand Import Export Model Inputs — 2026-05-08 16:40

- **Status:** complete
- **Decisions taken:**
  - Added `build_za_demand_import_export_inputs` as a dedicated Snakemake rule and `scripts/build_za_demand_import_export_inputs.py` as the dual-mode builder.
  - Replaced the module 01 bootstrap demand setting with `load_options.weather_year: 2023_custom` while keeping `ssp2-2.6`, `prediction_year: 2030`, and `scale: 1`.
  - Exported Eskom `RSA Contracted Demand` to the upstream GEGIS CSV route at `data/ssp2-2.6/2030/era5_2023_custom/Africa.csv`.
  - Kept gross imports and gross exports separate. `International Imports` is positive supply injection, `International Exports` is positive withdrawal, and net import is diagnostic only.
  - Treated `Other RE` as a curtailable local generator input for module 10: `p_nom = 50.58 MW`, `p_max_pu = Other RE / p_nom`, clipped to `[0, 1]`, and `p_min_pu = 0`.
  - Built demand weights for candidate layers `1`, `10`, and `34` with PyPSA-Earth-style GADM area-overlay allocation using normalized `0.6 * gdp + 0.4 * pop`.
  - Used conservative proxy attachments for non-demand series: imports attach to `ZA`, `Gauteng`, and `Pretoria`; exports and `Other RE` reuse demand weights until module 09 resolves final bus IDs.
- **Deviations from plan:**
  - PyPSA-RSA regional `GVA_2016`/`POP_2016` diagnostics are available for the national layer only. The actual audited PyPSA-RSA 10- and 34-region layers do not contain regional `GVA_2016`/`POP_2016` columns, so `pypsa_rsa_gva_pop_load_weight_comparison.csv` records 1 available diagnostic row and 44 `diagnostic_unavailable` rows instead of inventing regional PyPSA-RSA weights.
  - The first Snakemake execution with `-F` also reran module 02 and module 04 prerequisites because Snakemake force-propagated through the dependency chain; the unrelated module 04 powerplant CSVs only changed nondeterministic ordering inside serialized set/dict strings and were restored to their pre-run state.
  - Notebook HTML export passed with a non-blocking nbconvert warning that 4 images lack alternative text.
- **Source inputs used:**
  - `doc/active/calibration-plan/06_demand_import_export_model_inputs.md`
  - `6-codebases/Plans/Calibration Plan/90_Comments_Questions.md` (`# 06_Demand_import_export_model_inputs`)
  - `data/za_validation/eskom_2023_hourly_clean.csv`, SHA256 `bab73ee6b46d4c147d64b9e0b8d88a01eff2d49229e4688729b180aa1ca4221a`
  - `data/za_validation/eskom_2023_targets_by_carrier.csv`, SHA256 `dc0bba6c28d5dc0f1fb4004eee3a476f6c371f0bfe13316d5ec6c7204e508ec3`
  - `data/za_audit/pypsa_rsa_load_weight_audit.csv`
  - `resources/za_2023_fixed_validation/shapes/gadm_shapes.geojson`
  - PyPSA-RSA `data/bundle/supply_regions/rsa_supply_regions.gpkg` at pin `89872c1ea703af3d8a3f198706d1ab7958f50a5f`
- **Output artifacts produced:**
  - `scripts/build_za_demand_import_export_inputs.py`
  - `configs/za/za_2023_fixed_validation.yaml`
  - `Snakefile`
  - `.gitignore`
  - `data/za_validation/za_2023_demand_profile.csv`
  - `data/ssp2-2.6/2030/era5_2023_custom/Africa.csv`
  - `data/za_validation/za_2023_import_export_timeseries.csv`
  - `data/za_validation/za_2023_other_re_timeseries.csv`
  - `data/za_audit/za_2023_load_allocation_weights.csv`
  - `data/za_audit/pypsa_rsa_gva_pop_load_weight_comparison.csv`
  - `data/za_audit/za_2023_import_export_attachment.csv`
  - `data/za_audit/za_2023_other_re_attachment.csv`
  - `doc/za_demand_import_export_model_inputs.md`
  - `notebooks/za_validation/06_demand_import_export/demand_import_export_overview.ipynb`
  - `doc/za_validation/figures/06_demand_import_export/demand_import_export_overview.html`
  - `data/za_audit/source_hashes.csv`
  - `data/za_audit/input_file_manifest.csv`
  - `doc/za_data_provenance.md`
- **Verification completed:**
  - YAML parse passed for `configs/za/za_2023_fixed_validation.yaml`; `weather_year` is `2023_custom`.
  - `python -m py_compile scripts/build_za_demand_import_export_inputs.py` passed.
  - Direct script execution passed in `/opt/anaconda3/envs/pypsa-earth`.
  - Snakemake dry-run passed for `build_za_demand_import_export_inputs`; after the generated `Africa.csv` existed, `get_load_paths_gegis` resolved the route to `data/ssp2-2.6/2030/era5_2023_custom/Africa.csv`.
  - Snakemake execution passed for `build_za_demand_import_export_inputs`.
  - Demand, GEGIS demand, import/export, and `Other RE` time series each have exactly 8,760 rows aligned to the cleaned Eskom 2023 hourly index.
  - All attachment-weight groups sum to `1.0` for layers `1`, `10`, and `34`.
  - Demand annual energy equals the module 02 `RSA Contracted Demand` target: `225.874862263 TWh`.
  - Notebook execution and HTML export passed for `notebooks/za_validation/06_demand_import_export/demand_import_export_overview.ipynb`.
- **Open follow-ups:**
  - Module 09 must resolve final PyPSA-Earth bus IDs and may replace the conservative import/export and `Other RE` proxy attachments with stronger grid evidence.
  - Module 10 must consume `za_2023_other_re_timeseries.csv` as a non-extendable curtailable `other_re` generator input, not as negative load or a fixed-dispatch generator.

## 07 Costs Fuels Efficiencies And CoUE — 2026-05-11 12:36

- **Status:** complete
- **Decisions taken:**
  - Locked upstream `costs.year: 2030` because the repo ships
    `data/costs.csv`, `data/costs_2025.csv`, and `data/costs_2030.csv` but
    no `costs_2023.csv`. Recorded as a known V1 limitation for Module 12.
  - Moved the ZA overlay `output_currency: ZAR` key from top-level into the
    `costs:` block because `scripts/add_electricity.py:759` reads
    `config["costs"]["output_currency"]`. The top-level key was unused.
  - Added `costs.electricity_grid_connection: 0` to disable the upstream
    per-generator grid-connection cost (PR `f8eab87a`) for ZA local
    carriers. Rationale: Module 08 will reconcile full per-plant capex
    through `custom_powerplants.csv`, including grid-connection components.
    Applying the upstream formula again would double-count.
  - Used the ECB historical archive `eurofxref-hist.zip` from
    `alexprengere/currencyconverter` instead of the spot file
    `eurofxref.csv` referenced in the plan, because the spot file only
    carries the latest ECB trading day. Frozen 2023 EUR/ZAR =
    `20.3477` on `2023-12-29`. Recorded the source URL, archive SHA256,
    and member name in `za_eur_zar_fxrate_2023.csv` and
    `data/za_audit/source_hashes.csv`.
  - Module 07 ships the data sidecar `za_local_carrier_cost_rows.csv` plus
    the importable EUR/ZAR helper `scripts/za_costs/currency.py`. The
    `apply_za_local_carriers` hook itself remains owned by Module 10. The
    plan's §"Cost currency policy" note that the hook is "implemented as
    part of Module 07" was reconciled against §"Local Carrier
    Requirements" (and the Module 05 log) by giving Module 07 the helper
    + sidecar and deferring the hook wiring.
  - Treated PyPSA-RSA fuel-price/cost rows as **2018 ZAR** for the
    ME_IRP23 scenario set. Used the ECB 2018 year-average EUR/ZAR =
    `15.6186` for ZAR → EUR conversion of audited values, and the frozen
    2023 rate for downstream EUR → ZAR reporting conversion.
  - For local carriers without a station entry in the PyPSA-RSA
    `fuel_prices` role (Sasol stations), fell back to the per-plant
    `Fuel Price (R/GJ)` column from `fixed_tech` so the local sidecar
    rows have populated `marginal_cost`.
  - Recorded CSIR (R116,570/MWh, 2024), Nova (R9,530/MWh, 2018/19), and
    Deloitte (R8,950/MWh, 2009) as the policy CoLS reference values.
    Solver safety-valve marginal cost (`100,000 EUR/MWh` from
    `solving.options.load_shedding: 100` × 1000 in `solve_network.py:161`)
    was not changed. Both frames are recorded for Module 12 reporting.
  - Left `capital_cost` blank in the local-carrier sidecar — Module 08
    owns per-plant capex through `custom_powerplants.csv`.
- **Deviations from plan:**
  - Plan §"Frozen exchange rate" pinned the URL to `eurofxref.csv` (spot
    file); used `eurofxref-hist.zip` from the same repository because the
    spot file does not carry historical rows. Documented in
    `scripts/za_costs/fxrate.py` and `doc/za_costs_fuels_efficiencies_and_coUE.md`.
  - Plan §"Cost currency policy" said the hook is implemented as part of
    Module 07. Implemented the helper + sidecar in Module 07 but deferred
    the hook wiring to Module 10 per §"Local Carrier Requirements" and the
    Module 05 log. Captured the resolution in the canonical doc.
  - Snakemake injects boilerplate above the entry script body, which
    forbids a leading `from __future__ import annotations` line in
    `scripts/build_za_costs_fuels_efficiencies.py`. Removed it; Python
    3.11 supports `dict[str, list[str]]` natively via PEP 585.
- **Source inputs used:**
  - `doc/active/calibration-plan/07_costs_fuels_efficiencies_and_coUE.md`
  - `data/za_audit/pypsa_rsa_cost_fuel_emissions_audit.csv`, SHA256 `42648462daa9c6bec30ac41ce5886132b0321d355d21917aa230dfb23e311e03`
  - `data/za_audit/za_carrier_taxonomy.csv`
  - `data/costs_2030.csv`, SHA256 `8a412a1d32c1f43fba1aa46295a67eab13345758eb5f5bffef415ca743b4d7b7`
  - `https://raw.githubusercontent.com/alexprengere/currencyconverter/master/currency_converter/eurofxref-hist.zip` (ECB historical archive)
  - PyPSA-Earth HEAD `2d76ba3569689817dc0c8bda99719670ec292f08`
  - PyPSA-RSA HEAD `89872c1ea703af3d8a3f198706d1ab7958f50a5f`
- **Output artifacts produced:**
  - `scripts/build_za_costs_fuels_efficiencies.py`
  - `scripts/za_costs/__init__.py`
  - `scripts/za_costs/fxrate.py`
  - `scripts/za_costs/currency.py`
  - `scripts/za_costs/audit_builder.py`
  - `scripts/za_costs/local_rows.py`
  - `Snakefile` (added `rule build_za_costs_fuels_efficiencies`)
  - `configs/za/za_2023_fixed_validation.yaml` (added `costs:` + `za_cols_policy:`; removed unused top-level `output_currency`)
  - `data/za_audit/za_costs_fuels_efficiencies_audit.csv` (105 rows)
  - `data/za_audit/za_local_carrier_cost_rows.csv` (5 rows)
  - `data/za_audit/za_eur_zar_fxrate_2023.csv` (1 row)
  - `data/za_audit/za_cols_reference_values.csv` (3 rows)
  - `doc/za_costs_fuels_efficiencies_and_coUE.md`
  - `notebooks/za_validation/07_costs_fuels/cost_fuel_overview.ipynb`
  - `doc/za_validation/figures/07_costs_fuels/cost_fuel_overview.html`
  - `data/za_audit/source_hashes.csv` (Module 07 rows appended)
  - `data/za_audit/input_file_manifest.csv` (Module 07 rows appended)
  - `doc/za_data_provenance.md` (Module 07 section appended)
- **Verification completed:**
  - YAML parse passed for `configs/za/za_2023_fixed_validation.yaml`.
  - `scripts/za_costs/currency.py` roundtrip self-test passed with `|err|=0`.
  - Direct script execution passed in `/opt/anaconda3/envs/pypsa-earth`:
    `{'audit': 105, 'local_rows': 5, 'cols_refs': 3, 'fxrate': 1, 'rate_2023': 20.3477, 'rate_2018': 15.6186}`.
  - Snakemake dry-run passed for `build_za_costs_fuels_efficiencies` (2 jobs counting `build_za_carrier_taxonomy` rerun).
  - Snakemake forced execution passed: `3 of 3 steps (100%) done`.
  - Carrier coverage assertion passed: every carrier in
    `za_carrier_taxonomy.csv` except `hydro_import` is present in the
    audit CSV (`{coal, nuclear, sasol_coal, sasol_gas, ocgt_diesel,
    ocgt_gas, onwind, solar, csp, hydro, ror, PHS, battery, biomass,
    other_re}`).
  - Local-rows lock passed: 5 rows for
    `{sasol_coal, sasol_gas, ocgt_diesel, ocgt_gas, other_re}` with
    `pypsa_earth_default_retained_reason` column present.
  - FX row passed: `date=2023-12-29`, `eur_zar_rate=20.3477`, archive
    SHA256 `9dea72fbf8116f2d76106d78f9875f2aa8157f39ed3cf728a1602f2a5445d199`.
  - CoLS refs passed: 3 rows with both ZAR and EUR populated.
  - `other_re` zero-policy passed: `marginal_cost=0`, `co2_emissions=0`,
    notes flag aggregate-category + biogenic-neutral V1.
  - `solving.options.load_shedding: true` unchanged in the overlay.
  - Notebook execution + HTML export passed
    (`cost_fuel_overview.html`, 294,469 bytes).
- **Open follow-ups:**
  - Module 08 owns capital-cost reconciliation for ZA local carriers
    through `custom_powerplants.csv`; the sidecar's `capital_cost` column
    is intentionally blank.
  - Module 10 must import `scripts.za_costs.currency.eur_to_zar` for the
    `apply_za_local_carriers` hook's EUR → ZAR reporting conversion and
    consume `data/za_audit/za_local_carrier_cost_rows.csv`.
  - Module 11 dispatch validation must use the marginal-cost values in
    `za_local_carrier_cost_rows.csv`; sensitivity to PyPSA-RSA base-year
    rate (2018 vs 2020) should be flagged.
  - Module 12 reporting must present load-shedding cost in both the
    solver-safety-valve EUR frame and the CSIR/Nova/Deloitte policy ZAR
    frame; aggregate-category limitation of `other_re` must be noted.
  - Reliability plan (Workstream B) consumes
    `za_cols_reference_values.csv` for the slack-penalty handoff in
    Module 13.

## 08 Fleet Reconciliation And Custom Powerplants — 2026-05-11 17:02

- **Status:** complete
- **Decisions taken:**
  - **Hex 20 MW battery:** include in `custom_powerplants.csv` as the only
    V1 battery row (carrier `battery_4h`, COD 2023, decommissioning 2038).
    Audit row 782 carries `included_2023 == True`.
  - **Redstone Solar Thermal:** exclude — DateIn 2024, outside 2023 baseline.
    All three Redstone audit rows in scenarios BASE / IRP23_FULL / AMBITIONS
    have commissioning_year=2024.
  - **PHS storage hours:** write per-station `StorageCapacity_MWh` from
    PyPSA-RSA `Max Storage (GWh)` column. Audit values supersede the V1
    reference table — Drakensberg=21.7 GWh, Ingula=27.4 GWh, Palmiet=10 GWh,
    Steenbras=2.7 GWh. Upstream `add_electricity.py:1027` only replaces
    `max_hours == 0` with the 6h config default, so audit-derived values
    survive the pipeline.
  - **CSP — six 2023 plants:** include via PyPSA-RSA fixed_technologies
    BASE scenario. Audit names retained verbatim: `Kaxu Solar One`,
    `Khi Solar One`, `Bokpoort CSP project`, `!XiNa Solar One`,
    `Karoshoek Solar One` (also known as Ilanga CSP-1), `Kathu Solar Park`.
    Total = 500 MW. CSP storage hours stored in
    `za_named_plant_inventory.csv` notes for Module 10 to consume — NOT
    written into `StorageCapacity_MWh` per plan (Module 10 owns
    `renewable.csp.csp_model`).
  - **Scenario filter:** `scenario_set == "ME IRP 2024" AND Scenario == "BASE"`.
    The `Coal_Flexibilisation` scenario set is excluded from V1.
  - **bus column blank:** leave `bus` empty for every row in Module 08;
    upstream KDTree assigns substation via `scripts/build_powerplants.py:362-367`.
    Module 09 finalises explicit bus assignments.
  - **`electricity.powerplants_filter`:** set to
    `(DateOut >= 2022 or DateOut != DateOut) and (DateIn <= 2023 or DateIn != DateIn)`
    so the pipeline keeps rows operational in 2023.
  - **Eskom anchors:** derived per-carrier 2023 max installed-capacity from
    the raw hourly feed (`raw/eskom_data_2023_full.csv`). Only renewable
    carriers (Wind, PV, CSP, Other RE) and `Installed Eskom Capacity` are
    exposed in the hourly file; conventional carriers (coal/nuclear/
    OCGT/Sasol) are recorded as `available: False` — Module 12 must use
    Eskom Annual Report 2023 / IRP 2023.
- **Deviations from plan:**
  - Plan claimed "upstream loader reads the CSV without `index_col=0`".
    Actual `scripts/build_powerplants.py:252` uses
    `read_csv_nafix(custom_powerplants, index_col=0, dtype={"bus":"str"})`.
    Verified — `Name` becomes the index, which matches the
    `pm.powerplant.to_pypsa_names()` contract downstream.
  - Plan asked for ≥30 stations in named inventory; delivered 30. The CSP
    plant called `Ilanga CSP` in the plan is the audit's
    `Karoshoek Solar One` (alternate trade name for Ilanga CSP-1 at
    Postmasburg, 100 MW, COD 2018) — recorded in the inventory `source`
    field.
  - Mondi biomass (120 MW, audit `included_2023=False`, no GPS coords in
    audit) excluded from `custom_powerplants.csv` because upstream KDTree
    bus assignment requires finite lat/lon. Logged as V1 limitation.
- **Source inputs used:**
  - `data/za_audit/pypsa_rsa_fixed_technologies_2023_candidates.csv`
    (1211 rows, scenario_set=ME IRP 2024/Scenario=BASE active-2023 filter
    → 150 rows).
  - `data/za_audit/reipppp_wind_2023_candidates.csv` (71 rows,
    `included_2023 == True` → 71 rows).
  - `data/za_audit/reipppp_solar_2023_candidates.csv` (65 rows,
    `included_2023 == True` AND Type ∈ PV → ~65 rows; CSP rows skipped
    because the PyPSA-RSA path retains storage metadata).
  - `data/za_audit/raw/eskom_data_2023_full.csv` for anchor derivation
    (10272 raw rows → 8760 clean 2023 hourly observations).
  - `data/za_audit/za_carrier_taxonomy.csv` (16 carrier rows).
- **Output artifacts produced:**
  - `data/custom_powerplants.csv` — 227 rows (was header-only).
  - `data/za_audit/za_powerplant_reconciliation.csv` — 229 rows.
  - `data/za_audit/za_named_plant_inventory.csv` — 30 rows.
  - `data/za_audit/za_eskom_2023_capacity_anchors.csv` — 17 rows
    (5 renewables `available=True`, 12 conventional `available=False`).
  - `data/za_audit/za_phs_storage_hours.csv` — 4 rows.
  - `data/za_audit/za_powerplants_normalization_diff.csv` — 227 rows,
    all `status == "ok"` after `build_powerplants` smoke.
  - `doc/za_powerplant_reconciliation.md` — canonical reconciliation report.
  - `notebooks/za_validation/08_fleet/fleet_overview.ipynb` (executed) +
    `doc/za_validation/figures/08_fleet/fleet_overview.html` (294,329 bytes).
- **Verification completed:**
  - YAML parse: pass.
  - Direct CLI run: pass with summary
    `{reconciliation: 229, custom: 227, named: 30, anchors: 17, phs: 4,
    diff_rows: 227, named_failures: 1}`.
  - Snakemake dry-run: 1 job.
  - Snakemake force exec: 100% complete.
  - Idempotency: re-run = "Nothing to be done".
  - Schema check: header matches plan exactly; `Name` unique;
    `Country == "ZA"` on every row; `DateIn` populated on every row.
  - Named-plant gate: **28 matches, 1 failure**.
    - Hendrina capacity-weighted centroid distance 25 km exceeds ±10 km.
      Root cause: audit `Hendrina**` row carries coordinates
      `(-26.62, 30.09)` (≈Camden area), not the real Hendrina site at
      `(-26.03, 29.60)`. Flagged for Module 04 follow-up; capacity sum
      (1098 MW) matches the expected value within ±0 MW.
  - PHS verification: all four PHS rows have non-empty
    `StorageCapacity_MWh` (21700, 27400, 10000, 2700 MWh) and survive
    `build_powerplants` smoke (verified in
    `resources/za_2023_fixed_validation/powerplants.csv`).
  - Hex battery present: exactly one row with `Name="Hex"`,
    `Fueltype="Battery"`, `Capacity=20.0`, `DateIn=2023`.
  - Redstone absent: zero rows.
  - CSP six rows summing to 500 MW: pass.
  - Smoke build (`snakemake build_powerplants`): success in 4 seconds.
    Output `resources/za_2023_fixed_validation/powerplants.csv` contains
    227 rows (matches custom_powerplants count).
  - Smoke diff: all 227 rows `status == "ok"`. No `dropped_by_filter`,
    `carrier_remapped`, `capacity_shifted`, or `unintended_addition` rows
    — `custom_powerplants: replace` correctly blocks powerplantmatching
    IRENA additions.
  - Anchor cross-check (informational): Wind anchor max 3442.57 MW from
    hourly feed vs custom 6890 MW. The Eskom hourly "Wind Installed
    Capacity" appears to track Eskom-contracted utility wind only (not
    full national fleet including REIPPPP). Documented for Module 12 to
    reconcile.
  - Notebook execution + HTML export passed (`fleet_overview.html`,
    294,329 bytes).
  - `bus` column policy: blank in Module 08 — verified KDTree assigns bus
    in smoke (227/227 rows have non-null bus in
    `resources/za_2023_fixed_validation/powerplants.csv`).
- **Open follow-ups:**
  - **Module 04 audit-quality issues to address:**
    - `Hendrina**` row has wrong coordinates `(-26.62, 30.09)` — flag for
      Module 04 re-extraction.
    - `Medupi*` and `Medupi**` rows have coords `(-23.42, 27.33)` instead
      of real Lephalale at `(-23.69, 27.61)` (~30 km off) — flag.
    - `Drakensberg` audit coord `(-28.56, 29.08)` differs from real
      Bergville site `(-28.76, 29.05)` by ~22 km — flag.
    - `Mondi` biomass row has no GPS coordinates — Module 04 should
      backfill from Eskom Annual Report (Richards Bay / Felixton).
  - **Module 09** finalises `bus` per audited substation; will overwrite
    blank values in `custom_powerplants.csv`. Module 10 consumes only the
    finalised values.
  - **Module 10** owns:
    - `apply_za_local_carriers` hook that maps `sasol_coal`/`sasol_gas`/
      `ocgt_diesel`/`ocgt_gas` Name-prefixed rows to the V1 local carrier
      identity post `add_electricity`.
    - `renewable.csp.csp_model` configuration; CSP storage hours from
      `za_named_plant_inventory.csv` notes must be wired here.
    - `other_re` Generator attachment from Module 06 time series (no
      custom_powerplants row).
  - **Module 11** dispatch validation must verify per-PHS-station
    `max_hours` derivation. If upstream `pm.powerplant.to_pypsa_names()`
    drops `StorageCapacity_MWh`, patch the local carrier hook to
    re-inject `max_hours = StorageCapacity_MWh / p_nom` before
    `aggregate_ppl_by_bus_carrier_year` runs.
  - **Module 12** consumes:
    - `za_eskom_2023_capacity_anchors.csv` for the ≤2% renewable
      tolerance gate (Wind, PV, CSP) — the conventional anchors require
      Eskom Annual Report 2023 / IRP 2023 sources.
    - `za_powerplant_reconciliation.csv` for per-plant capacity audit.
  - **CSP storage representation** decision deferred to Module 10:
    whether `csp_model: simple` (generator only) or `csp_model: advanced`
    (atlite SAM tower model with internal thermal storage). The plan
    forbids modifying `custom_powerplants.csv` schema for CSP storage.
  - **Carrier coverage limitations vs taxonomy:**
    - `ror` (run-of-river hydro): zero rows in PyPSA-RSA fixed_technologies
      (audit lacks `ror`/`run-of-river` carrier values). SA ror capacity is
      <50 MW small-scale and is accepted as a V1 limitation. Module 10
      hook does not need to attach ror generators.
    - `ocgt_gas`: zero rows in BASE scenario. The four gas-converted units
      (Acacia, PortRex) only appear under `ocgt_gas` in the `AMBITIONS_LC`
      scenario; under BASE they retain `ocgt_avf` (mapped to `ocgt_diesel`
      for V1). Module 10 hook reads `za_local_carriers.ocgt_gas` config
      block but should expect zero plants for V1 — recorded as a deferred
      decision for Module 11 sensitivity analysis.

## 09 Grid Spatial And Transmission Model — 2026-05-11 17:46

- **Status:** complete
- **Decisions taken:**
  - **Spatial level locked to 34 Eskom local areas** (Stage 4b, per `pre-implementation-decisions.md` Q2). No fallback to 10 regions. `za_spatial_level_lock.csv` records `level=34`, layer hash `eacd403aaf70ea1e...`.
  - **V1 busmap path = custom busmap** (`enable.custom_busmap: true` merged into the existing `enable:` block in `configs/za/za_2023_fixed_validation.yaml`). Custom subregion shapes (`subregion.method`) stays `false`. The 34-cluster target is resolved at CLI time via the path wildcard `networks/{run}/elec_s_34.nc` — no `scenario:` or `cluster_options:` override added to the overlay.
  - **YAML duplicate-key guard:** `custom_busmap: true` is merged into the existing `enable:` block at lines 45-47 of the overlay, not appended as a second `enable:` block (PyYAML `safe_load` silently overwrites duplicate keys; verified prior to wiring).
  - **St Clair coefficients:** `(53.736, -0.65)` from pypsa-rsa `scripts/build_topology.py:241-253`. Differs from literature-standard Dunlop fit `(43.261, -0.6678)`. The pypsa-rsa value is used verbatim for consistency with the reference model; the discrepancy is documented in `doc/za_grid_reconciliation.md` and in this log.
  - **Thermal/SIL/s_max_pu/n1 values pinned** from pypsa-rsa `config.yaml:146-162` (commit `89872c1ea703af3d8a3f198706d1ab7958f50a5f`). Thermal MW: 220→492, 275→921, 400→1788, 765→5512. SIL MW: 220→122, 275→245, 400→602, 765→2280.
  - **N-1 derating** applied per pypsa-rsa rule: single-line corridor × 0.7; multi-line corridor drops the strongest line then sums the rest (no further 0.7 factor). Implemented inline in `scripts/za_grid_spatial/rsa_corridors.py:build_corridor_table`.
  - **Endpoint→region assignment** uses `gpd.sjoin(predicate='within')` over the 34 supply-region polygons (EPSG:4148 source, reprojected to EPSG:4326). Lines whose endpoints fall in the same region or fail to assign are dropped before grouping.
  - **Plant bus back-fill** (per Module 08 hand-off contract): `custom_powerplants.csv` `bus` column blank rows filled via point-in-polygon against 34-region layer with nearest-centroid fallback in EPSG:32735. All 227 plants assigned; no row left blank. Audit CSV `za_plant_bus_assignment.csv` records every assignment with original Module 08 blank-flag.
  - **Custom busmap CSV format:** index = simplified PyPSA-Earth bus id (str), value = 34-region `LocalArea` name. Consumed by `scripts/cluster_network.py:796-800` via `pd.read_csv(path, index_col=0).squeeze()`.
  - **Demand / other_re bus attachment** uses 34-region area-share weights (audit-only). Active disaggregation remains in `scripts/build_demand_profiles.py` via GDP/POP layouts — Module 09 does not change the demand pipeline.
  - **Import/export attachment** uses `Polokwane` as V1 proxy frontier for `International Imports` (Cahora Bassa HVDC routing via Apollo substation). Documented as proxy in `za_import_export_bus_attachment.csv` `notes_module09` column.
- **Deviations from plan:**
  - `from __future__ import annotations` removed from `scripts/build_za_grid_spatial.py` because Snakemake's `script:` directive prepends the rule preamble before user imports, which violates the "must occur at beginning of file" constraint. The submodule files still use it (they are imported, not script-injected).
  - The plan listed `cluster_options:` and `scenario:` blocks in the overlay; both are dropped because (a) `config.default.yaml` already sets `alternative_clustering: false` and the upstream `aggregation_strategies`, and (b) Snakemake resolves `{clusters}=34` from the path wildcard. No overrides needed for Module 09 gates.
  - Module 09 does NOT yet apply MTS hosting limits as `n.lines.s_nom` caps; the plan defers this to Module 10. Module 09 only writes the corridor cap registry `za_rsa_interregional_transfer_limits.csv` for Module 10 to consume.
  - Validation notebook added (user-opted-in) even though `00_governance_and_scope.md` validation-notebook table omits Module 09.
- **Source inputs used:**
  - `data/bundle/supply_regions/rsa_supply_regions.gpkg` layer `34` (34 features, pypsa-rsa pinned commit `89872c1ea703af3d8a3f198706d1ab7958f50a5f`, hash `eacd403aaf70ea1e...`).
  - `data/za_audit/za_rsa_existing_lines_220kv_plus.geojson` (324 features ≥ 220 kV, Module 04 output, hash `4fb775abd47ed5e9...`).
  - `data/za_audit/za_rsa_supply_area_connection_limits.csv` (30 rows, Module 04, hash `a5f1ec2c36bbf26a...`).
  - `data/za_audit/za_rsa_mts_hosting_limits.csv` (198 rows, Module 04, hash `19d94b53a5fdc0b3...`).
  - `data/za_audit/za_2023_load_allocation_weights.csv` (Module 06, hash `d1b0060e25d065a1...`).
  - `data/za_audit/za_2023_import_export_attachment.csv` (Module 06, hash `9066189c6adfbbd7...`).
  - `data/za_audit/za_2023_other_re_attachment.csv` (Module 06, hash `fef2ad3e86122166...`).
  - `data/custom_powerplants.csv` (227 rows, Module 08 output) — back-filled in place.
  - `networks/za_2023_fixed_validation/base.nc` (PyPSA-Earth OSM base network).
  - `networks/za_2023_fixed_validation/elec_s.nc` (simplified network, 803 buses after stub removal).
  - pypsa-rsa parameter references: `scripts/build_topology.py:241-253` (St Clair calc), `config.yaml:146-162` (thermal/SIL/s_max_pu/n1_approx).
- **Output artifacts produced:**
  - `scripts/build_za_grid_spatial.py`
  - `scripts/za_grid_spatial/__init__.py`
  - `scripts/za_grid_spatial/io.py`
  - `scripts/za_grid_spatial/supply_regions.py`
  - `scripts/za_grid_spatial/osm_summary.py`
  - `scripts/za_grid_spatial/rsa_corridors.py`
  - `scripts/za_grid_spatial/busmap.py`
  - `scripts/za_grid_spatial/bus_attachments.py`
  - `scripts/za_grid_spatial/reconciliation.py`
  - `scripts/za_grid_spatial/lock.py`
  - `Snakefile` (added `build_za_grid_spatial` rule between `build_za_fleet_reconciliation` and `clean`).
  - `configs/za/za_2023_fixed_validation.yaml` (merged `custom_busmap: true` into existing `enable:` block; appended `za_grid_spatial` provenance block).
  - `data/custom_busmap_elec_s_34.csv` — 803 buses → 34 region names.
  - `data/custom_powerplants.csv` — 227 rows; `bus` column now populated for every row.
  - `data/za_audit/za_pypsa_earth_osm_grid_summary.csv` — 12 rows (totals + per-voltage-bucket breakdown).
  - `data/za_audit/za_rsa_interregional_transfer_limits.csv` — 65 corridors with thermal/SIL/St Clair/St Clair N-1 capacities.
  - `data/za_audit/za_grid_reconciliation.csv` — 7 rows OSM vs RSA voltage-bucket comparison.
  - `data/za_audit/za_spatial_level_lock.csv` — locks level 34.
  - `data/za_audit/za_plant_bus_assignment.csv` — 227 rows (one per plant + Module-08-blank flag).
  - `data/za_audit/za_demand_bus_attachment.csv` — 1530 rows (45 source declarations × 34 regions).
  - `data/za_audit/za_import_export_bus_attachment.csv` — 48 rows.
  - `data/za_audit/za_other_re_bus_attachment.csv` — 1530 rows.
  - `data/za_audit/za_custom_busmap_coverage.csv` — 7 metrics (gate pass: 0 unassigned, 0 orphan regions, 23.6 buses/region mean).
  - `doc/za_grid_reconciliation.md` — canonical reconciliation report including St Clair discrepancy note.
  - `notebooks/za_validation/09_grid/grid_reconciliation.ipynb` (executed) + `doc/za_validation/figures/09_grid/grid_reconciliation.html` (1,099,710 bytes).
- **Verification completed:**
  - YAML parse: pass (`enable.custom_busmap=True`, `za_grid_spatial.*` block fully populated).
  - Snakemake dry-run: 1 job (Module 09 alone) when deps are fresh; cascades into ~10 upstream jobs when deps are stale.
  - Snakemake force exec: `1 of 1 steps (100%) done` (first run); subsequent runs touch `data/custom_powerplants.csv` which triggers Module 08 re-run (known quirk).
  - Direct CLI exec: `python scripts/build_za_grid_spatial.py --configfile configs/za/za_2023_fixed_validation.yaml` returns `{level: 34, regions: 34, osm_summary_rows: 12, rsa_corridors: 65, busmap_buses: 803, busmap_regions_used: 34, plant_assignments: 227, plants_backfilled: 227, demand_rows: 1530, import_export_rows: 48, other_re_rows: 1530}`.
  - Coverage gate: `unassigned_buses=0, orphan_regions=0, n_target_regions=34, n_used_regions=34, buses_per_region_mean=23.618`. Pass.
  - Busmap shape gate: 803 simplified buses → 34 unique region names. Pass.
  - Plant back-fill gate: all 227 plants in `custom_powerplants.csv` have non-blank `bus`. Pass.
  - End-to-end clustering smoke gate: `snakemake networks/za_2023_fixed_validation/elec_s_34.nc` produced 34 buses (matching Eskom local-area names: `Bloemfontein, Carletonville, East London, …`), 72 lines, 109 generators, 34 loads. Custom busmap consumed cleanly by `cluster_network.py`. Pass.
  - Notebook execution + HTML export: pass (`grid_reconciliation.html`, 1,099,710 bytes; 4 image alt-text warnings, non-blocking).
- **Open follow-ups:**
  - **Module 10** consumes `za_rsa_interregional_transfer_limits.csv` to apply `n.lines.s_nom = st_clair_n1_mw` per corridor AFTER `cluster_network`, plus `za_rsa_mts_hosting_limits.csv` for per-region transfer caps (`Supply_Areas2022_Steady_State_Limit`). Module 09 only writes the registry tables; no post-cluster hook implemented here.
  - **Module 10** must also wire the `apply_za_local_carriers` hook (deferred from Module 05/08); plant bus back-fill in Module 09 leaves this contract intact.
  - **DAG re-run quirk:** because Module 09 writes back into `data/custom_powerplants.csv` (which is also an output of `build_za_fleet_reconciliation`), Snakemake treats it as upstream-touched on the next invocation and rebuilds Module 08 (and downstream) when `-F` is used. Mitigation: run Module 09 normally (no `-F`); subsequent `snakemake build_za_grid_spatial` reports `Nothing to be done` once outputs settle.
  - **Import/export proxy:** V1 attaches all `International Imports` rows to `Polokwane` for Cahora Bassa routing. Module 13 (expansion handoff) may refine using a per-interconnector table once a 765 kV HVDC node is exposed in the OSM/Eskom corridor data.
  - **Demand / other_re weights** use 34-region polygon area share for audit; active model disaggregation remains in `build_demand_profiles.py`. Module 12 reconciliation must NOT use the audit CSV as the demand allocation — it is provenance only.
  - **`from __future__ import annotations` quirk:** the orchestrator (`build_za_grid_spatial.py`) cannot use this future import because Snakemake's `script:` directive injects code before user imports. Submodule files keep the future import. Recorded for module-template reuse.
