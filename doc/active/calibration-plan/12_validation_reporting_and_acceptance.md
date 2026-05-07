# 12 Validation Reporting And Acceptance

## Goal

Produce the final evidence package showing whether the South Africa 2023
baseline is accurate enough for thesis use and later expansion.

## Required Reports

```text
data/za_validation/za_2023_validation_annual.csv
data/za_validation/za_2023_validation_monthly.csv
data/za_validation/za_2023_validation_hourly_metrics.csv
data/za_validation/za_2023_validation_capacity.csv
data/za_validation/za_2023_load_shedding_validation.csv
data/za_validation/za_2023_validation_secondary_sources.csv
data/za_validation/za_2023_irena_carrier_harmonization.csv
doc/za_2023_validation_report.md
doc/za_data_provenance.md
doc/za_model_limitations.md
```

`doc/za_data_provenance.md` and the machine-readable provenance appendix must
include at minimum: `artifact_path`, `hash`, `source`, `owner`,
`extraction_date`, and `unresolved_warnings`.

## Validation Metrics

Annual energy and capacity:

```text
RSA Contracted Demand
Thermal Generation
Nuclear Generation
Eskom Gas Generation
Eskom OCGT Generation
Dispatchable IPP OCGT
Hydro Water Generation
Pumped Water Generation
Pumped Water SCO Pumping
Wind
PV
CSP
Other RE
Total RE
MLR + ILS + IOS / modeled unserved energy
Imports
Exports
installed capacity by carrier
```

## PyPSA-Earth Validation Notebook Idioms

Reuse upstream PyPSA-Earth validation notebook idioms as implementation patterns
for reporting, not as a replacement for South Africa primary evidence. Eskom
2023 data remains the acceptance authority where it exists. IRENA, OWID, IEA,
BP, Ember, and PyPSA-RSA are secondary plausibility anchors unless a later
reviewed source-of-truth module explicitly changes the source hierarchy.

Capacity validation may run on the unoptimized prepared network from module
`10_fixed_capacity_network_build.md`, before module `11` solves dispatch. The
capacity portion of the Stage 1 check must compare:

```text
data/custom_powerplants.csv
resources/<run>/powerplants.csv
networks/<run>/elec.nc
IRENA 2023 carrier capacity where available
PyPSA-RSA audited fleet references
Eskom installed-capacity anchors from 02
```

Demand validation must report annual model demand using the upstream aggregation
idiom:

```text
annual_demand_twh = n.loads_t.p_set.sum().sum() / 1e6
```

Compare this against Eskom `RSA Contracted Demand` as the primary target and
against OWID 2023 South Africa electricity demand as a secondary whole-system
plausibility check. Any secondary-source difference must be classified as
boundary, embedded generation, imports/exports, source-definition, or unresolved
before it can appear in the final limitations report.

Hydro validation must reuse the upstream annual-generation idiom for storage
units and run-of-river generators:

```text
hydro_storage_generation_twh = (
  n.storage_units_t.p[hydro_storage_units].clip(lower=0).sum().sum() / 1e6
)
phs_pumping_twh = (
  -n.storage_units_t.p[phs_units].clip(upper=0).sum().sum() / 1e6
)
ror_generation_twh = n.generators_t.p[ror_generators].sum().sum() / 1e6
```

Report pumped-storage generation, pumped-storage pumping, reservoir hydro, and
run-of-river separately where the model representation permits it. Compare
against Eskom `Hydro Water Generation`, `Pumped Water Generation`, and `Pumped
Water SCO Pumping`; IRENA/IEA hydro totals are secondary checks only.

Use a carrier-harmonization table for secondary IRENA comparisons. The table
must preserve ZA's CSP-not-PV lock:

| Secondary source category | ZA comparison treatment |
|---|---|
| IRENA `solar` | compare against ZA `solar` + `csp`; also report separate ZA PV and CSP values |
| IRENA `hydro` | compare against reservoir hydro + run-of-river + pumped storage where IRENA includes PHS; document inclusion choice |
| IRENA `bioenergy` | normalize to ZA `biomass`; compare against explicit 2023 biomass if present; if biomass remains inside aggregate `other_re`, report only as residual uncertainty |
| OWID demand | compare against modeled annual load as whole-system plausibility, not a primary pass/fail target |

Secondary-source comparisons must be written to
`data/za_validation/za_2023_validation_secondary_sources.csv`, and the carrier
mapping must be written to
`data/za_validation/za_2023_irena_carrier_harmonization.csv`.

Hourly/monthly metrics:

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

## Acceptance Standard

Use staged acceptance:

- Stage 1: annual demand, capacity, and generation totals.
- Stage 2: monthly demand and renewable shape.
- Stage 3: hourly dispatch and load shedding.
- Stage 4a: `10`-region multi-node validation and transmission plausibility.
- Stage 4b: Eskom-aligned `34`-region reliability/myopic handoff readiness.

The validation report must state which stages pass, which fail, and whether the
model is accepted for:

```text
national fixed 2023 validation
multi-node 2023 validation
brownfield expansion starting point
ready for reliability/myopic handoff
```

This module cannot certify reliability/myopic thesis scenarios themselves.
Scenario definitions and reliability acceptance are owned by
`doc/active/reliability-plan/`.

## Tolerance Bands

| Metric group | Pass band |
|---|---|
| Parser-level demand and exogenous series arithmetic | same precision as `02`: `1e-6 TWh` annual and `1e-3 MWh` hourly |
| Wind, PV, CSP, Total RE annual energy | absolute percentage error `<= 2%` unless documented and accepted as limitation |
| Wind, PV, CSP, Total RE installed capacity | absolute percentage error `<= 2%` unless documented and accepted as limitation |
| Conventional fleet capacity by carrier | nuclear `<= 1%`, coal `<= 2%`, OCGT diesel plus gas `<= 5%`, Sasol carriers `<= 5%`, PHS `<= 1%`; revise upward only for documented boundary/source conflict |
| Eskom Gas, OCGT, IPP OCGT, PHS, imports, exports, Other RE | documented per-series annual error and source/boundary interpretation; `Other RE` reports CO2 emissions factor = 0 under the V1 biogenic-neutral accounting policy and flags aggregate-category uncertainty |
| Monthly renewable and demand shape | for wind/PV/CSP/Total RE, monthly correlation `>= 0.85` and monthly MAE `<= 5%` of monthly mean unless documented boundary issue justifies weaker acceptance |
| Hourly dispatch/load shedding | diagnostic-only unless annual and monthly stages pass |

Capacity factor diagnostics must report Eskom-derived target ranges where
available, including Wind around `38%`, PV around `26%`, CSP around `31%`, and
coal/nuclear/OCGT ranges from cleaned Eskom 2023 data.

## Acceptable Limitations

- embedded/rooftop PV boundary uncertainty when documented.
- exact outage-cause attribution.
- small hourly dispatch mismatches after annual and monthly stages pass.
- distribution-network effects not represented in PyPSA-Earth.

## Hard Exclusions

These block acceptance:

- unresolved demand accounting.
- unresolved carrier-capacity mismatch.
- CSP mapped to PV.
- missing source provenance in `data/za_audit/input_file_manifest.csv` or
  `data/za_audit/source_hashes.csv`: every row must have non-empty `hash` and
  `source` for Stage 1 pass.
- unresolved Eskom-aligned 34-region mapping for Stage 4b reliability/myopic
  handoff. This does not block Stage 4a `10`-region multi-node acceptance.

The validation script must detect whether pumped hydro storage is represented as
`StorageUnit` or as `Store` + `Link` in the built PyPSA-Earth version, then use
the matching generation and pumping accounting idiom.

## Accepted Use By Validation Stage

The final validation report must include an explicit statement mapping each
passed stage to accepted model use:

```text
Stage 1 -> national annual accounting only
Stage 2 -> national fixed 2023 validation with monthly shape evidence
Stage 3 -> hourly dispatch/load-shedding validation
Stage 4a -> 10-region multi-node/regional validation
Stage 4b -> Eskom-aligned 34-region reliability/myopic handoff readiness
```

## Acceptance Gates

- All required reports exist.
- Provenance is complete.
- Tolerance table, acceptable limitations, hard exclusions, and accepted-use
  statement are included in `doc/za_2023_validation_report.md`.
- Validation failures are classified as data, fleet, weather/profile, grid,
  availability, cost, operational-constraint, or boundary issues.
- The model is either accepted for the next module or blocked with explicit
  remediation tasks.
