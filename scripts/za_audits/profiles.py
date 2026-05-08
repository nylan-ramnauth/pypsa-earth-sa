# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""ZA Module 04 — profile reference audit (Eskom pu + supply-area xlsx + nc)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .io import list_xlsx_sheets, sha256_of_file


def _eskom_pu_profile_summary(path: Path) -> list[dict]:
    """Compute per-carrier coverage and basic statistics for the Eskom pu CSV."""
    if not path.exists():
        return []
    df = pd.read_csv(path)
    # Row 0 is the units row ("time (SAST)" / "normalised feed-in [MW/MW]"); drop it.
    if str(df.iloc[0, 0]).startswith("time"):
        df = df.iloc[1:].reset_index(drop=True)
    df = df.rename(columns={df.columns[0]: "timestamp"})
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    summary = []
    for col in df.columns[1:]:
        series = pd.to_numeric(df[col], errors="coerce")
        non_null = series.dropna()
        summary.append(
            {
                "source": "data/eskom_pu_profiles.csv",
                "carrier": col,
                "row_count": int(len(series)),
                "non_null_count": int(len(non_null)),
                "min": float(non_null.min()) if len(non_null) else None,
                "max": float(non_null.max()) if len(non_null) else None,
                "mean": float(non_null.mean()) if len(non_null) else None,
                "first_timestamp": str(df["timestamp"].min()),
                "last_timestamp": str(df["timestamp"].max()),
                "hash": sha256_of_file(path),
            }
        )
    return summary


def _supply_area_normalised_summary(path: Path, label: str) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for s in list_xlsx_sheets(path):
        out.append(
            {
                "source": f"data/bundle/{path.name}",
                "carrier": label,
                "sheet": s["sheet"],
                "row_count": s["n_rows"] - 1 if s["n_rows"] > 0 else 0,
                "n_cols": s["n_cols"],
                "columns_sample": "|".join((s["columns"] or [])[:8]),
                "hash": sha256_of_file(path),
            }
        )
    return out


def _renewable_profiles_nc_summary(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        import xarray as xr

        ds = xr.open_dataset(path)
        info = {
            "source": "data/bundle/renewable_profiles_updated.nc",
            "carrier": "all",
            "data_vars": "|".join(map(str, list(ds.data_vars))),
            "dims": "|".join(f"{k}={v}" for k, v in ds.sizes.items()),
            "attrs": "|".join(f"{k}={v}" for k, v in ds.attrs.items())[:200],
            "hash": sha256_of_file(path),
        }
        ds.close()
        return [info]
    except Exception as exc:  # noqa: BLE001
        return [{"source": "data/bundle/renewable_profiles_updated.nc", "carrier": "all", "error": str(exc), "hash": sha256_of_file(path)}]


def build_eskom_pu_profiles_audit(pypsa_rsa_root: Path, out_path: Path) -> int:
    base = Path(pypsa_rsa_root)
    rows: list[dict] = []
    rows.extend(_eskom_pu_profile_summary(base / "data" / "eskom_pu_profiles.csv"))
    rows.extend(
        _supply_area_normalised_summary(
            base / "data" / "bundle" / "Supply area normalised power feed-in for Wind.xlsx",
            "wind",
        )
    )
    rows.extend(
        _supply_area_normalised_summary(
            base / "data" / "bundle" / "Supply area normalised power feed-in for PV.xlsx",
            "solar_pv",
        )
    )
    rows.extend(_renewable_profiles_nc_summary(base / "data" / "bundle" / "renewable_profiles_updated.nc"))
    df = pd.DataFrame(rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return len(df)
