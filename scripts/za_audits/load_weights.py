# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""ZA Module 04 — load weight (GVA_2016 + POP_2016) audit + Mesozones traversal."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .io import sha256_of_file


def _gva_pop_summary(gpkg_path: Path) -> list[dict]:
    if not gpkg_path.exists():
        return []
    try:
        import fiona
        import geopandas as gpd
    except Exception as exc:  # noqa: BLE001
        return [{"source": str(gpkg_path), "error": str(exc)}]
    rows = []
    try:
        layers = fiona.listlayers(str(gpkg_path))
    except Exception as exc:  # noqa: BLE001
        return [{"source": str(gpkg_path), "error": str(exc)}]
    file_hash = sha256_of_file(gpkg_path)
    for layer in layers:
        try:
            gdf = gpd.read_file(gpkg_path, layer=layer)
        except Exception:
            continue
        cols = list(gdf.columns)
        gva_col = next((c for c in cols if c.upper().replace("_", "") in {"GVA2016", "GVA"}), None)
        pop_col = next((c for c in cols if c.upper().replace("_", "") in {"POP2016", "POP"}), None)
        rec = {
            "source_path": gpkg_path.name,
            "layer": layer,
            "feature_count": int(len(gdf)),
            "has_gva_2016": gva_col is not None,
            "has_pop_2016": pop_col is not None,
            "gva_column": gva_col or "",
            "pop_column": pop_col or "",
            "hash": file_hash,
        }
        if gva_col:
            v = pd.to_numeric(gdf[gva_col], errors="coerce")
            rec["gva_sum"] = float(v.sum())
            rec["gva_min"] = float(v.min()) if len(v) else None
            rec["gva_max"] = float(v.max()) if len(v) else None
        if pop_col:
            v = pd.to_numeric(gdf[pop_col], errors="coerce")
            rec["pop_sum"] = float(v.sum())
            rec["pop_min"] = float(v.min()) if len(v) else None
            rec["pop_max"] = float(v.max()) if len(v) else None
        rows.append(rec)
    return rows


def _mesozones_traversal(meso_dir: Path) -> list[dict]:
    if not meso_dir.exists() or not meso_dir.is_dir():
        return []
    rows = []
    try:
        import fiona
    except Exception:
        fiona = None
    for path in sorted(meso_dir.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix not in {".gpkg", ".shp", ".csv", ".xlsx"}:
            continue
        rec = {
            "source_path": str(path.relative_to(meso_dir)),
            "suffix": suffix,
            "size_bytes": path.stat().st_size,
            "hash": sha256_of_file(path),
            "layers": "",
        }
        if suffix == ".gpkg" and fiona is not None:
            try:
                rec["layers"] = "|".join(fiona.listlayers(str(path)))
            except Exception:
                pass
        rows.append(rec)
    return rows


def build_load_weight_audit(pypsa_rsa_root: Path, out_path: Path) -> int:
    base = Path(pypsa_rsa_root)
    rows: list[dict] = []
    rows.extend(_gva_pop_summary(base / "data" / "bundle" / "supply_regions" / "rsa_supply_regions.gpkg"))
    rows.extend(_gva_pop_summary(base / "data" / "bundle" / "supply_regions" / "rsa_supply_regions2.gpkg"))
    meso_rows = _mesozones_traversal(base / "data" / "bundle" / "CSIR" / "Mesozones")
    for r in meso_rows:
        r.setdefault("layer", "")
        r.setdefault("feature_count", -1)
        r.setdefault("has_gva_2016", False)
        r.setdefault("has_pop_2016", False)
    rows.extend(meso_rows)
    df = pd.DataFrame(rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return len(df)
