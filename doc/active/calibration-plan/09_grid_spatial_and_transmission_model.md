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

### pypsa-rsa grid parameters — explicit import list

All grid parameters below are imported from pypsa-rsa at pinned commit `89872c1ea703af3d8a3f198706d1ab7958f50a5f`.
For each parameter, cite the exact source file and line number (look up at implementation time):

| Parameter | Value | pypsa-rsa source |
|---|---|---|
| Voltage threshold | ≥ 220 kV (lines below this threshold excluded) | `scripts/build_topology.py` (line TBD) |
| `s_max_pu` | 0.7 (line loading factor) | `config.yaml` or `build_topology.py` (line TBD) |
| `n1_approx_single_lines` | 0.7 | `config.yaml` (line TBD) |
| St Clair limit coefficients | `(53.736, -0.65)` | `scripts/build_topology.py` lines 242–246 |
| SIL 220 kV | ~122 MW | `scripts/build_topology.py` (line TBD) |
| SIL 400 kV | ~600 MW | `scripts/build_topology.py` (line TBD) |
| SIL 765 kV | ~2200 MW | `scripts/build_topology.py` (line TBD) |
| N-1 rule | Drop strongest line per corridor | `scripts/build_topology.py` (line TBD) |
| MTS hosting limits | Per-corridor caps from `Supply_Areas2022_Steady_State_Limit` | `data/` file (TBD) |
| Supply area corridor caps | From `pypsa_rsa_transmission_expansion_audit.csv` | Module 04 registry |

The implementing agent must fill in all `TBD` line numbers during Module 04 before using these parameters.

### St Clair coefficient discrepancy

The pypsa-rsa coefficients `(53.736, -0.65)` differ from the literature-standard
Dunlop/St Clair fit `(43.261, -0.6678)`.

The implementing agent must:
1. Locate the pypsa-rsa source for `(53.736, -0.65)` in `scripts/build_topology.py`
2. Check whether pypsa-rsa documents the source of this calibration
3. Document the discrepancy and the chosen value in `doc/za_implementation_log.md`
4. Use the pypsa-rsa value `(53.736, -0.65)` for consistency with the reference model,
   unless inspection reveals it is clearly a data-entry error

Do not silently use one value without documenting the discrepancy.

### Spatial resolution — Eskom-34 supply regions (Stage 4b)

Target: 34 Eskom supply regions. This is a hard requirement with no fallback to 10-region.
The 27-region intermediate layer is intentionally skipped.

If the 34-region custom busmap cannot be cleanly built in one pass, do not fall back to 10-region.
Instead: document the blockers in `doc/za_implementation_log.md`, propose targeted fixes, and
resolve them before proceeding. Escalate to nylan-ramnauth if blockers cannot be resolved within
the implementing session.

### MTS hosting limits

`Supply_Areas2022_Steady_State_Limit` and MTS hosting limits (from Module 04 registry) are
applied as post-clustering corridor capacity caps, not as per-line parameters. Specifically:
after the custom busmap collapses lines to the 34-region network, apply the regional transfer
limits as `n.lines.s_nom` caps where each corridor's limit comes from the audit table.
Document the implementation approach in `doc/za_implementation_log.md`.

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
