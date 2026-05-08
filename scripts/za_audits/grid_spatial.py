# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""ZA Module 04 — grid spatial + external bundle inventory + supply-region resolution check."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .io import sha256_of_file, write_geojson

CANONICAL_SUPPLY_REGIONS = (1, 10, 27, 34, 159)
EXISTING_LINE_KV_THRESHOLD = 220.0


def _safe_listlayers(gpkg: Path) -> list[str]:
    try:
        import fiona

        return list(fiona.listlayers(str(gpkg)))
    except Exception:
        return []


def _gdf_or_none(path: Path, layer: str | None = None):
    try:
        import geopandas as gpd

        if layer is not None:
            return gpd.read_file(path, layer=layer)
        return gpd.read_file(path)
    except Exception:
        return None


def build_external_bundle_inventory(pypsa_rsa_root: Path, out_path: Path) -> int:
    base = Path(pypsa_rsa_root)
    inventory_targets = [
        ("data/bundle/supply_regions/rsa_supply_regions.gpkg", "gpkg", "supply_regions"),
        ("data/bundle/supply_regions/rsa_supply_regions2.gpkg", "gpkg", "supply_regions"),
        ("data/bundle/GCCA 2025 GIS/AREAS_GCCA2025.gpkg", "gpkg", "gcca_2025"),
        ("data/bundle/GCCA 2025 GIS/SUPPLY_AREA_GCCA2025.shp", "shp", "gcca_2025"),
        ("data/bundle/GCCA 2025 GIS/LOCAL_AREA_GCCA2025.shp", "shp", "gcca_2025"),
        ("data/bundle/GCCA 2025 GIS/MTS_ZONES_GCCA2025.shp", "shp", "gcca_2025"),
        ("data/bundle/Shapefiles/Existing_Lines.shp", "shp", "existing_lines"),
        ("data/bundle/Shapefiles/Planned_Lines.shp", "shp", "planned_lines"),
        ("data/bundle/Shapefiles/Existing_Substations.shp", "shp", "substations"),
        ("data/bundle/Shapefiles/Planned_Substations.shp", "shp", "substations"),
        ("data/bundle/Shapefiles/Supply_Areas2022_Steady_State_Limit.shp", "shp", "supply_area_limits"),
        ("data/bundle/Shapefiles/MTS_Subs2022.shp", "shp", "mts_subs"),
        ("data/bundle/Shapefiles/RE_IPP_1_to_4b.shp", "shp", "reipppp_siting"),
        ("data/bundle/transmission_grid/eskom_gcca_2022/Existing_Lines.shp", "shp", "existing_lines_deeper"),
        ("data/bundle/transmission_grid/tdp_digitised/TDP_2023_32.shp", "shp", "planned_tdp"),
    ]
    rows: list[dict] = []
    for rel, kind, role in inventory_targets:
        path = base / rel
        if not path.exists():
            rows.append({"rel_path": rel, "kind": kind, "role": role, "feature_count": -1, "layers": "", "hash": "", "present": False})
            continue
        layers = _safe_listlayers(path) if kind == "gpkg" else [""]
        feature_count = 0
        for layer in layers:
            gdf = _gdf_or_none(path, layer if layer else None)
            if gdf is not None:
                feature_count += int(len(gdf))
        rows.append(
            {
                "rel_path": rel,
                "kind": kind,
                "role": role,
                "feature_count": feature_count,
                "layers": "|".join(layers),
                "hash": sha256_of_file(path),
                "present": True,
            }
        )
    df = pd.DataFrame(rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return len(df)


def build_supply_region_layer_resolution(pypsa_rsa_root: Path, out_path: Path) -> int:
    """Probe every supply-region layer and match feature_count to canonical 1/10/27/34/159."""
    base = Path(pypsa_rsa_root)
    candidates = [
        base / "data" / "bundle" / "supply_regions" / "rsa_supply_regions.gpkg",
        base / "data" / "bundle" / "supply_regions" / "rsa_supply_regions2.gpkg",
        base / "data" / "bundle" / "GCCA 2025 GIS" / "AREAS_GCCA2025.gpkg",
    ]
    rows: list[dict] = []
    for path in candidates:
        if not path.exists():
            rows.append(
                {
                    "layer_path": str(path),
                    "layer_name": "",
                    "feature_count": -1,
                    "matched_canonical_resolution": "none",
                    "notes": "absent at pin",
                }
            )
            continue
        layers = _safe_listlayers(path)
        for layer in layers:
            gdf = _gdf_or_none(path, layer)
            if gdf is None:
                rows.append(
                    {
                        "layer_path": str(path.relative_to(base)),
                        "layer_name": layer,
                        "feature_count": -1,
                        "matched_canonical_resolution": "none",
                        "notes": "failed to read layer",
                    }
                )
                continue
            n = int(len(gdf))
            match = n if n in CANONICAL_SUPPLY_REGIONS else "none"
            rows.append(
                {
                    "layer_path": str(path.relative_to(base)),
                    "layer_name": layer,
                    "feature_count": n,
                    "matched_canonical_resolution": match,
                    "notes": "" if match != "none" else "feature count outside {1,10,27,34,159}",
                }
            )
    # Also probe shapefile-based supply areas (GCCA 2025 SUPPLY_AREA / LOCAL_AREA / MTS_ZONES)
    shp_targets = [
        base / "data" / "bundle" / "GCCA 2025 GIS" / "SUPPLY_AREA_GCCA2025.shp",
        base / "data" / "bundle" / "GCCA 2025 GIS" / "LOCAL_AREA_GCCA2025.shp",
        base / "data" / "bundle" / "GCCA 2025 GIS" / "MTS_ZONES_GCCA2025.shp",
    ]
    for path in shp_targets:
        if not path.exists():
            continue
        gdf = _gdf_or_none(path)
        if gdf is None:
            continue
        n = int(len(gdf))
        match = n if n in CANONICAL_SUPPLY_REGIONS else "none"
        rows.append(
            {
                "layer_path": str(path.relative_to(base)),
                "layer_name": "<single-layer-shp>",
                "feature_count": n,
                "matched_canonical_resolution": match,
                "notes": "" if match != "none" else "feature count outside {1,10,27,34,159}",
            }
        )
    df = pd.DataFrame(rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return len(df)


def export_supply_regions_geojson(pypsa_rsa_root: Path, out_path: Path) -> int:
    """Export the canonical 27-region layer as a GeoJSON convenience copy."""
    gpkg = Path(pypsa_rsa_root) / "data" / "bundle" / "supply_regions" / "rsa_supply_regions.gpkg"
    layers = _safe_listlayers(gpkg)
    target = "27" if "27" in layers else (layers[0] if layers else None)
    if target is None:
        return write_geojson(None, out_path)
    gdf = _gdf_or_none(gpkg, target)
    return write_geojson(gdf, out_path)


def export_existing_lines_220kv_plus(pypsa_rsa_root: Path, out_path: Path) -> int:
    base = Path(pypsa_rsa_root)
    path = base / "data" / "bundle" / "Shapefiles" / "Existing_Lines.shp"
    gdf = _gdf_or_none(path)
    if gdf is None:
        return write_geojson(None, out_path)
    voltage_col = next(
        (c for c in gdf.columns if c.upper() in {"DESIGN_VOL", "VOLTAGE", "NOMINAL_VO"}),
        None,
    )
    if voltage_col is not None:
        v = pd.to_numeric(gdf[voltage_col], errors="coerce").fillna(0)
        gdf = gdf[v >= EXISTING_LINE_KV_THRESHOLD].copy()
    return write_geojson(gdf, out_path)


def export_planned_tdp_lines(pypsa_rsa_root: Path, out_path: Path) -> int:
    base = Path(pypsa_rsa_root)
    path = base / "data" / "bundle" / "transmission_grid" / "tdp_digitised" / "TDP_2023_32.shp"
    gdf = _gdf_or_none(path)
    return write_geojson(gdf, out_path)


def build_supply_area_connection_limits(pypsa_rsa_root: Path, out_path: Path) -> int:
    base = Path(pypsa_rsa_root)
    path = base / "data" / "bundle" / "Shapefiles" / "Supply_Areas2022_Steady_State_Limit.shp"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        pd.DataFrame().to_csv(out_path, index=False)
        return 0
    gdf = _gdf_or_none(path)
    if gdf is None:
        pd.DataFrame().to_csv(out_path, index=False)
        return 0
    df = pd.DataFrame(gdf.drop(columns=[c for c in gdf.columns if c.lower() == "geometry"]))
    df.to_csv(out_path, index=False)
    return len(df)


def build_mts_hosting_limits(pypsa_rsa_root: Path, out_path: Path) -> int:
    base = Path(pypsa_rsa_root)
    path = base / "data" / "bundle" / "Shapefiles" / "MTS_Subs2022.shp"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        pd.DataFrame().to_csv(out_path, index=False)
        return 0
    gdf = _gdf_or_none(path)
    if gdf is None:
        pd.DataFrame().to_csv(out_path, index=False)
        return 0
    df = pd.DataFrame(gdf.drop(columns=[c for c in gdf.columns if c.lower() == "geometry"]))
    df.to_csv(out_path, index=False)
    return len(df)


def build_transmission_expansion_audit(pypsa_rsa_root: Path, out_path: Path) -> int:
    """Combine ME IRP + Coal Flex transmission_expansion workbooks + planned shapefile."""
    base = Path(pypsa_rsa_root)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for scenario_set, rel in [
        ("ME IRP 2024", "scenarios/ME IRP 2024/sub_scenarios/transmission_expansion.xlsx"),
        ("Coal_Flexibilisation", "scenarios/Coal_Flexibilisation/sub_scenarios/transmission_expansion.xlsx"),
    ]:
        path = base / rel
        if not path.exists():
            continue
        try:
            xl = pd.ExcelFile(path)
        except Exception:
            continue
        for sheet in xl.sheet_names:
            df = xl.parse(sheet)
            df.insert(0, "scenario_set", scenario_set)
            df.insert(1, "sheet", sheet)
            df.insert(2, "source_path", rel)
            rows.append(df)
    df = pd.concat(rows, ignore_index=True, sort=False) if rows else pd.DataFrame()

    # Append digitised planned-corridor evidence as a flat audit table.
    tdp_shp = base / "data" / "bundle" / "transmission_grid" / "tdp_digitised" / "TDP_2023_32.shp"
    gdf = _gdf_or_none(tdp_shp)
    if gdf is not None and len(gdf):
        flat = pd.DataFrame(gdf.drop(columns=[c for c in gdf.columns if c.lower() == "geometry"]))
        flat.insert(0, "scenario_set", "TDP_DIGITISED")
        flat.insert(1, "sheet", "TDP_2023_32")
        flat.insert(2, "source_path", "data/bundle/transmission_grid/tdp_digitised/TDP_2023_32.shp")
        df = pd.concat([df, flat], ignore_index=True, sort=False)

    df.to_csv(out_path, index=False)
    return len(df)
