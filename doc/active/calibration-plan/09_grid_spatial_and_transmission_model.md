# 09 Grid Spatial And Transmission Model

## Goal

Make the South Africa network spatially credible before final validation and
later expansion. Start from PyPSA-Earth OSM, then benchmark against Eskom/PyPSA-
RSA grid and supply-region data.

## Spatial Ladder

Implement in this order:

1. `1` national node for smoke and national accounting.
2. `10` supply-region comparison for practical multi-node validation.
3. `34` local-area-aligned model for thesis/reliability compatibility if the
   grid and custom busmap gates pass.

The final `34`-region run must use a documented custom busmap or custom
subregion path; generic k-means clustering alone is not enough to claim Eskom
local-area alignment.

Acceptance levels:

- `1` node: accepted only for national accounting and smoke validation.
- `10` regions: accepted for practical multi-node baseline validation.
- Eskom-aligned `34` regions: required for reliability/myopic thesis handoff
  because the user Stage 4b answer in `pre-implementation-decisions.md` Q2
  locks the thesis objective to Eskom 34 local areas.

The V1 path is the hand-built custom busmap:

```yaml
enable:
  custom_busmap: true
scenario:
  clusters: [34]
```

The consumed artifact is `data/custom_busmap_elec_s_34.csv`. Custom subregion
shapes are a fallback only if the busmap coverage gate fails.

## Benchmark Corridor Model

Build a benchmark table:

```text
RSA physical lines
-> RSA supply-region corridors
-> St Clair limits
-> N-1 corridor limits
```

Reference rules:

```text
voltage threshold >= 220 kV
s_max_pu = 0.7
n1_approx_single_lines = 0.7
St_Clair_limit = min(thermal_limit, SIL_limit * 53.736 * length_km^-0.65)
if one line: multiply by 0.7
if multiple lines: drop strongest line for N-1 case
```

The St Clair coefficients are sourced from PyPSA-RSA
`scripts/build_topology.py:242-246`, which records them as digitized from the
St Clair curve reference linked in that script.

Compare against:

```text
PyPSA-Earth OSM lines
-> clustered corridors
-> effective s_nom after s_max_pu
```

## PyPSA-Earth Integration Options

Apply only after audit evidence justifies them:

- custom subregions via `subregion.method: custom`
- custom busmap via `enable.custom_busmap: true`
- cleaned custom line/substation inputs if OSM is missing major assets
- post-clustering transfer-capacity cap from RSA corridor benchmarks

Do not replace the physical PyPSA-Earth network with a directed-link transfer
model unless a separate scenario explicitly requests it.

## Outputs

```text
data/za_audit/za_pypsa_earth_osm_grid_summary.csv
data/za_audit/za_rsa_interregional_transfer_limits.csv
data/za_audit/za_grid_reconciliation.csv
data/za_audit/za_spatial_level_lock.csv
data/za_audit/za_plant_bus_assignment.csv
data/za_audit/za_demand_bus_attachment.csv
data/za_audit/za_import_export_bus_attachment.csv
data/za_audit/za_other_re_bus_attachment.csv
doc/za_grid_reconciliation.md
data/custom_busmap_elec_s_34.csv  # V1 thesis value if custom busmap path is used
data/za_custom/lines_220kv_plus.csv  # only if cleaned custom lines are used
data/za_custom/substations.csv  # only if cleaned custom substations are used
```

## Acceptance Gates

- OSM grid summary and RSA corridor benchmark exist.
- `za_spatial_level_lock.csv` declares the selected `1`, `10`, or `34` spatial
  level before module `10` builds the fixed network.
- Plant, demand, import/export, and `other_re` bus attachments are written as
  machine-readable CSVs and documented.
- Any custom busmap has coverage/hash checks.
- Any corridor cap has before/after capacity diagnostics.
- The chosen spatial level is declared before module `10` builds the fixed
  network.
