# 03 Weather Cutout And Profiles

## Goal

Build physically based 2023 South Africa renewable availability profiles using
PyPSA-Earth/atlite before any fixed dispatch validation.

## PyPSA-Earth Additions

Add or fill the local cutout config in `configs/za/za_2023_fixed_validation.yaml`:

```yaml
run:
  name: za_2023_fixed
enable:
  retrieve_cutout: false
  build_cutout: true
snapshots:
  start: "2023-01-01"
  end: "2024-01-01"
atlite:
  default: cutout-2023-era5
  cutouts:
    cutout-2023-era5:
      module: era5
      dx: 0.3
      dy: 0.3
```

Use a short-snapshot smoke cutout first, then the full 8760-hour 2023 cutout.
The plan assumes a clean pypsa-earth repo by default, so the build path is
`enable.build_cutout: true`. As an optimization only, if
`cutouts/cutout-2023-era5.nc` already exists with recorded hash/provenance,
set `enable.retrieve_cutout: false` and `enable.build_cutout: false` for that
run. The full validation baseline cannot use the default 2013-era cutout.

## Required Profile Outputs And References

Generate and validate enabled profiles:

```text
resources/za_2023_fixed/renewable_profiles/profile_solar.nc
resources/za_2023_fixed/renewable_profiles/profile_onwind.nc
resources/za_2023_fixed/renewable_profiles/profile_hydro.nc
resources/za_2023_fixed/renewable_profiles/profile_csp.nc
data/za_audit/za_atlite_renewable_profile_validation.csv
data/za_audit/za_atlite_technical_potential.csv
doc/za_renewable_profile_validation.md
```

CSP is included because South Africa 2023 has a 500 MW CSP validation anchor.
If PyPSA-Earth cannot build `profile_csp.nc` with limited local changes, V1 may
use a documented temporary simplified CSP profile fallback only after reopening
this module to name the consuming script and fallback artifact. Do not add an
unconsumed `za_baseline.csp_profile_mode` key to the overlay. Any fallback must
preserve CSP as `csp` and must not collapse CSP into PV.

PyPSA-RSA `data/eskom_pu_profiles.csv` comparison is a deferred validation
check that consumes the raw audit from `04` after module `04` completes. It is
not required for this module's profile-generation gate.

## Technical Potential Sanity Checks

Reuse the PyPSA-Earth renewable-potential validation notebook idiom as QA only.
For each enabled profile file, compute carrier-level technical potential:

```text
technical_potential_twh = sum_over_buses_and_hours(
  p_nom_max_mw * hourly_availability_pu
) / 1e6
```

Where usable land/sea area metadata exists, also report:

```text
installable_power_density_mw_per_km2 = sum(p_nom_max_mw) / area_km2
```

Write `data/za_audit/za_atlite_technical_potential.csv` with at least:

```text
carrier
profile_path
hours
p_nom_max_mw
technical_potential_twh
area_km2
installable_power_density_mw_per_km2
comparison_sources
sanity_status
notes
```

Compare technical potential and MW/km2 density against public/literature sanity
anchors where available, including IFC, IRENA, Mentis, Pietzcker, Wikipedia PV
lists, public wind-farm density references, and the PyPSA-RSA
REDZ/Power_corridors evidence cataloged in `04_source_data_audits.md`. These
checks are diagnostics only. They may classify a profile or siting issue, but
they must not trigger correction factors, capacity scaling, or resource masking
changes without a later reviewed source-of-truth update.

## Gate A Validation Checks

- Cutout covers South Africa plus the PyPSA-Earth margin.
- Full cutout has 8760 hourly snapshots for 2023.
- Profile files have non-empty bus coordinates.
- Hourly values are bounded and non-null.
- `p_nom_max` values are plausible by carrier and region.
- Annual full-load hours are compared with Eskom 2023 generation.
- Technical-potential TWh and MW/km2 sanity checks are written and any warnings
  are classified as diagnostic-only.
- Any temporary CSP fallback is explicitly flagged in the validation CSV and
  markdown report.

## Gate B Validation Checks

Gate B closes after `04_source_data_audits.md` and blocks final acceptance in
`12_validation_reporting_and_acceptance.md`. Gate B does not block module `10`
network build or module `11` solve.

- PyPSA-RSA `data/eskom_pu_profiles.csv` audit from `04` is available.
- Atlite profile full-load hours and shapes are compared with PyPSA-RSA profile
  references.
- Any mismatch is reported as capacity, weather/profile, curtailment/grid,
  outage, commissioning-timing, or unresolved.

## Guardrails

- Eskom observed renewable generation is a validation target, not the default
  availability profile.
- PyPSA-RSA normalized profiles are diagnostics/fallback evidence, not the first
  model driver.
- Correction factors are forbidden until the validation report classifies the
  bias as capacity error, profile/weather bias, curtailment/grid constraint,
  outage, or commissioning timing.
- Correction factors are disabled by default for future horizons unless a later
  reviewed module explicitly accepts the carry-forward policy.

## Acceptance Gates

Gate A, profile generation:

- Short-snapshot smoke profile generation passes.
- Full-year profile generation passes for solar, onwind, hydro, and native CSP;
  or a documented temporary CSP fallback is activated without mapping CSP to PV.
- Validation CSV and markdown report are written.
- Technical-potential CSV is written.
- Provenance records ERA5/CDS settings and cutout name.

Gate B, deferred profile-reference comparison after `04`:

- Gate B validation checks above pass before final acceptance in `12`.
