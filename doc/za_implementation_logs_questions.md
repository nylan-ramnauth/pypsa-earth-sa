
Overall, explain me the purpose of every output artifacts produced

## 01

- What was changed in the snakefile and why?
- How does the `za_2023_fixed_validation.yaml`overrides the main config file?
- What is the purpose of the `za_environment.yaml`and where is it called?

## 02

- Why did you add an explicit Snakemake rule `build_za_eskom_validation_data` and what does it do exactly?
- what is the `build_za_eskom_validation_data.py`?

# 03

- Should we always stick to `cutout-2023-era5`? Is there any other option?
- What does it mean that you verified: "PyPSA-Earth resolves `renewable.csp.cutout: auto` to `cutout-2023-era5`; CSP is a separate `csp` carrier and is not merged into PV."?
- What does the rule `validate_za_renewable_profiles`does?
- `build_powerplants` report no hydro? But in my former runs with PyPSA-Earth on South Africa, I had a bit of hydro so what is the reason? was this only RoR plants?
- what does the `za_atlite_renewable_profile_validation.csv`do? and the `technical_potential`one?

# 04

- What does the Snakemake rule `build_za_source_audits`is doing exactly?
- if in the end we want to model the year 2024 instead, will we have the data and we can change the commissioning data later?
- Why do we keep only above 220kV lines?
- So the only layer you did not find is 27 right? you find 34 regions in the Local Area files?
- what is the consequence of the `renewables_profiles_updated.nc`opening as an empty xarray Dataset?
- why `reippp_phs_data.csv`is absent at pin? this is not part of the repo?
- Give me a short but clear explanation of all the artifacts produced?
- What is the difference between the `powerplants_pm_za_full.csv`and the `powerplants_pm_za_audit.csv`?
- What is exactly `pypsa_rsa_fixed_technologies_2023_candidates.csv`?
- What is `pypsa_rsa_availability_audit.csv`?

# 05

- What is `sasol`?
- Explain all artefacts produced and what is their purposes
- In `v1_carrier`this generator has no name in the notebook, what is this? It has 10878.00 MW capacity
- Why onwind, solar and hydro_import have more capacity than coal?

# 06

- Why did you do it like this? "Built demand weights for candidate layers `1`, `10`, and `34` with PyPSA-Earth-style GADM area-overlay allocation using normalized `0.6 * gdp + 0.4 * pop`."
- Explain why you do this: Treated `Other RE` as a curtailable local generator input for module 10: `p_nom = 50.58 MW`, `p_max_pu = Other RE / p_nom`, clipped to `[0, 1]`, and `p_min_pu = 0`.
- How to solve this? PyPSA-RSA regional `GVA_2016`/`POP_2016` diagnostics are available for the national layer only. The actual audited PyPSA-RSA 10- and 34-region layers do not contain regional `GVA_2016`/`POP_2016` columns, so `pypsa_rsa_gva_pop_load_weight_comparison.csv` records 1 available diagnostic row and 44 `diagnostic_unavailable` rows instead of inventing regional PyPSA-RSA weights.
	- Should we retrieve another GVA/Pop?
	- Isn't Earth also retrieving the population data directly? It has weight too?
