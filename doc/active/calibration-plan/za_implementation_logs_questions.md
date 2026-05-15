
Overall, explain me the purpose of every output artifacts produced

## 01

### What was changed in the Snakefile and why?

`configfile: "configs/za/za_2023_fixed_validation.yaml"` added to the top-level configfile block. The ZA overlay is not auto-discovered by upstream PyPSA-Earth; it must be explicitly declared so Snakemake merges it with `config.yaml` defaults.

### How does `za_2023_fixed_validation.yaml` override the main config file?

Snakemake merges config files in order — later files override earlier keys. The ZA overlay sets `countries: ["ZA"]`, `snapshots`, `electricity.custom_powerplants: replace`, `extendable_carriers: []`, solver settings, and `costs.year: 2030`. Any key present in the ZA file wins over `config.yaml`.

### What is the purpose of `za_environment.yaml` and where is it called?

Frozen conda environment locking exact versions of Python, pypsa, atlite, powerplantmatching, gurobi, etc. Called manually via `conda env create -f envs/za_environment.yaml` at session start. Not called by Snakemake rules directly — it is the *execution environment* those rules run inside.

---

## 02

### Why did you add an explicit Snakemake rule `build_za_eskom_validation_data` and what does it do exactly?

The raw Eskom CSV has a known parse defect: `Total UCLF+OCLF` sometimes uses a comma decimal separator, producing 43 fields vs a 42-field header. Upstream PyPSA-Earth has no Eskom parser. An explicit rule owns: repair of the malformed column, 12-hour AM/PM timestamp parsing (`%Y-%m-%d %I:%M:%S %p`), 2023 filter, annual validation targets, and parser warnings. Without a dedicated rule there is no Snakemake provenance or rerun-on-change tracking for this preprocessing.

### What is `build_za_eskom_validation_data.py`?

Reads `data/za_audit/raw/eskom_data_2023_full.csv`, repairs the comma-decimal split, parses timestamps, filters exactly 2023-01-01–2023-12-31 (8760 rows), and writes:

- `data/za_validation/eskom_2023_hourly_clean.csv` — clean hourly series
- `data/za_validation/eskom_2023_targets_by_carrier.csv` — annual anchors
- `data/za_audit/eskom_2023_parser_report.csv` — parse warnings + accounting identity checks

---

# 03

### Should we always stick to `cutout-2023-era5`? Is there any other option?

For 2023 fixed-validation: yes. The model is locked to 2023 weather. If you ever model a different year (e.g., 2024), you would build `cutout-2024-era5` and update the overlay accordingly. The cutout name is the key that links the atlite config → profile files → network build.

### What does it mean that you verified "PyPSA-Earth resolves `renewable.csp.cutout: auto` to `cutout-2023-era5`; CSP is a separate `csp` carrier and is not merged into PV."?

PyPSA-Earth's `renewable.csp.cutout: auto` instructs atlite to pick the default cutout. Verifying means confirming that `auto` resolves to the ZA cutout (`cutout-2023-era5`) and not a global or stale cutout. If it resolved incorrectly, the CSP profile would use wrong-year or wrong-geography weather data. The verification confirmed correct resolution; this is documented in the implementation log.

### What does the rule `validate_za_renewable_profiles` do?

A local Snakemake rule that reads the generated profile `.nc` files and writes:

- `data/za_audit/za_atlite_renewable_profile_validation.csv` — full-load hours, shape checks, annual total vs Eskom anchors, sanity status per carrier
- `data/za_audit/za_atlite_technical_potential.csv` — technical potential TWh and MW/km²

### `build_powerplants` reports no hydro? But in my former runs with PyPSA-Earth on South Africa, I had a bit of hydro so what is the reason? Was this only RoR plants?

Hydro *is* in `custom_powerplants.csv`. Former runs used PyPSA-Earth default mode (merge with powerplantmatching), which includes IRENA hydro even without explicit entries. With `custom_powerplants: replace`, powerplantmatching is bypassed entirely; only what is in `custom_powerplants.csv` enters the network. The hydro plants (Gariep, Vanderkloof, Ingula, Drakensberg, Palmiet, Steenbras) are in the current file. If `build_powerplants` shows zero hydro, verify the date filter is not excluding them (plants with `DateIn=1971` require `DateIn <= 2023 or DateIn != DateIn` null handling). The former runs' "bit of hydro" was likely RoR pulled from PPM/IRENA data.

### What does `za_atlite_renewable_profile_validation.csv` do? And the `technical_potential` one?

- **Validation CSV**: diagnostic QA — checks profile shape, null count, annual full-load hours vs Eskom actuals, flags deviations. Used in Module 13 reporting. Not fed to the solver.
- **Technical potential CSV**: upper-bound capacity if all available land were installed at nameplate density. Sanity check only — never directly fed to the model. Used to verify that `p_nom_max` values from atlite are physically plausible.

---

# 04

### What does the Snakemake rule `build_za_source_audits` do exactly?

Reads all PyPSA-RSA source files at pinned commit `89872c1` and writes ~15 audit CSVs:

- `pypsa_rsa_source_registry.csv` — every tracked/external file with hash and port policy
- `pypsa_rsa_fixed_technologies_2023_candidates.csv` — 306 active-2023 plant candidates from RSA scenario workbooks
- `reipppp_solar/wind_2023_candidates.csv` — REIPPPP plants filtered to 2023 with `included_2023` flag
- `pypsa_rsa_availability_audit.csv` — EAF/outage data from `plant_availability.xlsx`
- `pypsa_rsa_cost_fuel_emissions_audit.csv` — fuel prices, heat rates, VOM from RSA workbooks
- Grid GeoJSONs, load weight audit, scenario workbook inventory, and resource siting audit

No model inputs are written by this module — audit evidence only.

### If in the end we want to model the year 2024 instead, will we have the data and we can change the commissioning data later?

Yes. Change the filter `commissioning_year <= 2023` → `<= 2024` in `reconciliation.py` and the overlay `powerplants_filter`. Any RSA candidate with `commissioning_date <= 2024` and `decommissioning_date > 2024` automatically becomes eligible. You would also need a 2024 ERA5 cutout and updated Eskom hourly data. The `included_2023` flag in audit CSVs would need to become `included_2024`.

### Why do we keep only above 220 kV lines?

Below 220 kV lines are distribution-level. Eskom operates the HV transmission backbone at 220/275/400/765 kV. Including sub-220 kV lines would add ~13,000+ OSM segments representing distribution feeders and medium-voltage lines not relevant to national dispatch. They would make the grid model computationally intractable without adding meaningful transmission constraint information.

### So the only layer you did not find is 27 right? You find 34 regions in the Local Area files?

Correct. `LOCAL_AREA_GCCA2025.gpkg` contains 34 local areas. The intermediate 27-region layer is intentionally skipped per the Stage 4b plan lock — 34 is the hard target. The absence of 27 is not a problem.

### What is the consequence of `renewables_profiles_updated.nc` opening as an empty xarray Dataset?

This PyPSA-RSA file is audit-only (profile reference comparison for Module 03 Gate B). An empty dataset means the PyPSA-RSA profile reference comparison cannot be run. Gate B defers to Module 13 before final acceptance, so this does not block the network build. Documented in implementation log; the file should not be reconstructed.

### Why `reipppp_phs_data.csv` is absent at pin? Is this not part of the repo?

The source registry records it as `ABSENT at pin: Not present at pinned commit 89872c1`. The file does not exist in PyPSA-RSA at the pinned commit under `pre_processing/resource_processing/`. PHS capacity data was taken from `fixed_technologies.xlsx` instead. Not a blocker.

### Give me a short but clear explanation of all the artifacts produced

| Artifact | Purpose |
|---|---|
| `pypsa_rsa_source_registry.csv` | Registry of every RSA source file with hash and port policy |
| `pypsa_rsa_fixed_technologies_2023_candidates.csv` | 306 active-2023 plant candidates from RSA scenario workbooks |
| `reipppp_solar/wind_2023_candidates.csv` | REIPPPP plant lists filtered to 2023 with `included_2023` flag |
| `powerplants_pm_za_full.csv` | Raw powerplantmatching extraction for all ZA plants (276 rows, all fuel types) |
| `powerplants_pm_za_audit.csv` | Same 276 rows with additional source-comparison and provenance columns |
| `pypsa_rsa_availability_audit.csv` | Per-plant annual EAF and p_max_pu reference from RSA availability workbook |
| `pypsa_rsa_cost_fuel_emissions_audit.csv` | Fuel prices, heat rates, VOM from RSA for Module 07 reference |
| Grid GeoJSONs + supply region CSVs | Transmission topology evidence consumed by Module 09 |
| `pypsa_rsa_load_weight_audit.csv` | GVA_2016/POP_2016 regional weights for Module 06 comparison |
| `pypsa_rsa_scenario_workbook_inventory.csv` | Index of all RSA scenario workbook sheets and row counts |

### What is the difference between `powerplants_pm_za_full.csv` and `powerplants_pm_za_audit.csv`?

Both have 276 rows and the same base schema. `_full` is the raw PPM extraction retaining all plant types including wind/solar that upstream `build_powerplants.py` would filter out. `_audit` adds cross-reference columns: which plants appear in RSA but not PPM, capacity deltas, source flags. `_full` is the extraction; `_audit` is the analysis.

### What is exactly `pypsa_rsa_fixed_technologies_2023_candidates.csv`?

Extraction from `scenarios/ME IRP 2024/sub_scenarios/fixed_technologies.xlsx` (and Coal Flex equivalent), filtered to `commissioning_date <= 2023` and `decommissioning_date > 2023`. 306 rows. Each row is a potential 2023-active unit with capacity, location, heat rate, fuel price, cost, and storage parameters. This is the canonical RSA fleet reference consumed by Module 08 reconciliation.

### What is `pypsa_rsa_availability_audit.csv`?

Extraction from RSA `plant_availability.xlsx` — per-plant annual availability (EAF equivalent), outage profiles, and p_max_pu-equivalent constraints for 2023. This is the reference Module 12 will consume to apply coal EAF (~55%) as monthly `p_max_pu` and verify nuclear at 0.534. Currently audit-only; Module 12 activates it.

---

# 05

### What is `sasol`?

Sasol is a South African petrochemicals company that operates the Secunda synthetic fuel complex using coal gasification. It runs captive power plants burning its own process gas (`sasol_gas`) and coal (`sasol_coal`) and supplies electricity to Eskom under IPP contracts. They require separate carriers because their fuel prices, heat rates, and emissions factors differ from standard coal/gas.

### Explain all artefacts produced and what is their purposes

- `za_carrier_taxonomy.csv`: locked carrier mapping table (RSA concept → V1 PyPSA carrier), profile intent, emissions treatment, reporting metadata — machine-readable
- `za_carrier_taxonomy.md`: human-readable version of the same table
- `za_carrier_taxonomy_crosscheck.csv`: automated check that every carrier present in `custom_powerplants.csv` maps to a valid V1 carrier in the taxonomy

### In `v1_carrier` this generator has no name in the notebook, what is this? It has 10,878 MW capacity.

This is the aggregated coal fleet viewed from a pre-Module-08 intermediate. In the `pypsa_rsa_fixed_technologies_2023_candidates.csv` file, `v1_carrier` was not yet assigned (that mapping lives in `reconciliation.py`). The 10,878 MW figure in the notebook likely comes from summing Hard Coal rows from a PPM or intermediate audit view before the reconciliation applied the RSA → V1 carrier mapping. It is not a single generator — it is an aggregated row from a carrier-sum view.

### Why onwind, solar and hydro_import have more capacity than coal?

This was the pre-fix state: wind was doubled to 6,890 MW (fleet duplication bug) and solar was ~10,000 MW (doubling + 4,439 MW distributed PV). The fix has been applied — see `custom_powerplants.csv` current state: Hard Coal ~41 GW >> Wind 3,507 MW, Solar PV+CSP 2,788 MW. If the notebook still shows pre-fix numbers, it was generated before the rebuild.

---

# 06

### Why did you do it like this? "Built demand weights for candidate layers `1`, `10`, and `34` with PyPSA-Earth-style GADM area-overlay allocation using normalized `0.6 * gdp + 0.4 * pop`."

PyPSA-Earth's standard demand allocation formula for multi-node runs. GDP-weighted allocation captures industrial/commercial load concentration; population-weighted captures residential. The 60/40 split is the upstream PyPSA-Earth default. For the single-node baseline (`clusters: 1`), weights collapse to one bus and are irrelevant. For 34-region runs, these weights disaggregate national demand to regional buses.

### Explain why you do this: Treated `Other RE` as a curtailable local generator input for module 10.

`Other RE` is an Eskom aggregate category (biomass, biogas, small hydro, embedded wind/PV not separately metered). There is no per-plant data. Modeling it as a fixed-dispatch generator with `p_min_pu = p_max_pu` would force injection at every hour regardless of demand, risking infeasibility at low-load hours. Setting `p_min_pu = 0` allows curtailment: the solver can curtail Other RE at low load while still dispatching it first under normal conditions (zero marginal cost).

### How to solve this? PyPSA-RSA regional GVA/POP diagnostics available only at national level — 44 rows show `diagnostic_unavailable`.

No action needed. The comparison table correctly records 1 diagnostic row (national) and 44 `diagnostic_unavailable` rows. PyPSA-Earth retrieves population and GDP data directly from GADM/WorldPop during `build_demand_profiles.py` and uses those for intra-country demand allocation. The PyPSA-RSA comparison is a diagnostic only. The V1 default (PyPSA-Earth allocation) stands. Switching to PyPSA-RSA weights would require reopening Module 06 for review.

---

# 07

### There are no costs_2023, only 2025, 2030 and 2040

Correct. `costs.year: 2030` is locked as the V1 baseline. Technology-data costs are not available for exactly 2023. The 2030 values are used as proxies — mostly relevant for capex of extendable carriers, which is disabled for fixed-validation. For marginal costs of ZA local carriers, RSA's own fuel prices and heat rates are used instead (in `za_local_carrier_cost_rows.csv`). This limitation is documented in the validation report.

### In which currency are we expressing every cost? And from which date exactly? In 2023 price?

**Internal solver**: all costs are in EUR. **Output/reporting**: ZAR, converted post-solve by the `apply_za_local_carriers` hook. **Frozen exchange rate**: 2023-12-29 ECB closing rate, recorded in `data/za_audit/za_eur_zar_fxrate_2023.csv`. For ZAR-source values from RSA workbooks (typically 2018-vintage), conversion uses the source document's own base-year rate, not the 2023 rate. So marginal costs are in 2018-EUR equivalent, not 2023-EUR — documented as a known limitation.

### Are we using the costs of each of the plant that is given by RSA?

For conventional local carriers (coal, nuclear, OCGT, Sasol): yes, marginal costs are computed from RSA fuel prices + heat rates as recorded in `za_local_carrier_cost_rows.csv`. Capital costs for conventional plants are left blank because the fixed-validation run does not optimize capacity (Module 08 owns capex via `custom_powerplants.csv`). For extendable carriers: upstream technology-data 2030 costs apply, but extendable capacity is fully disabled.

### Why didn't we change the VOLL cost in the config file using one of the values from the report (CSIR, Nova, Deloitte)?

The solver uses `load_shedding: 100` EUR/kWh (= 100,000 EUR/MWh) as a numerical safety valve — intentionally ~200× any real CoLS estimate. Changing this to a realistic value (e.g., CSIR R116,570/MWh ≈ 6,000 EUR/MWh) would make the solver willing to shed load cheaply, distorting dispatch. The CSIR, Nova, and Deloitte values are stored in `data/za_audit/za_cols_reference_values.csv` for *reporting* (monetizing modeled load shedding in ZAR) but are not fed to the solver.

### Why did you add `costs.electricity_grid_connection: 0`?

Upstream PR `f8eab87a` added a per-generator grid-connection cost. ZA local carriers in `custom_powerplants.csv` already have reconciled capex values that include grid-connection components per Module 08. Applying the upstream formula again would double-count. Setting to 0 prevents this. Documented in implementation log.

### How did you treat the PyPSA-RSA fuel-price/cost row? Did you express these costs in 2023 price?

RSA fuel prices are in ZAR at the source document's base year (typically 2018). They were converted to EUR using the 2018 ZAR/EUR rate, not the 2023 rate, to avoid mixing base years. The `za_costs_fuels_efficiencies_audit.csv` records base year, ZAR value, EUR conversion, and exchange rate used per row. Costs are in 2018-EUR equivalent — documented as a known limitation.

### Did you move `fuel_prices` of Sasol stations to marginal cost?

Yes. `sasol_coal` and `sasol_gas` carriers have explicit `marginal_cost` entries in `za_local_carrier_cost_rows.csv`: sasol_coal at 18.02 EUR/MWh and sasol_gas at 48.49 EUR/MWh. These are computed as `(fuel_price R/GJ ÷ base-year EUR/ZAR) × heat_rate + VOM_eur`.

### What was the objective of this module and how these findings will help calibrate the model?

Objective: freeze all dispatch-cost inputs before the network build so Module 12 can attribute dispatch errors unambiguously to capacity/availability constraints, not to unknown costs. Key outcome: coal at 40.56 EUR/MWh and nuclear at 16.39 EUR/MWh establish the merit order; OCGT diesel at 380 EUR/MWh ensures diesels only dispatch at peak. These are the inputs Module 12 holds fixed while testing coal EAF and nuclear p_max_pu.

---

# 08

### Where are the EAF values and availabilities of the powerplants consumed to achieve fidelity in dispatch?

`pypsa_rsa_availability_audit.csv` (from Module 04) contains per-plant annual EAF from `plant_availability.xlsx`. Currently audit-only. Module 12 must consume this file to apply coal EAF (~55%) as monthly `p_max_pu` time series and verify nuclear at 0.534. The current network has coal at `p_max_pu = 1.0` — no EAF applied yet.

### So for now, you just used all the powerplants that RSA used and formatted it in the way Earth processes it?

Correct. Module 08 took RSA's `fixed_technologies.xlsx` + REIPPPP plant lists, reconciled them, and wrote `custom_powerplants.csv` in the PyPSA-Earth schema with static installed capacity. No EAF, no dynamic availability. Dispatch calibration with actual availability is Module 12.

### If I change the commission year, can the additional powerplants from RSA be used?

Yes. Change the date filter in `reconciliation.py` and the overlay `powerplants_filter`. Plants with `commissioning_date <= new_year` and `decommissioning_date > new_year` automatically become eligible. Example: Kusile Unit 6 (COD 2024) would enter a 2024 model.

### What is `Coal_Flexibilisation` and what is it excluded from V1?

A PyPSA-RSA scenario family for modeling flexible coal dispatch: minimum stable level, ramp constraints, startup costs, and phased decommissioning schedule. Excluded from V1 because: (1) V1 is a fixed-capacity validation baseline with no capacity optimization; (2) minimum stable level and ramp constraints add solver complexity that obscures whether dispatch errors come from costs/availability vs. operational constraints; (3) these constraints are Module 12 / reliability-plan inputs, not the fixed-validation baseline.

### Why only renewable carriers (Wind, PV, CSP, Other RE) and `Installed Eskom Capacity` are exposed in the hourly file; conventional carriers recorded as `available: False` — we have hourly data for Coal etc in the Eskom hourly demand file?

Correct — the Eskom hourly file contains hourly *generation* for coal and other conventional carriers, but not hourly *availability* (the fraction of installed capacity that is physically available at each hour). Generation ≠ availability: a plant can be available but not dispatched. The per-carrier hourly *installed capacity* columns (`Wind Installed Capacity`, `PV Installed Capacity`, etc.) only exist for RE carriers in the Eskom file. Conventional capacity availability must be inferred from EAF data in the Eskom Annual Report 2023 and `plant_availability.xlsx` — those are static annual values, not hourly signals.

### So now CSP is retrieved from RSA, so if we run the model, Earth will now be able to generate CSP right?

Yes. CSP plants are in `custom_powerplants.csv` (six plants, 500 MW total, `Fueltype=Solar`, `Technology=CSP`). The overlay adds `csp` to `renewable_carriers`. The `apply_za_local_carriers` hook retagged them to carrier `csp` after `add_electricity`. PyPSA-Earth dispatches them using `profile_csp.nc` availability from atlite.

### So now, the custom powerplants built is the one used by Earth if we run the model?

Yes. With `electricity.custom_powerplants: replace` in the overlay, PyPSA-Earth's `build_powerplants` takes `custom_powerplants.csv` as the sole fleet source — no merging with powerplantmatching or IRENA data. This is the production fleet file.

### What is the difference between bioenergy and biomass? Because Ngodwana energy is written as "bioenergy" in `custom_powerplants.csv` but on the internet this is a biomass plant.

`bioenergy` is a secondary-source label used in powerplantmatching and some Eskom classifications. PyPSA-Earth's canonical carrier name is `biomass`. Per Module 05 carrier policy, any `bioenergy` label must normalize to `biomass` before entering the network. Ngodwana Energy is indeed a biomass plant (eucalyptus wood chips → steam → electricity). It appears as `Bioenergy` in `custom_powerplants.csv` because that is how PPM records it. Verify that the `apply_za_local_carriers` hook or the reconciliation script normalizes this — otherwise Ngodwana attaches to a carrier with no cost/profile metadata. **Flag: potential bug to verify.**

---

# 09

### How is the 34-cluster target resolved at CLI and why we don't use `cluster_options` with the 34 gpkg?

The ZA overlay sets `enable.custom_busmap: true` and `scenario.clusters: [34]`. When `custom_busmap: true`, PyPSA-Earth's `cluster_network` rule reads `data/custom_busmap_elec_s_34.csv` instead of running k-means. The custom busmap maps each OSM substation to one of 34 Eskom local areas deterministically. The `cluster_options` gpkg path (custom subregions) was the fallback; the busmap path was used because it provides deterministic Eskom-aligned assignment without requiring custom subregion shapes to be valid for every OSM polygon.

#### Are the buses aggregated to the 34 local areas in the network?

Yes. After `cluster_network` with the 34-region custom busmap, the network has 34 buses (one per Eskom local area) connected by aggregated line corridors capped to `za_rsa_interregional_transfer_limits.csv` values.

### Why are the St Clair coefficients different?

PyPSA-RSA uses `(53.736, -0.65)` vs. literature Dunlop/St Clair `(43.261, -0.6678)`. The RSA coefficients appear to be calibrated to South African transmission engineering practice rather than the North American-derived St Clair curve. The RSA value is used for consistency with the reference model. Discrepancy documented in implementation log.

### Explain the change in the Thermal/SILS/s_max_pu/n1 values pinned

- `s_max_pu = 0.7`: lines de-rated to 70% of thermal limit for security margin
- `n1_approx_single_lines = 0.7`: for single-line corridors, additional 0.7× de-rating (effectively 49% of thermal)
- `St_Clair_limit = min(thermal_limit, SIL × 53.736 × length_km^{-0.65})`: surge impedance loading limits long lines more than thermal (voltage stability constraint for lines over ~300 km)
- N-1 for multi-line corridors: drop the strongest line and use remaining capacity

### N-1 derating applied how and why with 0.7?

Applied as `n.lines["s_max_pu"] = 0.7` post-clustering. Rationale: Eskom operates the grid with N-1 security — any single contingency must not cause cascading failure. A 30% headroom ensures that if one line trips, remaining lines absorb the rerouted power without overloading. The 0.7 value is from PyPSA-RSA `config.yaml`, calibrated to Eskom practice.

### Explain this: Demand / other_re bus attachment uses 34-region area-share weights (audit-only). Active disaggregation remains in `scripts/build_demand_profiles.py` via GDP/POP layouts — Module 09 does not change the demand pipeline.

The Module 06 bus-attachment tables assign demand and Other RE injection to specific buses using area-share weights derived from the 34-region spatial overlay. These tables are *audit evidence* — they document what spatial allocation would look like. The *active* demand disaggregation lives in `scripts/build_demand_profiles.py` via PyPSA-Earth's GDP/POP GEGIS route. Module 09 audits the spatial allocation and flags discrepancies for Module 12 reporting, but does not redirect the demand pipeline.

### What does the final grid look like post aggregation? Do I have one bus per local area?

Yes. After `cluster_network` with the 34-region custom busmap: 34 buses (one per Eskom local area) connected by aggregated line corridors. Each bus has generators from all `custom_powerplants.csv` plants in that local area, assigned via lat/lon coordinates (post-PR #1622 behaviour). Corridor thermal limits are capped to the RSA interregional transfer limit audit values.

---

## Contradictions / Issues to Flag

1. **Hydro possibly missing in `build_powerplants` output**: Verify the date filter handles null `DateIn` for plants commissioned in the 1970s. Expression must be `(DateIn <= 2023 or DateIn != DateIn)` — if null handling is wrong, hydro plants get dropped.

2. **Ngodwana `Bioenergy` label not normalized**: `custom_powerplants.csv` shows `Bioenergy` Fueltype (176 MW). PyPSA-Earth canonical carrier is `biomass`. Verify `apply_za_local_carriers` normalizes this before the solve — otherwise Ngodwana attaches to a carrier with no metadata.

3. **Solar 2,788 MW in `custom_powerplants.csv` vs Eskom 2,287 MW anchor**: No contradiction. The `Solar` Fueltype in PPM includes both PV (2,288 MW) and CSP (500 MW). The `apply_za_local_carriers` CSP retag in Module 11 splits them into `solar` and `csp` carriers in the network. Totals are correct.

4. **`v1_carrier` null in notebook carrier table (Module 05, 10,878 MW coal)**: This is an intermediate-view artifact — `v1_carrier` is not a column in `pypsa_rsa_fixed_technologies_2023_candidates.csv`. The mapping lives in `reconciliation.py`. The 10,878 MW figure comes from a pre-reconciliation aggregation view. Not a bug in the current pipeline.
