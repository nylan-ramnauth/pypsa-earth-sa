# 10 Fixed Capacity Network Build

## Goal

Build the first complete South Africa 2023 PyPSA-Earth network using the cleaned
validation data, 2023 profiles, reconciled fleet, and selected grid/spatial
setup. This module builds the network; dispatch calibration belongs to `11`.

## Required Configuration

Use the fixed-validation overlay from `01` with:

```yaml
countries: ["ZA"]
snapshots:
  start: "2023-01-01"
  end: "2024-01-01"
electricity:
  custom_powerplants: replace
  estimate_renewable_capacities:
    stats: false
  extendable_carriers:
    Generator: []
    StorageUnit: []
    Store: []
    Link: []
```

Load shedding must be enabled at high cost so observed unserved demand can be
represented during dispatch validation. The cost value and units are owned by
`07`.

## Local Hook Contract

Rule name: `apply_za_local_carriers`.

Input: the network emitted by upstream `add_electricity`.

Output: the same network with local ZA carriers, local generator metadata, and
fixed exogenous `other_re` dispatch attached.

Consumes:

```text
data/za_audit/za_local_carrier_cost_rows.csv
data/za_audit/za_2023_other_re_attachment.csv
```

The hook runs after `add_electricity` and before fixed-network audit. It must
not mutate upstream Carrier rows.

## Build Requirements

The network must consume:

- `data/custom_powerplants.csv`
- 2023 renewable profile files from `03`
- demand/import/export model inputs from `06`
- `Other RE` exogenous model input from `06`
- cost, fuel, efficiency, emissions, and load-shedding-cost inputs from `07`
- selected grid/spatial artifacts from `09`
- final plant, demand, import/export, and `other_re` bus attachment tables from
  `09`
- 2023 demand period aligned with cleaned Eskom validation data
- exogenous import/export representation from `06`

## Network Checks

Before solving, inspect `networks/<run>/elec.nc` and verify:

- all expected carriers are present.
- fixed capacities match reconciliation totals.
- no unintended extendable capacity exists.
- demand, import, and export time series have the sign conventions from `06`.
- `other_re` is attached as the `06` locked non-extendable
  Generator with `p_nom = 50.58 MW` from the end-of-2023 installed-capacity
  anchor in `02`, `p_max_pu = Eskom Other RE 8760 series / p_nom` (clipped per
  the `06` locked rule), and `p_min_pu = 0` (curtailment allowed; see Module 06
  rationale). Not folded into demand.
- carrier costs and local carrier rows match `07`.
- wind rows use `onwind` profile.
- PV rows use `solar` profile.
- CSP rows use `csp` profile and are not PV.
- PHS, hydro, imports, storage, and local carriers map as declared in `05`.
- load time index matches 8760 validation hours.
- network buses/clusters match the spatial choice from `09`.

## Smoke Build Stages

### Smoke Build Stages (required before full 8760 build)

Do not run the full 8760-hour solve without passing staged smoke builds first.
Each stage has its own acceptance gate.

#### Stage 1 — 7-day smoke (required)

Period: `2023-07-01` to `2023-07-07` (peak winter week).
Solve: Gurobi, `Threads=2`, full carrier set.
Gate: network solves without errors; load-shedding ≤ 5% of demand; no infeasibility.
If Stage 1 fails: diagnose and fix before Stage 2. Do not proceed.

#### Stage 2 — 1-month smoke (required)

Period: July 2023 (full month).
Solve: Gurobi, `Threads=2`, full carrier set.
Gate: network solves; monthly generation by carrier within 30% of Eskom anchor; no infeasibility.
If Stage 2 fails: diagnose and fix before Stage 3. Do not proceed.

#### Stage 3 — Full 8760 (only after Stage 1 and 2 pass)

Period: Full year 2023.
Solve: Gurobi, `Threads=2` (serial). Or `Threads=1` if running in batch.
Gate: Module 12 staged acceptance criteria.

## Uncalibrated Baseline

### Uncalibrated baseline configuration

For the before/after comparison required by Module 12, the uncalibrated baseline uses:
```yaml
# za_2023_uncalibrated_baseline.yaml
countries: [ZA]
# All other settings: pure upstream config.default.yaml defaults
# Do NOT include: custom_powerplants.csv, ZA cost overlay, ZA grid override, ZA demand overlay
```

This "stock PyPSA-Earth" run with only `countries: [ZA]` set is the methodological baseline.
Its results serve as the denominator for all before/after comparison metrics in Module 12.
Build and solve this baseline as part of Module 10 so that Module 12 has both runs available.

## Acceptance Gates

- Fixed-capacity `elec.nc` builds reproducibly.
- A network audit CSV is written to `data/za_audit/za_fixed_network_audit.csv`.
  Required columns: `carrier`, `capacity_mw_built`, `capacity_mw_anchor`,
  `anchor_delta_pct`, `bus_count`, `generator_count`, `bus_load_total_mwh`,
  `p_min_pu_mean`, `p_max_pu_mean`, `extendable_flag`,
  `is_load_shedding_safety_valve`.
- `bus_count` means buses with at least one generator or storage asset for the
  carrier; `generator_count` records the number of generator rows.
- Load-shedding generators added by `solve_network.py:add_load_shedding` are
  excluded from the no-unintended-extendable-capacity gate and marked with
  `is_load_shedding_safety_valve: true`.
- All carrier and capacity checks pass or are explicitly documented as blockers.
- No solve is accepted until this module passes.
