# 02 Eskom Validation Data Pipeline

## Goal

Turn raw Eskom 2023 hourly data into the validation authority for all later
network, dispatch, and reporting checks.

## Glossary Reference

When interpreting Eskom CSV column headers, consult the official Eskom Data Portal Glossary:
```
1-sources/web-clips/2026-05-07 WEB Glossary.md
```
Canonical reference page: `3-wiki/reference/web-clips/2026-05-07-eskom-dataportal-glossary.md`

Key definitions for this module:
- **Residual Demand:** Hourly average MW that must be supplied by all dispatchable resources
  (Eskom generation + international imports + dispatchable IPPs + IOS). Note: per the glossary,
  `Residual Demand` **already includes IOS**.
- **RSA Contracted Demand:** Residual Demand + self-dispatched (renewables). This is the total
  contracted MW Eskom supplies.
- **MLR (Manual Load Reduction):** Deliberate demand reduction by load shedding schedule.
- **ILS (Interruptible Load Shed):** Contractually interruptible consumer load.
- **IOS (Interruption of Supply):** All contracted + mandatory demand reductions, including
  transmission faults. Per the glossary, IOS is a component of Residual Demand.
- **EAF:** `1 - (PCLF + UCLF + OCLF)`. See Module 11 for formula derivation.
- **PCLF:** Planned Capability Loss Factor (planned maintenance outage ratio).
- **UCLF:** Unplanned Capability Loss Factor (unplanned outage ratio).
- **OCLF:** Other Capability Loss Factor (external-constraint outage ratio).

## Input

```text
data/za_audit/raw/eskom_data_2023_full.csv
```

The file has a known parse defect: most rows have 43 fields but the header has
42 because `Total UCLF+OCLF` sometimes uses a comma decimal separator such as
`17953,568`. The parser must repair this before loading the table.

Raw Eskom CSVs must be staged under `data/za_audit/raw/` during bootstrap so the
repo root stays clean. The raw coverage starts on `2022-12-01`; the 2023 filter
must drop pre-2023 and post-2023 rows and record pre-count, dropped-count, and
post-count in the parser report.

## PyPSA-Earth Additions

Add a preprocessing script or notebook-driven script that:

1. Reads the raw Eskom CSV without losing malformed rows.
2. Repairs the `Total UCLF+OCLF` comma-decimal split.
3. Parses `Date Time Hour Beginning` with `%Y-%m-%d %I:%M:%S %p`
   (12-hour AM/PM clock).
4. Filters exactly `2023-01-01 00:00` to `2023-12-31 23:00`.
5. Writes a clean hourly CSV.
6. Writes annual validation targets.
7. Writes parser warnings and accounting diagnostics.

Outputs:

```text
data/za_validation/eskom_2023_hourly_clean.csv
data/za_validation/eskom_2023_targets_by_carrier.csv
data/za_audit/eskom_2023_parser_report.csv
```

## Locked Accounting

- Demand target: `RSA Contracted Demand`.
- Do not subtract load shedding from demand before modeling.
- Observed reduced/unserved demand:

```text
Manual Load_Reduction(MLR) + ILS Usage + IOS Excl ILS and MLR
```

Accounting checks:

```text
Total RE = Wind + PV + CSP + Other RE
Residual Demand = Dispatchable Generation + MLR + ILS + IOS
RSA Contracted Demand ~= Residual Demand + Total RE
  using the annual tolerance locked below
```

### Accounting identity — verification required

The identity as written must be verified against the actual CSV column structure before locking:

**Risk:** The Eskom glossary defines `Residual Demand` as already including IOS. If the raw CSV
has a single `Residual Demand` column, then adding `IOS` separately would double-count.

**Implementing agent must:**
1. Print the raw CSV column headers and inspect whether `MLR`, `ILS`, and `IOS` are independent
   columns or whether some are sub-totals already inside `Residual Demand`.
2. Reconstruct the identity from first principles using the actual column list.
3. Document the resolved identity in `doc/za_implementation_log.md` with a column-header printout.
4. Do not lock the identity formula until this inspection is done.

## Target Anchors

The annual target file must include at least:

```text
RSA Contracted Demand = 225.875 TWh
Residual Demand = 207.190 TWh
Dispatchable Generation = 190.434 TWh
Thermal Generation = 165.627 TWh
Nuclear Generation = 8.127 TWh
Eskom Gas Generation = raw repaired 2023 total
Eskom OCGT Generation = 3.566 TWh
Dispatchable IPP OCGT = 1.677 TWh
Hydro Water Generation = 1.992 TWh
Pumped Water Generation = 4.294 TWh
Pumped Water SCO Pumping = -5.658 TWh
Wind = 11.613 TWh
PV = 5.015 TWh
CSP = 1.375 TWh
Other RE = 0.238 TWh
Total RE = 18.241 TWh
Manual Load Reduction = 16.562 TWh
ILS Usage = raw repaired 2023 total
IOS Excl ILS and MLR = raw repaired 2023 total
MLR + ILS + IOS = raw repaired 2023 total
International Imports = raw repaired 2023 total
International Exports = raw repaired 2023 total
```

Parser-computed raw totals must be recorded in
`data/za_validation/eskom_2023_targets_by_carrier.csv` with parser provenance
and a `source` column for every locked anchor value.

`Eskom Gas Generation = 0` in the 2023 raw file is expected and must not be
classified as a parser error.

### Source requirements for anchors

Every anchor value must cite a primary source (Eskom Annual Report 2023, CSIR Utility Statistics
Report 2024, Eskom System Adequacy Outlook 2023, National Treasury Budget Review 2024, etc.).
Do not leave any anchor un-cited. The implementing agent must retrieve the primary source document
for each anchor and record it in the source column before locking the table.

Note: `MLR = 16.562 TWh` is consistent with FTI Consulting (2025) citing 16.6 million MWh shed in
2023. Cross-check against the Eskom primary source nonetheless.

### Capacity reference year policy

Two PV capacity values appear in the anchor data (capacity at start-of-year vs end-of-year).
For Module 12 validation, **use end-of-year 2023 installed capacity** as the reference for
carrier-level capacity tolerance checks. Document this choice in `doc/za_implementation_log.md`.

Installed capacity anchors:

```text
Wind = 3442.57 MW
PV = 2212.09 MW at start, 2287.09 MW by end
CSP = 500.00 MW
Other RE = 50.58 MW
Total RE = 6205.24 MW at start, 6280.24 MW by end
Installed Eskom Capacity = 46686 MW
```

## Acceptance Gates

- Clean hourly output has exactly 8760 rows.
- Required columns are present and numeric after repair.
- Accounting identities pass within locked parser tolerances:
  - annual TWh accounting identities: absolute tolerance `1e-6 TWh`
  - hourly MWh arithmetic: absolute tolerance `1e-3 MWh`
  - larger discrepancies are parser-report warnings or blockers
- Annual targets match the locked anchors or any difference is explained in the
  parser report with source rows, source label, repair logic, and unit
  conversions.
- Annual targets include `MLR`, `ILS`, `IOS`, `MLR + ILS + IOS`, imports,
  exports, and Eskom gas generation.
- Provenance files record raw input path and hash.
