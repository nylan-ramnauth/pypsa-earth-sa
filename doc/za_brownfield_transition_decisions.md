# ZA Brownfield Transition Decisions

**Date:** 2026-06-02  
**Actor:** Codex  
**Related decision:** [[3-wiki/decisions/2026-06-02-module14c-no-vre-no-annual-ocgt-cap-baseline|DEC-003]]  
**Related handoff:** [[4-work/expansion-handoff-decisions]]

## Accepted Baseline

DEC-003 accepts the Module 14c **No VRE / No annual OCGT cap** case as the
calibrated 2023 reference and expansion basis:

```text
results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-UC-OPC-LOW-GAS-OFFICIAL-FLEET-MODULE14C-COAL485-NUCLEAR50-NO-VRE-NO-OCGT-CAP.nc
```

"No annual OCGT cap" means the Module 14 annual OCGT generation cap is absent.
It does not mean the source solve contains no OCGT-related LOW_GAS constraints.
Future expansion configs must rebuild from clean components and must not carry
2023 LOW_GAS solve-time constraints by default.

## Carries Forward

- Eskom-34 spatial interface and custom busmap.
- Official 2023 Eskom fleet identity as the brownfield starting fleet, subject
  to future-year retirements and policy treatment.
- Plant-to-bus mapping and coal station split weights.
- Local ZA carrier taxonomy and local carrier cost rows, pending the horizon
  cost audit.
- Current ZA transmission rating model: 220 kV threshold, St Clair correction,
  `s_max_pu: 0.7`, `n1_approx_single_lines: 0.7`, and the current SIL/thermal
  MW table.
- Load shedding as a solver safety valve.
- Physical PHS storage-hour assumptions.
- Hydro 1.20 inflow multiplier unless a future weather review supersedes it.

## Stripped For Future Years

- 2023 VRE correction factors: onshore wind 1.58 and solar 1.40.
- 2023 coal EAF 48.5% target and the weekly 2023 coal outage profiles.
- 2023 nuclear `p_max_pu: 0.5` and nuclear annual generation cap.
- LOW_GAS nuclear hourly minimum and LOW_GAS weekly OCGT CF constraints.
- OCGT annual generation cap and 2023 scarcity-cap mechanics.
- 2023 import/export exogenous series.
- 2023 Eskom demand series and 2023 load-shedding calibration target.
- Temporary fallback or diagnostic mechanics used only to match 2023.

## Retirement Policy Status

`data/za_audit/za_retirement_policy.csv` includes only rows with known numeric
retirement years from pypsa-rsa `fixed_technologies.xlsx` corroborating evidence.
The source column deliberately records that the IRP 2023 canonical source file
is still pending locally. The pypsa-rsa workbook is corroborating evidence only,
not the canonical retirement source.

Rows with non-numeric `beyond 2050` evidence were omitted to keep
`retirement_year` parseable as a numeric field. The omitted unresolved plants
from the inspected `IRP23_FULL` evidence are:

- Kusile*
- Kusile**
- Kusile***
- Medupi*
- Medupi**

Kelvin and Komati appear in the corroborating evidence but are not applicable to
the active 2023 baseline: Kelvin is excluded by locked policy, and Komati is
already retired before the 2023 baseline.

## Future Asset Policy Status

`data/za_audit/za_future_asset_policy.csv` records policy classes rather than an
invented project list:

- Redstone CSP is excluded unless a later reviewed future-asset policy
  reclassifies it.
- Solar, onshore wind, and CSP are candidate classes for expansion, not fixed
  builds unless separately source-backed.
- TDP planned lines are scenario-dependent unless reviewed and promoted.
- Future contracted projects are scenario-dependent unless reviewed evidence
  explicitly locks `fixed_build`, `candidate`, or `excluded`.

## Expansion Permissions

Generation expansion is allowed for solar, onshore wind, and CSP only in the
first implementation. Existing fossil, nuclear, hydro, and storage assets remain
brownfield assets subject to retirement and operating assumptions.

Transmission expansion is allowed with `lcopt`. The current rating/corridor
audit package is accepted for handoff, but planned TDP lines remain
scenario-dependent until reviewed.

No CO2 cap is imposed for the first expansion implementation.

## Reliability Inputs And Cautions

Regional VOLL remains unresolved. User intent is to map regional VOLL values to
load-shedding generator marginal costs, but implementation semantics need review
because this changes dispatch economics, not just reporting.

The observation adapter remains external to pypsa-earth. Synthetic dry-run input
is allowed for interface testing, but thesis input must come from the external
observation workstream and match the agreed GeoParquet schema.

## Open Modeling Decisions

- LP vs MILP: the user wants coal realism through min-up/down behavior, but
  integer dwell-time constraints turn the investment solve into a MILP. The
  Reliability Plan rewrite must decide how to preserve interpretability of duals
  and solve feasibility.
- Future coal EAF: 80% EAF is a provisional working target only. It needs
  source provenance before becoming a final scenario value.
- Costs: horizon costs for 2040 and 2050 are missing locally, and
  grid-connection costs for renewable/CSP candidates must be restored or
  replaced before final expansion solves.
- Weather: 2023 ERA5 is the near-term smoke/presentation scope. Scenario 4
  multi-weather robustness remains later and needs cutout readiness checks.
- Regional VOLL: load-shedding marginal cost semantics must be reviewed before
  implementation.

## Remaining Blockers Before Reliability Plan Rewrite

- Complete IRP 2023 retirement mapping from a local canonical source.
- Decide LP vs MILP coal realism and dual interpretation.
- Resolve regional VOLL implementation semantics.
- Audit horizon cost files and restore or replace grid-connection costs.
- Source future coal EAF assumptions.
- Confirm Scenario 4 cutout readiness beyond the existing 2023 cutout.
- Confirm external observation adapter production path or synthetic dry-run
  substitute for smoke testing.
