# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Bus-attachment audit CSVs for plants, demand, imports/exports, and other_re.

Plant attachment: assigns 34-region per (lat,lon) AND back-fills the `bus` column
in `data/custom_powerplants.csv` only for rows where it is blank (preserves
Module 08 contract).
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point

PROJ_M = "EPSG:32735"


def _point_in_region(lat: float, lon: float, regions_4326: gpd.GeoDataFrame) -> str | None:
    if pd.isna(lat) or pd.isna(lon):
        return None
    point = Point(float(lon), float(lat))
    hits = regions_4326[regions_4326.contains(point)]
    if not hits.empty:
        return str(hits.iloc[0]["region_id"])
    # nearest centroid fallback in projected meters
    projected_regions = regions_4326.to_crs(PROJ_M)
    proj_pt = gpd.GeoSeries([point], crs="EPSG:4326").to_crs(PROJ_M).iloc[0]
    distances = projected_regions.geometry.centroid.distance(proj_pt)
    return str(regions_4326.iloc[int(distances.idxmin())]["region_id"])


def assign_plants(
    custom_powerplants_csv: Path,
    regions: gpd.GeoDataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """Return (audit_df, updated_powerplants_df, n_backfilled).

    audit_df: every plant with its assigned 34-region.
    updated_powerplants_df: same shape as input; `bus` filled where blank.
    """
    pp = pd.read_csv(custom_powerplants_csv, index_col=0)
    regions_4326 = regions[["region_id", "geometry"]].to_crs("EPSG:4326")

    assignments: list[str | None] = []
    for _, row in pp.iterrows():
        lat = row.get("lat")
        lon = row.get("lon")
        assignments.append(_point_in_region(lat, lon, regions_4326))

    audit_df = pd.DataFrame(
        {
            "Name": pp.index,
            "Fueltype": pp.get("Fueltype", ""),
            "Capacity_MW": pp.get("Capacity", np.nan),
            "lat": pp.get("lat", np.nan),
            "lon": pp.get("lon", np.nan),
            "bus_module08_blank": pp["bus"].isna()
            | (pp["bus"].astype(str).str.strip() == ""),
            "assigned_region": assignments,
        }
    )

    # back-fill bus only where it was blank
    updated = pp.copy()
    blank_mask = updated["bus"].isna() | (updated["bus"].astype(str).str.strip() == "")
    n_backfilled = int(blank_mask.sum())
    updated.loc[blank_mask, "bus"] = [a for a, b in zip(assignments, blank_mask) if b]

    # sanity guard — fail loudly if any blank remains
    still_blank = updated["bus"].isna() | (updated["bus"].astype(str).str.strip() == "")
    if still_blank.any():
        raise RuntimeError(
            f"after back-fill, {int(still_blank.sum())} plants have no bus; "
            f"likely missing lat/lon for: {updated.index[still_blank].tolist()}"
        )
    return audit_df, updated, n_backfilled


def build_demand_attachment(
    load_weights_csv: Path, regions: gpd.GeoDataFrame
) -> pd.DataFrame:
    """Map Module 06 national load to 34 regions via polygon-area share (audit only).

    Active disaggregation is done by `build_demand_profiles.py` using GDP/POP layouts;
    this CSV is provenance for the 34-region attachment, not a model input.
    """
    src = pd.read_csv(load_weights_csv)
    projected = regions.to_crs(PROJ_M)
    region_area = projected.geometry.area.values
    total = float(region_area.sum())
    weights = region_area / total
    rows = []
    for src_row in src.itertuples(index=False):
        for region_name, w in zip(regions["region_id"].values, weights):
            rows.append(
                {
                    "spatial_level": 34,
                    "attachment_type": "demand",
                    "source_id": getattr(src_row, "source_id", "RSA"),
                    "target_region_id": region_name,
                    "weight_area_share": float(w),
                    "notes_module06": getattr(src_row, "notes", ""),
                    "notes_module09": "area-share proxy; active disaggregation in build_demand_profiles",
                }
            )
    return pd.DataFrame(rows)


def build_other_re_attachment(
    other_re_csv: Path, regions: gpd.GeoDataFrame
) -> pd.DataFrame:
    """Distribute national `other_re` time-series by area share (audit only)."""
    src = pd.read_csv(other_re_csv)
    projected = regions.to_crs(PROJ_M)
    region_area = projected.geometry.area.values
    total = float(region_area.sum())
    weights = region_area / total
    rows = []
    for src_row in src.itertuples(index=False):
        for region_name, w in zip(regions["region_id"].values, weights):
            rows.append(
                {
                    "spatial_level": 34,
                    "attachment_type": "other_re",
                    "source_id": getattr(src_row, "source_id", "Other RE"),
                    "target_region_id": region_name,
                    "weight_area_share": float(w),
                    "notes_module06": getattr(src_row, "notes", ""),
                    "notes_module09": "area-share proxy; Eskom hourly source lacks plant locations",
                }
            )
    return pd.DataFrame(rows)


def build_import_export_attachment(
    import_export_csv: Path,
    regions: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """Attach each external interconnector to a frontier region.

    V1 attaches "International Imports" to Polokwane (Limpopo) as proxy for
    Cahora Bassa HVDC routing through Apollo substation. Documented as proxy.
    """
    src = pd.read_csv(import_export_csv)
    # frontier proxy: northern region
    proxy_region = "Polokwane"
    available = set(regions["region_id"].astype(str))
    if proxy_region not in available:
        # fallback to first SupplyArea=='Limpopo' region or northernmost by centroid latitude
        northernmost = regions.copy()
        projected = regions.to_crs(PROJ_M)
        northernmost["cent_lat"] = projected.geometry.centroid.to_crs("EPSG:4326").y
        proxy_region = str(
            northernmost.sort_values("cent_lat", ascending=False).iloc[0]["region_id"]
        )
    rows = []
    for src_row in src.itertuples(index=False):
        rows.append(
            {
                "spatial_level": 34,
                "attachment_type": getattr(src_row, "attachment_type", "import"),
                "source_id": getattr(src_row, "source_id", "International Imports"),
                "target_region_id": proxy_region,
                "weight": 1.0,
                "notes_module06": getattr(src_row, "notes", ""),
                "notes_module09": (
                    f"V1 proxy: attached to {proxy_region}; "
                    "Cahora Bassa HVDC routing via Apollo substation"
                ),
            }
        )
    return pd.DataFrame(rows)
