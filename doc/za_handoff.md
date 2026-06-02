# ZA Expansion And Reliability Handoff

**Date:** 2026-06-02  
**Actor:** Codex  
**Related decision:** [[3-wiki/decisions/2026-06-02-module14c-no-vre-no-annual-ocgt-cap-baseline|DEC-003]]  
**Related handoff decisions:** [[4-work/expansion-handoff-decisions]]

## Accepted Baseline

DEC-003 accepts the Module 14c **No VRE / No annual OCGT cap** network as the
calibrated 2023 baseline reference and the starting basis for future expansion
inputs:

```text
results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-UC-OPC-LOW-GAS-OFFICIAL-FLEET-MODULE14C-COAL485-NUCLEAR50-NO-VRE-NO-OCGT-CAP.nc
```

"No annual OCGT cap" means the selected Module 14c overlay does not apply the
2023 annual OCGT generation cap. It does not mean all OCGT-related operating
constraints are absent from the source solve. The source path came through a
LOW_GAS OPC workflow, so future expansion must strip 2023 LOW_GAS solve-time
constraints unless a future-year source reintroduces them.

## Source Artifacts And Receiving Contracts

The machine-readable handoff table is:

```text
data/za_audit/za_handoff_artifact_table.csv
```

It binds accepted ZA artifacts to the Reliability Plan receiving contract:

- network and buildable inputs to `07_implementation_handoff.md` repo-layout and
  Snakemake input sections.
- fleet and busmap inputs to the external input contract.
- costs and local carriers to the cost data contract.
- retirement, future-asset, and eta-y tables to brownfield and reliability
  parameter inputs.
- validation, provenance, and limitations reports to evidence inputs.
- external observation and regional VOLL rows to unresolved receiving contracts.

Required rows cover the accepted network, frozen `data/custom_powerplants.csv`,
GEGIS demand files for 2030/2040/2050 using `era5_2018`, Eskom-34 busmap, grid
and transmission mapping audits, local carrier cost rows, present and missing
cost files, coal availability/EAF artifacts, eta-y defaults, retirement policy,
future-asset policy, observation adapter input, validation report, provenance
report, limitations report, regional VOLL contract, and Scenario 4 cutout
readiness.

## Future-Year Exclusions

Do not carry these 2023 calibration artifacts into 2030, 2040, or 2050 unless a
reviewed future-year source explicitly reintroduces them:

- VRE correction factors.
- 48.5% coal EAF calibration target.
- Weekly 2023 coal outage profiles.
- Nuclear 50% `p_max_pu`, nuclear annual cap, and LOW_GAS nuclear minimum.
- LOW_GAS weekly OCGT CF constraints.
- OCGT annual generation cap.
- 2023 import/export series.
- 2023 Eskom demand and load-shedding target.
- temporary CSP fallback or other diagnostic-only repairs.

## Ready Inputs

- DEC-003 accepted network and supplementary professionalized EAF-CONFIG network
  outputs exist locally.
- `data/custom_powerplants.csv` exists and is frozen for this handoff.
- `data/custom_busmap_elec_s_34.csv` exists.
- GEGIS `era5_2018` demand NetCDF files exist for 2030, 2040, and 2050.
- ZA grid, corridor, and rating audit artifacts exist.
- Local carrier cost rows and cost audit artifacts exist.
- Validation, provenance, and limitations reports exist.
- Eta-y defaults are recorded in `data/za_audit/za_reliability_eta_y.csv`.
- Retirement and future-asset policy CSVs are present, with unresolved source
  limitations documented.

## Missing Or Placeholder-Backed Inputs

- Local canonical IRP 2023 retirement source file is still missing.
- `data/costs_2040.csv` and `data/costs_2050.csv` are not present locally.
- Regional VOLL input is not implemented; user intent is regional
  load-shedding marginal cost, but semantics require review.
- Thesis observation input remains external. A synthetic dry-run file is allowed
  only for interface testing.
- Scenario 4 weather robustness cutouts beyond the existing 2023 cutout are not
  ready locally.
- Future 80% coal EAF remains provisional until sourced.

## Recommended Next Implementation Order

1. Rewrite or update the Reliability Plan from DEC-003 and this handoff package.
2. Resolve regional VOLL semantics before changing load-shedding marginal costs.
3. Complete the cost audit and restore or replace grid-connection costs.
4. Complete IRP 2023 retirement mapping against a local canonical source.
5. Decide LP vs MILP treatment for coal realism and dual interpretation.
6. Build a short hourly 2023 smoke path before any full-horizon solves.
7. Add Scenario 4 cutout readiness checks only after the first implementation
   path is stable.

The Reliability Plan has not yet been rewritten. All Reliability Plan modules
and the active repo mirror must be re-reviewed after this handoff update.
