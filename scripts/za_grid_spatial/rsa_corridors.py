# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build pypsa-rsa-style ≥220 kV corridor benchmark with N-1 derating.

St Clair coefficients (53.736, -0.65) are taken from pypsa-rsa
`scripts/build_topology.py:241-253`. They differ from the literature-standard
Dunlop fit (43.261, -0.6678); see `doc/za_grid_reconciliation.md`.
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString

PROJ_M = "EPSG:32735"
VOLTAGE_KV_BUCKETS = [220, 275, 400, 765]


def _classify_voltage(v_kv: float) -> int | None:
    for bucket in VOLTAGE_KV_BUCKETS:
        if abs(v_kv - bucket) <= 5:
            return bucket
    if v_kv >= 765:
        return 765
    if v_kv >= 400:
        return 400
    if v_kv >= 275:
        return 275
    if v_kv >= 220:
        return 220
    return None


def st_clair_limit_mw(length_km: float, voltage_kv: int, sil_mw: dict, thermal_mw: dict,
                     a: float = 53.736, b: float = -0.65) -> float:
    """Per-line St Clair limit: min(thermal, SIL * a * length_km^b)."""
    if length_km <= 0 or voltage_kv not in sil_mw:
        return float("nan")
    sil = float(sil_mw[voltage_kv])
    thermal = float(thermal_mw[voltage_kv])
    return float(min(thermal, sil * a * (length_km ** b)))


def assign_lines_to_regions(
    lines: gpd.GeoDataFrame, regions: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """Map each line endpoint to a region. Lines wholly inside one region are intra-regional."""
    lines = lines.copy()
    starts = gpd.GeoDataFrame(
        geometry=lines.geometry.apply(lambda g: g.coords[0]).apply(
            lambda c: gpd.points_from_xy([c[0]], [c[1]])[0]
        ),
        crs=lines.crs,
    )
    ends = gpd.GeoDataFrame(
        geometry=lines.geometry.apply(lambda g: g.coords[-1]).apply(
            lambda c: gpd.points_from_xy([c[0]], [c[1]])[0]
        ),
        crs=lines.crs,
    )
    starts = gpd.sjoin(starts, regions[["region_id", "geometry"]], how="left", predicate="within")
    ends = gpd.sjoin(ends, regions[["region_id", "geometry"]], how="left", predicate="within")

    lines["bus0_region"] = starts["region_id"].values
    lines["bus1_region"] = ends["region_id"].values
    return lines


def build_corridor_table(
    lines_geojson: Path,
    regions: gpd.GeoDataFrame,
    sil_mw: dict[int, float],
    thermal_mw: dict[int, float],
    n1_factor: float = 0.7,
    st_clair_a: float = 53.736,
    st_clair_b: float = -0.65,
) -> pd.DataFrame:
    """Return interregional corridor table with thermal/SIL/St Clair/N-1 caps."""
    lines = gpd.read_file(lines_geojson)
    if "DESIGN_VOL" not in lines.columns:
        raise KeyError(
            "expected DESIGN_VOL column in existing-lines geojson; "
            "available: " + ", ".join(lines.columns)
        )
    # voltage normalisation
    lines["voltage_kv"] = lines["DESIGN_VOL"].apply(_classify_voltage)
    lines = lines.dropna(subset=["voltage_kv"]).copy()
    lines["voltage_kv"] = lines["voltage_kv"].astype(int)

    # length in km (meters projection)
    proj_lines = lines.to_crs(PROJ_M)
    lines["length_km"] = proj_lines.geometry.length / 1000.0

    # per-line limits
    lines["thermal_mw"] = lines.apply(
        lambda r: float(thermal_mw.get(r["voltage_kv"], float("nan"))), axis=1
    )
    lines["sil_mw"] = lines.apply(
        lambda r: float(sil_mw.get(r["voltage_kv"], float("nan"))), axis=1
    )
    lines["st_clair_mw"] = lines.apply(
        lambda r: st_clair_limit_mw(
            r["length_km"], int(r["voltage_kv"]), sil_mw, thermal_mw, st_clair_a, st_clair_b
        ),
        axis=1,
    )

    # assign endpoints to regions (sjoin requires matching CRS)
    regions_geo = regions[["region_id", "geometry"]].to_crs(lines.crs)
    lines = assign_lines_to_regions(lines, regions_geo)

    # drop intra-regional and unassigned-endpoint lines
    mask_inter = (
        lines["bus0_region"].notna()
        & lines["bus1_region"].notna()
        & (lines["bus0_region"] != lines["bus1_region"])
    )
    inter = lines[mask_inter].copy()
    # canonicalise corridor key (alphabetical)
    inter["corridor_a"] = np.where(
        inter["bus0_region"] <= inter["bus1_region"], inter["bus0_region"], inter["bus1_region"]
    )
    inter["corridor_b"] = np.where(
        inter["bus0_region"] <= inter["bus1_region"], inter["bus1_region"], inter["bus0_region"]
    )

    grouped = inter.groupby(["corridor_a", "corridor_b"], as_index=False)
    rows = []
    for (a, b), grp in grouped:
        n_lines = len(grp)
        thermal_sum = float(grp["thermal_mw"].sum())
        sil_sum = float(grp["sil_mw"].sum())
        st_clair_sum = float(grp["st_clair_mw"].sum())
        if n_lines <= 1:
            st_clair_n1 = float(grp["st_clair_mw"].sum() * n1_factor)
        else:
            # drop strongest line, sum the rest
            sorted_lines = grp.sort_values("st_clair_mw", ascending=False)
            st_clair_n1 = float(sorted_lines["st_clair_mw"].iloc[1:].sum())
        rows.append(
            {
                "bus0": a,
                "bus1": b,
                "n_lines": n_lines,
                "voltage_max_kv": int(grp["voltage_kv"].max()),
                "voltage_min_kv": int(grp["voltage_kv"].min()),
                "total_length_km": float(grp["length_km"].sum()),
                "thermal_sum_mw": thermal_sum,
                "sil_sum_mw": sil_sum,
                "st_clair_sum_mw": st_clair_sum,
                "st_clair_n1_mw": st_clair_n1,
                "n1_factor": n1_factor,
                "st_clair_a": st_clair_a,
                "st_clair_b": st_clair_b,
            }
        )

    df = pd.DataFrame(rows).sort_values(["bus0", "bus1"]).reset_index(drop=True)
    return df
