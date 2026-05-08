# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""ZA Module 04 — resource siting audit (expansion-only evidence)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .io import sha256_of_file


SITING_TARGETS = [
    ("data/bundle/Power_corridors", "directory", "Power corridors"),
    ("data/bundle/REDZ_DEA_Unpublished_Draft_2015", "directory", "REDZ DEA unpublished draft"),
    ("data/bundle/Phase2_REDZs", "directory", "Phase 2 REDZs"),
    ("data/bundle/SAPAD_OR_2023_Q3.shp", "shp", "Protected areas (SAPAD)"),
    ("data/bundle/SACAD_OR_2023_Q3.shp", "shp", "Conservation areas (SACAD)"),
    ("data/bundle/SALandCover_OriginalUTM35North_2013_GTI_72Classes", "directory", "Land cover raster set"),
    ("data/bundle/ZAF_wind-speed_100m.tif", "raster", "Wind speed @100m"),
    ("data/bundle/ZAF15adjv4.tif", "raster", "Adjusted DEM"),
    ("data/bundle/Shapefiles/RE_IPP_1_to_4b.shp", "shp", "REIPPPP rounds 1-4b siting"),
    ("pre_processing/resource_processing", "directory", "PyPSA-RSA resource processing pre-pipeline"),
]


def _shape_count(path: Path) -> int:
    try:
        import geopandas as gpd

        return int(len(gpd.read_file(path)))
    except Exception:
        return -1


def _dir_summary(path: Path) -> tuple[int, int]:
    """Return (file_count, total_bytes) for a directory tree. (-1, -1) if absent."""
    if not path.exists() or not path.is_dir():
        return -1, -1
    files = 0
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            files += 1
            try:
                total += p.stat().st_size
            except Exception:
                pass
    return files, total


def build_resource_siting_audit(pypsa_rsa_root: Path, out_path: Path) -> int:
    base = Path(pypsa_rsa_root)
    rows: list[dict] = []
    for rel, kind, description in SITING_TARGETS:
        path = base / rel
        rec = {
            "rel_path": rel,
            "kind": kind,
            "description": description,
            "present": path.exists(),
            "feature_count": -1,
            "file_count": -1,
            "size_bytes": -1,
            "hash": "",
        }
        if not path.exists():
            rows.append(rec)
            continue
        if kind == "shp":
            rec["feature_count"] = _shape_count(path)
            rec["hash"] = sha256_of_file(path)
            try:
                rec["size_bytes"] = path.stat().st_size
            except Exception:
                pass
        elif kind == "raster":
            rec["hash"] = sha256_of_file(path)
            try:
                rec["size_bytes"] = path.stat().st_size
            except Exception:
                pass
        elif kind == "directory":
            files, size = _dir_summary(path)
            rec["file_count"] = files
            rec["size_bytes"] = size
        rows.append(rec)
    df = pd.DataFrame(rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return len(df)
