# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Load the 34 Eskom supply-region layer from pypsa-rsa pinned bundle."""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd

GEO_CRS = "EPSG:4326"

SUPPLY_REGION_GPKG_REL = Path("data/bundle/supply_regions/rsa_supply_regions.gpkg")


def load_34_layer(pypsa_rsa_root: Path) -> gpd.GeoDataFrame:
    """Return the 34-feature supply-region layer in EPSG:4326.

    Adds a stable `region_id` column (zero-padded LocalArea name) for downstream joins.
    """
    gpkg = pypsa_rsa_root / SUPPLY_REGION_GPKG_REL
    if not gpkg.exists():
        raise FileNotFoundError(f"pypsa-rsa supply-region gpkg missing: {gpkg}")
    gdf = gpd.read_file(gpkg, layer="34")
    if len(gdf) != 34:
        raise ValueError(f"expected 34 features in supply-region layer 34, got {len(gdf)}")
    gdf = gdf.to_crs(GEO_CRS)
    # Region id = LocalArea (Eskom local-area name).
    gdf["region_id"] = gdf["LocalArea"].astype(str).str.strip()
    if gdf["region_id"].duplicated().any():
        dups = gdf.loc[gdf["region_id"].duplicated(keep=False), "region_id"].tolist()
        raise ValueError(f"duplicate LocalArea names in 34-layer: {dups}")
    return gdf[["region_id", "SupplyArea", "LocalArea", "OBJECTID", "Shape_Area", "geometry"]]


def supply_region_centroids(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Centroid geometry per region (uses EPSG:32735 to compute then reprojects back)."""
    projected = gdf.to_crs("EPSG:32735")
    out = gdf.copy()
    out["geometry"] = projected.geometry.centroid.to_crs(GEO_CRS)
    return out
