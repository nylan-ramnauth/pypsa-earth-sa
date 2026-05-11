# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build custom busmap mapping simplified PyPSA-Earth buses to 34 Eskom regions.

`cluster_network.py` reads this file with `pd.read_csv(path, index_col=0).squeeze()`,
so the file must be a 2-column CSV: `bus,region_id` with `bus` as index.
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
import pypsa
from shapely.geometry import Point

PROJ_M = "EPSG:32735"


def assign_buses_to_regions(
    elec_s_nc: Path, regions: gpd.GeoDataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (busmap_df, coverage_df). busmap has index=bus, column region_id."""
    n = pypsa.Network(str(elec_s_nc))
    buses = n.buses[["x", "y", "country"]].copy()
    if "country" in buses.columns:
        buses = buses[buses["country"].isin(["ZA", "South Africa", ""])]
    if buses.empty:
        buses = n.buses[["x", "y"]].copy()

    buses_reset = buses.reset_index()
    # PyPSA n.buses index is typically named "Bus" or "name"; coerce to "bus".
    first_col = buses_reset.columns[0]
    if first_col != "bus":
        buses_reset = buses_reset.rename(columns={first_col: "bus"})
    bus_points = gpd.GeoDataFrame(
        buses_reset,
        geometry=[Point(xy) for xy in zip(buses["x"], buses["y"])],
        crs="EPSG:4326",
    )

    # point-in-polygon assignment
    regions_geo = regions[["region_id", "geometry"]].to_crs("EPSG:4326")
    joined = gpd.sjoin(bus_points, regions_geo, how="left", predicate="within")
    # drop duplicate sjoin matches (boundary overlap)
    joined = joined.drop_duplicates(subset="bus", keep="first")

    # nearest-centroid fallback for unassigned buses (off-shore or in gap polygons)
    unassigned_mask = joined["region_id"].isna()
    if unassigned_mask.any():
        projected_regions = regions.to_crs(PROJ_M)
        centroids = gpd.GeoDataFrame(
            {"region_id": regions["region_id"].values},
            geometry=projected_regions.geometry.centroid,
            crs=PROJ_M,
        ).to_crs("EPSG:4326")
        unassigned_pts = joined.loc[unassigned_mask, ["bus", "geometry"]].copy()
        # nearest sjoin
        nearest = gpd.sjoin_nearest(
            unassigned_pts.to_crs(PROJ_M),
            centroids.to_crs(PROJ_M),
            how="left",
        ).drop_duplicates(subset="bus", keep="first")
        nearest_map = dict(zip(nearest["bus"], nearest["region_id"]))
        joined.loc[unassigned_mask, "region_id"] = joined.loc[unassigned_mask, "bus"].map(
            nearest_map
        )

    busmap_df = (
        joined[["bus", "region_id"]]
        .dropna(subset=["region_id"])
        .set_index("bus")
        .sort_index()
    )

    # coverage stats
    all_buses = set(buses.index.astype(str))
    mapped_buses = set(busmap_df.index.astype(str))
    unassigned = sorted(all_buses - mapped_buses)
    target_regions = set(regions["region_id"].astype(str))
    used_regions = set(busmap_df["region_id"].astype(str))
    orphan_regions = sorted(target_regions - used_regions)

    coverage_df = pd.DataFrame(
        [
            {
                "metric": "n_input_buses",
                "value": len(all_buses),
                "detail": "",
            },
            {
                "metric": "n_mapped_buses",
                "value": len(mapped_buses),
                "detail": "",
            },
            {
                "metric": "unassigned_buses",
                "value": len(unassigned),
                "detail": ",".join(unassigned[:50]),
            },
            {
                "metric": "n_target_regions",
                "value": len(target_regions),
                "detail": "",
            },
            {
                "metric": "n_used_regions",
                "value": len(used_regions),
                "detail": "",
            },
            {
                "metric": "orphan_regions",
                "value": len(orphan_regions),
                "detail": ",".join(orphan_regions),
            },
            {
                "metric": "buses_per_region_mean",
                "value": round(len(mapped_buses) / max(len(used_regions), 1), 3),
                "detail": "",
            },
        ]
    )
    return busmap_df, coverage_df


def write_busmap_csv(busmap_df: pd.DataFrame, path: Path) -> Path:
    """Write 2-column CSV for cluster_network: index=bus, col=region_id."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # cluster_network does pd.read_csv(path, index_col=0).squeeze() → Series.
    # n.buses.index is object/str in PyPSA, so coerce to str to keep dtypes
    # aligned when consumers reindex against the simplified network.
    out = busmap_df.copy()
    out.index = out.index.astype(str)
    out.index.name = "bus"
    out.to_csv(path)
    return path
