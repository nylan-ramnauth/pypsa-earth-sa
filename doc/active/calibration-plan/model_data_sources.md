# ZA Baseline Model: Data Sources and Build Pipeline

How the `za_2023_fixed_validation` model is assembled — what comes from
PyPSA-Earth/OSM, what comes from RSA/Eskom data, and how the network is
spatially aggregated.

---

## Pipeline Overview

```
OSM (via PyPSA-Earth)          RSA / Eskom data
        │                              │
        ▼                              ▼
  Network topology            Custom overrides
  (buses, lines)              (generators, demand,
  Renewable profiles           costs, thermal caps,
  (atlite / ERA5)              supply regions)
        │                              │
        └──────────────┬───────────────┘
                       ▼
           PyPSA network (elec_s_34.nc)
           34 buses × ~72 line corridors
```

---

## What Comes from Earth (OSM / PyPSA-Earth)

| Component | Source detail |
|---|---|
| Bus locations | OSM substations tagged as `transmission`, ZA only |
| Line topology | OSM ways tagged as high-voltage power lines |
| Renewable capacity factors | atlite ERA5 cutout, 2023 |
| Offshore/onshore regions | Voronoi tessellation over OSM buses |

PyPSA-Earth downloads and processes OSM data through its standard pipeline:
`build_osm_network` → `build_shapes` → `base_network`.

---

## What Comes from RSA (Eskom / PyPSA-RSA / REIPPPP)

| Component | Source detail | Module |
|---|---|---|
| All generators | `custom_powerplants.csv` replaces PPM entirely | 08 |
| REIPPPP additions | Solar and wind REIPPPP rounds added to fleet | 08 |
| Demand profile | Eskom 2023 measured contracted demand (8,760 h) | 06 |
| Import/export | Mozambique, Namibia, Swaziland, Zimbabwe interconnectors | 06 |
| Load allocation | GVA + population weights per supply area | 06 |
| Costs and fuels | ZA-specific: coal price, gas, diesel, nuclear, RE CAPEX | 07 |
| Efficiencies | Per-carrier from PyPSA-RSA audits | 07 |
| Thermal limits | St Clair N-1 caps for 55/65 corridors | 09 |
| Bus region geography | 34 Eskom local-area supply regions (GeoJSON) | 09 |
| Custom busmap | OSM bus → Eskom supply area assignment | 09 |

The generator replacement is total: `custom_powerplants: replace` means the
IRENA/powerplantmatching (PPM) global database is completely bypassed for ZA.
Module 10 confirmed that PPM would have missed ~13 GW of RE and
mis-attributed ~9 GW of coal.

---

## Bus Aggregation: OSM → 34 Eskom Supply Areas

The spatial aggregation runs in two stages:

### Stage 1 — OSM simplification (`elec_s`)

```
1,606 OSM buses  →  803 simplified buses
```

PyPSA-Earth merges buses that are electrically equivalent (same substation,
same voltage, connected by a zero-impedance transformer). The result is one
bus per distinct substation node.

Artefact: `resources/za_2023_fixed_validation/bus_regions/busmap_elec_s.csv`

### Stage 2 — Cluster to 34 supply areas (`elec_s_34`)

```
803 simplified buses  →  34 named Eskom supply areas
```

A custom busmap (`data/custom_busmap_elec_s_34.csv`) assigns each of the 803
simplified OSM buses to one of 34 Eskom local-area supply regions. The
mapping was built in module 09 using the Eskom supply-area GeoJSON: each bus
is placed in the supply area whose polygon contains it.

The 34 region names are Eskom supply-area identifiers: Peninsula, Vaal,
Witbank, Ladysmith, Highveld South, Middelburg, Pinetown, etc.

Coverage: 803/803 buses assigned, 0 orphans, mean 23.6 buses per region.

Artefact: `resources/za_2023_fixed_validation/bus_regions/busmap_elec_s_34.csv`

---

## Line Aggregation: OSM lines → Inter-Supply-Area Corridors

```
2,138 OSM raw lines  →  216 retained (post elec_s)  →  ~72 unique corridors
```

After bus aggregation, all OSM lines whose bus0 and bus1 map to the same
pair of supply areas are aggregated into a single representative line for
that corridor. PyPSA sums the number of parallel circuits and computes an
effective `s_nom` and impedance for the bundle.

Artefact: `resources/za_2023_fixed_validation/bus_regions/linemap_elec_s_34.csv`

The `elec_s_34.nc` network therefore has one (or occasionally two) lines per
inter-supply-area corridor, not one per physical tower.

### Thermal cap override

The OSM-derived `s_nom` values are unreliable for ZA: module 10 found that
52 of 65 RSA corridors are over-rated by OSM (median ~10×). Where a St Clair
N-1 limit exists (55/65 corridors), it overrides the OSM value. The 10
unmatched corridors (12 GW RSA capacity) have no OSM line and are absent
from the model — documented as a known gap.

---

## Final Network Dimensions (`elec_s_34.nc`)

| Dimension | Count |
|---|---|
| Buses | 34 |
| Inter-area line corridors | ~72 |
| Generators | ~229 (RSA fleet + REIPPPP) |
| Demand nodes | 34 (load attached per supply area) |
| Timesteps | 8,760 (2023) |

---

## Key Principle

> OSM provides the **topology** (where buses and lines exist).  
> RSA/Eskom data provides the **quantities** (how much generation, demand,
> and transmission capacity).

The custom busmap is the bridge: it re-labels OSM bus coordinates with
Eskom supply-area names so that RSA demand weights, generator attachments,
and thermal limits can be joined on a common geography.
