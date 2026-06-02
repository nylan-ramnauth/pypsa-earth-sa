# ZA Snakemake Extra Rules Audit

Date: 2026-06-01  
Reference baseline: `upstream/main:Snakefile` from `pypsa-meets-earth/pypsa-earth`  
Local config checked: `configs/za/za_2023_fixed_validation.yaml`

## Summary

After the professionalization pass, the ZA fork has **6 unique Snakemake rule
names** that are not present in base PyPSA-Earth:

- Base PyPSA-Earth unique rule names: **75**
- Current local unique rule names: **81**
- Extra unique rule names: **6**

The removed rules were source-audit generators, validation/reporting checks,
legacy labelled solve wrappers, audit-copy aliases, and stock-baseline
comparison helpers. Those tasks are now either packaged as tracked inputs,
handled by notebooks/scripts outside the model DAG, or folded into the single
optional input-regeneration target.

## Current Extra Rules

| Rule | Current role | Recommendation |
|---|---|---|
| `prepare_za_input_data` | Optional, disabled-by-default wrapper that regenerates packaged ZA source/model-input data through existing scripts, including custom busmap, custom-line, and coal EAF inputs. | Keep as the only public ZA data-regeneration target; run it only with `enable.za_input_data_regeneration: true`. |
| `apply_za_custom_lines` | Applies tracked ZA custom transmission line inputs to the clustered network before extra components. | Keep for now; later fold into the closest upstream grid/component script if this remains always-on for ZA. |
| `apply_za_local_carriers` | Applies tracked ZA local carrier metadata and fixed fleet adjustments before extra components. | Keep for now; later express carrier rows as ordinary input data consumed by upstream component/cost handling. |
| `za_fix_csp_links_stores` | Fixes ZA CSP link/store capacity representation before the prepared network is built. | Keep for now; later fold into `prepare_network` or upstream CSP handling if generally valid. |
| `apply_za_coal_eaf` | Builds the reusable EAF/UC source network from the prepared fixed network. | Keep as the durable ZA source-network boundary unless it can be folded into `prepare_network`. |
| `solve_network_eaf_config` | Generic config-labelled scenario solve from the EAF source network. | Keep as the only ZA scenario solve rule; do not add labelled presentation/diagnostic solve wrappers. |

## Removed From The Main DAG

- Source/input generation rules:
  `build_za_eskom_validation_data`, `build_za_source_audits`,
  `build_za_carrier_taxonomy`, `build_za_demand_import_export_inputs`,
  `build_za_costs_fuels_efficiencies`, `build_za_fleet_reconciliation`,
  `materialize_za_2023_fleet`, `build_za_grid_spatial`,
  `build_za_custom_lines`, and `build_za_coal_plants`.
- Network/reporting diagnostics:
  `validate_za_renewable_profiles`, `build_za_fixed_network_audit`, and
  `build_za_earth_rsa_diagnostic`.
- Legacy solves and audit aliases:
  all `solve_network_eaf_*` labelled diagnostics, `solve_network_eaf`, and all
  `materialize_za_*_audit*` copy rules.
- Stock-baseline comparison rules:
  `share_za_base_network` and `solve_network_stock_baseline`.

The accepted outputs of the removed source/input rules are treated as tracked
packaged inputs in normal reruns. If they need to be refreshed, run
`prepare_za_input_data` explicitly.

## Remaining Simplification Target

The active surface is now small enough for reproducibility. The next cleanup is
not another rule deletion pass; it is folding the three network-mutation marker
rules into upstream-style scripts without changing the accepted solved-network
objectives.
