# South Africa 2023 Renewable Profile Validation

**Module:** 03 Weather Cutout And Profiles

## Cutout

- Cutout: `cutouts/cutout-2023-era5.nc`
- SHA256: `0c6b22fa6b8a0a469cc24460df2014fdb9c041035985dfb3b1aa7d6608e19076`
- Decision: existing cutout reused because recorded hash/provenance and 8760-hour 2023 coverage verified.

## Validation Summary

- Status counts: `{'pass': 29, 'warn': 4}`
- CSP remains a separate `csp` carrier using the native atlite CSP method; it is not merged into PV.
- Technical-potential and full-load-hour comparisons are diagnostics only. No correction factors or resource scaling were applied.

## GEGIS 2023 Custom Weather-Year String

- Status: `pass`
- Returned paths: `data/ssp2-2.6/2030/era5_2023_custom/Africa.csv`
- Notes: accepted 2023_custom string

## Carrier Technical Potential

| carrier   | profile_path                                                            |   hours |   p_nom_max_mw |   technical_potential_twh |   full_load_hours |      area_km2 |   installable_power_density_mw_per_km2 | comparison_sources                                                                                   | sanity_status   | notes                                                             |
|:----------|:------------------------------------------------------------------------|--------:|---------------:|--------------------------:|------------------:|--------------:|---------------------------------------:|:-----------------------------------------------------------------------------------------------------|:----------------|:------------------------------------------------------------------|
| solar     | resources/za_2023_fixed_validation/renewable_profiles/profile_solar.nc  |    8760 |    4.70768e+06 |                   7179.54 |           1525.07 |   1.02341e+06 |                                  4.6   | Eskom 2023 validation targets; public/literature sanity anchors deferred to module 04 evidence audit | pass            | diagnostic only; no correction factors or profile scaling applied |
| onwind    | resources/za_2023_fixed_validation/renewable_profiles/profile_onwind.nc |    8760 |    3.09432e+06 |                   5436.63 |           1756.97 |   1.03144e+06 |                                  3     | Eskom 2023 validation targets; public/literature sanity anchors deferred to module 04 evidence audit | pass            | diagnostic only; no correction factors or profile scaling applied |
| hydro     | resources/za_2023_fixed_validation/renewable_profiles/profile_hydro.nc  |       1 |  nan           |                      0    |            nan    | nan           |                                nan     | Eskom 2023 validation targets; public/literature sanity anchors deferred to module 04 evidence audit | warn            | diagnostic only; no correction factors or profile scaling applied |
| csp       | resources/za_2023_fixed_validation/renewable_profiles/profile_csp.nc    |    8760 |    2.42246e+06 |                   3452.27 |           1425.11 |   1.01273e+06 |                                  2.392 | Eskom 2023 validation targets; public/literature sanity anchors deferred to module 04 evidence audit | pass            | diagnostic only; no correction factors or profile scaling applied |

## Warnings And Failures

| carrier   | check                        | status   | value   | unit   | notes                                                                                                                      |
|:----------|:-----------------------------|:---------|:--------|:-------|:---------------------------------------------------------------------------------------------------------------------------|
| hydro     | time_coverage                | warn     | 1       | hours  | first=None; last=None; time dimension has no coordinate                                                                    |
| hydro     | plant_count                  | warn     | 0       | plant  | upstream hydro profile is empty because build_powerplants found no ZA plants; fleet reconciliation is owned by module 08   |
| hydro     | finite_values                | warn     |         |        | upstream hydro profile is empty because build_powerplants found no ZA plants; fleet reconciliation is owned by module 08   |
| hydro     | annual_availability_vs_eskom | warn     | 0.0     | ratio  | availability_twh=0.0; observed_twh=1.991804788; availability potential is below observed Eskom generation; diagnostic only |
