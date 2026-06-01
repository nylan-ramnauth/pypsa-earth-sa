# ZA Snakemake Extra Rules Audit

Date: 2026-06-01  
Reference baseline: `upstream/main:Snakefile` from `pypsa-meets-earth/pypsa-earth`  
Local config checked: `configs/za/za_2023_fixed_validation.yaml`

## Summary

The current ZA fork has **30 unique Snakemake rule names** that are not present
in base PyPSA-Earth:

- Base PyPSA-Earth unique rule names: **75**
- Current local unique rule names: **105**
- Extra unique rule names: **30**
- Active extra rules under the clean ZA config: **27**
- Dormant or conditional extra rules under the clean ZA config: **3**

The long-term objective is to simplify this surface as far as possible so the
workflow looks like PyPSA-Earth again: a small number of generic config-driven
hooks, neutral target names, and South Africa logic hidden inside scripts,
config, packaged inputs, and validation notebooks rather than many labelled
Snakefile branches.

## Simplification Principles

- Prefer generic rules over scenario-labelled rules.
- Keep scenario behavior in `configs/za/za_2023_fixed_validation.yaml`, not in
  Snakefile params.
- Keep presentation naming in notebooks, not in Snakemake output names.
- Package stable ZA reference inputs so default runs do not need source-audit
  generation rules.
- Collapse one-off audit materialization rules into script outputs or notebooks
  where they are not workflow-critical.
- Use upstream PyPSA-Earth rule names and DAG shape whenever the ZA behavior can
  be expressed as an optional config block inside existing scripts.

## Extra Rules By Group

| Group | Extra rules | Earth-like simplification target |
|---|---:|---|
| ZA source/reference audit | 1 | Keep disabled by default or move to an offline maintenance workflow. |
| ZA input preparation and validation | 11 | Consolidate into a small `prepare_za_inputs` layer or fold into existing upstream prep scripts via config hooks. |
| ZA network mutation markers | 5 | Move into upstream-adjacent script hooks where possible; keep only rules that create durable reusable artifacts. |
| ZA solve wrappers | 8 | Retire scenario-specific wrappers in favor of one generic config-labelled solve rule. |
| Audit materialization aliases | 4 | Replace with stable file outputs from solve/prep rules or notebook discovery. |
| Stock/baseline sharing | 1 | Keep only if stock-baseline comparison remains active; otherwise archive. |

## Rule Audit

| Rule | Line | Active in clean ZA config | Current purpose | Simplification direction |
|---|---:|---|---|---|
| `build_za_eskom_validation_data` | 289 | yes | Builds cleaned Eskom 2023 validation input artifacts. | Keep as ZA input prep unless replaced by tracked packaged validation CSVs. |
| `validate_za_renewable_profiles` | 304 | yes | Validates renewable profile artifacts against ZA expectations. | Fold into a notebook/report or make it an optional QA target. |
| `build_za_source_audits` | 332 | no | Generates source audit artifacts from a live PyPSA-RSA checkout. | Keep disabled by default; move toward offline maintenance because packaged `data/za_reference/` should serve normal runs. |
| `build_za_carrier_taxonomy` | 363 | yes | Builds local carrier taxonomy and crosscheck files. | Consider packaging its stable output or merging with cost/fleet prep. |
| `build_za_demand_import_export_inputs` | 379 | yes | Builds calibrated demand, import/export, Other RE, and attachment inputs. | Keep for now; later fold into a generic ZA input preparation rule. |
| `build_za_costs_fuels_efficiencies` | 402 | yes | Builds ZA cost/fuel/emissions sidecars and local carrier rows. | Merge with generic cost processing if the local carrier rows can become config/data inputs. |
| `build_za_fleet_reconciliation` | 422 | yes | Builds reconciled ZA fleet artifacts and `custom_powerplants.csv`. | Keep while fleet reconciliation is active; later package stable outputs. |
| `materialize_za_2023_fleet` | 446 | yes | Applies the selected 2023 fleet mode and writes audit sidecars. | Fold into fleet reconciliation once the selected fleet basis is stable. |
| `build_za_grid_spatial` | 462 | yes | Builds 34-region busmap, grid reconciliation, and attachment artifacts. | Keep while grid spatial build is source-derived; later package stable busmap and move diagnostics out of default DAG. |
| `build_za_custom_lines` | 497 | yes | Builds missing custom line inputs from diagnostics. | Package stable custom lines or fold into `build_za_grid_spatial`. |
| `apply_za_custom_lines` | 511 | yes | Applies custom line edits before extra components. | Move into `add_extra_components` or `cluster_network` config hook if it remains always-on for ZA. |
| `apply_za_local_carriers` | 524 | yes | Applies local ZA carrier metadata before extra components. | Prefer data/config-driven carrier definitions inside existing upstream scripts. |
| `za_fix_csp_links_stores` | 540 | yes | Fixes ZA CSP link/store capacity representation before prepare. | Move into `prepare_network` or upstream-adjacent CSP handling if generally valid. |
| `build_za_fixed_network_audit` | 558 | yes | Audits fixed-capacity network construction. | Make optional QA target or notebook/report output. |
| `build_za_earth_rsa_diagnostic` | 572 | yes | Compares Earth/RSA fleet, grid, substations, and line diagnostics. | Move out of default build path once calibration is accepted. |
| `build_za_coal_plants` | 1530 | yes | Builds named coal plant, hourly EAF, and bus assignment inputs. | Keep until coal EAF input path is stable; later package generated coal CSVs or fold into EAF application. |
| `apply_za_coal_eaf` | 1565 | yes | Builds the EAF input network from the prepared fixed network. | Candidate to remain as the one durable ZA network-prep rule, or move into `prepare_network` with config. |
| `solve_network_eaf` | 1612 | yes | Solves the EAF input network without further scenario caps/overrides. | Keep only as baseline diagnostic if still used; otherwise use generic config-labelled solves. |
| `solve_network_eaf_config` | 1649 | yes | Generic config-owned EAF solve with neutral output label. | Preferred replacement for scenario-specific solve wrappers. |
| `solve_network_eaf_opc` | 1700 | yes | Labelled OPC solve wrapper for NO/LOW/HIGH gas scenarios. | Retire after generic config-labelled solves and notebook mapping cover these comparisons. |
| `solve_network_eaf_cap` | 1748 | yes | Labelled annual OCGT cap diagnostic without OPC. | Retire or replace with config-labelled solve using `za_generation_constraints`. |
| `solve_network_eaf_opc_cap` | 1791 | yes | Labelled OPC plus OCGT cap diagnostic. | Retire or replace with config-labelled solve. |
| `solve_network_eaf_opc_cap_ocgt_sasol_opc_delegated` | 1853 | yes | Labelled Sasol/OCGT CAP wiring smoke target. | Archive once Sasol diagnostics are no longer needed in default Snakefile. |
| `solve_network_eaf_opc_low_gas_cap_rsa_high_gas_5p5` | 1915 | yes | Optional sensitivity reproducing RSA HIGH_GAS OCGT cap magnitude. | Archive or convert to config-labelled target if still needed. |
| `materialize_za_opc_audit_scenario` | 1964 | yes | Human-readable per-scenario OPC audit alias. | Replace with stable audit output naming from generic solve rules. |
| `materialize_za_opc_audit` | 1975 | yes | Materializes OPC audit outputs. | Replace with solve rule outputs or notebook discovery. |
| `materialize_za_op_constraints_audit` | 1984 | yes | Materializes operational-constraint audit outputs. | Replace with solve rule outputs or notebook discovery. |
| `materialize_za_scarcity_cap_audit` | 1994 | yes | Materializes scarcity-cap audit outputs. | Replace with solve rule outputs or notebook discovery. |
| `share_za_base_network` | 2007 | no | Shares/restores stock baseline network inputs for comparison mode. | Keep only if stock-baseline comparison remains an active workflow; otherwise archive. |
| `solve_network_stock_baseline` | 2059 | no | Stock PyPSA-Earth ZA baseline solve wrapper. | Archive after stock comparison is frozen, or keep in a separate diagnostics Snakefile. |

## Recommended Reduction Path

1. **Standardize all new solves on `solve_network_eaf_config`.**  
   Stop adding named solve wrappers for calibration variants. Use config edits
   plus neutral `EAF-CONFIG-*` file labels.

2. **Retire or archive legacy solve wrappers.**  
   Candidate retirements after notebooks and reports use generic outputs:
   `solve_network_eaf_opc`, `solve_network_eaf_cap`,
   `solve_network_eaf_opc_cap`,
   `solve_network_eaf_opc_cap_ocgt_sasol_opc_delegated`, and
   `solve_network_eaf_opc_low_gas_cap_rsa_high_gas_5p5`.

3. **Remove audit aliases from the default DAG.**  
   The `materialize_za_*_audit*` rules should become either direct solve outputs
   or notebook-discovered artifacts.

4. **Package stable source-derived inputs.**  
   Once the current calibration is accepted, stable outputs from source audit,
   carrier taxonomy, fleet, grid, and coal input generation can be tracked as
   reference inputs. The generation rules can move to an offline maintenance
   workflow.

5. **Fold small network mutations into upstream-style scripts.**  
   `apply_za_custom_lines`, `apply_za_local_carriers`, and
   `za_fix_csp_links_stores` are useful but make the Snakefile look less like
   Earth. If they remain always-on for ZA, migrate them toward config-gated
   hooks inside the closest upstream stage.

6. **Target end-state rule surface.**  
   A maximally simplified ZA Snakefile should ideally keep only a small number
   of extra visible rules:
   - one ZA input/reference preparation rule, if source generation remains in
     scope;
   - one ZA EAF/network-prep rule, if EAF cannot be cleanly folded into
     `prepare_network`;
   - one generic config-labelled solve rule;
   - optional QA/report targets outside the default build path.

## Current Interpretation

The current extra-rule count is understandable for an active calibration fork,
but too high for the final reproducible baseline. The most important cleanup is
not deleting logic immediately; it is making every surviving rule generic,
config-owned, and aligned with the base PyPSA-Earth DAG. The new
`solve_network_eaf_config` rule is the right direction because it replaces many
labelled scenario solve rules with one neutral target pattern.
