# 05 System Boundary And Carrier Taxonomy

## Goal

Lock the modeling boundary and carrier mapping before model-input generation,
cost construction, and final fleet reconciliation. This prevents later modules
from making ad hoc choices.

## System Boundary Locks

- Boundary: national South Africa 2023 electricity system.
- Demand target: `RSA Contracted Demand`.
- Load shedding target: `MLR + ILS + IOS`.
- Imports/exports: exogenous time series owned by
  `06_demand_import_export_model_inputs.md`.
- Embedded/rooftop PV: excluded as explicit plant capacity in V1 unless it is
  already included in Eskom reported PV and reconciled as grid-facing capacity.
  Its possible effect is documented as a residual demand/accounting issue.
- IPP utility wind/PV/CSP: included when it appears in Eskom reported generation
  and 2023 plant reconciliation.

## Carrier Mapping Locks

The final fleet must use these V1 carrier mappings. No row may defer the carrier
choice to the implementing agent.

| RSA concept | V1 PyPSA-Earth treatment |
|---|---|
| coal | conventional `coal` generator |
| sasol_coal | local `sasol_coal` generator with explicit cost/emissions row |
| nuclear | conventional `nuclear` generator |
| ocgt_diesel / diesel peakers | local `ocgt_diesel` generator with explicit cost/emissions row |
| ocgt_avf / gas OCGT | local `ocgt_gas` generator with explicit cost/emissions row |
| sasol_gas | local `sasol_gas` generator with explicit cost/emissions row |
| wind | `onwind` generator using atlite profile |
| solar PV | `solar` generator using atlite profile |
| solar_csp / csp | `csp`, never silently mapped to PV |
| reservoir hydro | PyPSA-Earth hydro/reservoir-compatible treatment |
| run-of-river hydro | PyPSA-Earth `ror`/hydro-compatible treatment |
| pumped storage | PyPSA-Earth storage-compatible pumped-storage treatment with PHS energy checked |
| battery | include only 2023-active batteries that pass normalization smoke; otherwise exclude from V1 fleet with audit record |
| hydro_import | exogenous import, not domestic hydro |
| biomass | upstream `biomass` carrier; explicit generator only when present in 2023-active reconciliation; otherwise covered by `other_re` |
| Other RE | local `other_re` exogenous generator using the Eskom 8760 `Other RE` series for V1 accounting |

Any local carrier must add local cost, emissions, color/nice-name, validation
target, and availability treatment in `configs/za/za_2023_fixed_validation.yaml`
and any PyPSA-Earth carrier metadata table written by the local ZA hook.

Carrier case policy: local carriers are lowercase snake_case
(`sasol_coal`, `sasol_gas`, `ocgt_diesel`, `ocgt_gas`, `other_re`); upstream
carriers retain upstream casing and names (`OCGT`, `CCGT`, `H2`, `biomass`).
Use `biomass` as canonical. Treat `bioenergy` only as a secondary-source label
that must normalize to `biomass` before entering PyPSA-Earth.

The active-2023 biomass decision is owned by `08` and must use the `04` fixed
technology, REIPPPP/source-registry, and Eskom `Other RE` audit evidence. If no
separately validated 2023 biomass plant exists, the energy remains inside the
aggregate `other_re` accounting carrier.

## Carrier Registration Contract

This module owns canonical carrier names, profile intent, emissions-factor
intent, and reporting treatment. Module `07` owns local cost rows in
`data/za_audit/za_local_carrier_cost_rows.csv`. Module `10` owns the
`apply_za_local_carriers` hook that writes local carrier rows to the network
after `add_electricity`.

The hook must not mutate upstream Carrier rows. It may add only the local ZA
carrier rows and the local generator/reporting metadata needed by this plan.

## CSP Lock

South Africa 2023 CSP anchors:

```text
installed capacity = 500 MW
generation = 1.375 TWh
```

Exclude Redstone from the 2023 baseline. V1 preferred route is simplified
fixed-capacity CSP using native atlite/PyPSA-Earth `profile_csp.nc`. If native
CSP profile generation fails, a documented temporary simplified CSP profile
fallback is allowed. The fallback must be isolated, reported, and revisited
before final thesis claims. Mapping CSP to PV is forbidden.

Preserve CSP storage-hour metadata for later explicit thermal-storage CSP.

## Acceptance Gates

- A carrier taxonomy table is written to `doc/za_carrier_taxonomy.md`.
- All local carriers have cost/emissions/reporting treatment delegated to
  `07_costs_fuels_efficiencies_and_coUE.md`.
- Imports/exports and embedded PV treatment are documented.
- CSP cannot normalize as PV in the planned custom plant smoke.
- Smoke-test assertion passes:
      `assert "csp" in n.carriers.index`
      `assert n.generators.query("carrier=='csp'").p_nom.sum() > 400  # MW, lower bound`
      `assert "solar" in n.carriers.index`
      `assert n.generators.query("carrier=='solar'").p_nom.sum() > 5000  # MW, SA PV lower bound`
      CSP and solar must be distinct non-zero carriers. CSP must never merge into solar.
