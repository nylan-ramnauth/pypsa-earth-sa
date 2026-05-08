# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""ZA Module 04 — fleet, REIPPPP, availability, op-constraints, reserve audits."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

# Filter rule from plan §"Fleet, Availability, And REIPPPP Audits":
#   Commissioning Date <= 2023
#   AND
#   (Decommissioning Date > 2023 OR Decommissioning Date IS NULL)
COD_THRESHOLD = 2023


def _normalise_year(value) -> float | None:
    """Coerce a workbook 'date' cell to a numeric year. None when missing."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if pd.isna(value):
            return None
        return float(value)
    s = str(value).strip()
    if s in {"", "-", "n/a", "na", "NaN", "nan"}:
        return None
    m = re.search(r"(19|20)\d{2}", s)
    if m:
        return float(m.group(0))
    try:
        return float(s)
    except Exception:
        return None


def _apply_2023_filter(df: pd.DataFrame, cod_col: str, dec_col: str) -> pd.DataFrame:
    cod = df[cod_col].apply(_normalise_year)
    dec = df[dec_col].apply(_normalise_year) if dec_col in df.columns else pd.Series([None] * len(df))
    cod_ok = cod.fillna(0) <= COD_THRESHOLD  # missing CoD treated as already-online
    cod_ok &= cod.notna() | True  # keep "missing" as True per plan ("missing" handled positively for CoD only when value is real)
    # The plan filter requires Commissioning Date <= 2023; treat missing CoD as online for legacy assets.
    cod_ok = cod.apply(lambda v: True if v is None else v <= COD_THRESHOLD)
    dec_ok = dec.apply(lambda v: True if v is None else v > COD_THRESHOLD)
    df = df.copy()
    df["commissioning_year"] = cod
    df["decommissioning_year"] = dec
    df["included_2023"] = (cod_ok & dec_ok).values
    return df


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_fixed_technologies_audit(pypsa_rsa_root: Path, out_path: Path) -> int:
    """Combine ME IRP 2024 + Coal Flex fixed_technologies workbooks."""
    base = Path(pypsa_rsa_root)
    workbooks = [
        ("ME IRP 2024", base / "scenarios" / "ME IRP 2024" / "sub_scenarios" / "fixed_technologies.xlsx"),
        ("Coal_Flexibilisation", base / "scenarios" / "Coal_Flexibilisation" / "sub_scenarios" / "fixed_technologies.xlsx"),
    ]
    frames = []
    for scenario_set, path in workbooks:
        if not path.exists():
            continue
        for sheet in pd.ExcelFile(path).sheet_names:
            df = pd.read_excel(path, sheet_name=sheet)
            df.insert(0, "scenario_set", scenario_set)
            df.insert(1, "sheet", sheet)
            frames.append(df)
    if not frames:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame().to_csv(out_path, index=False)
        return 0
    df = pd.concat(frames, ignore_index=True, sort=False)
    df = _apply_2023_filter(df, "Commissioning Date", "Decommissioning Date")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return len(df)


def build_reipppp_solar_audit(pypsa_rsa_root: Path, out_path: Path) -> int:
    src = Path(pypsa_rsa_root) / "pre_processing" / "resource_processing" / "reipppp_solar_data.csv"
    if not src.exists():
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame().to_csv(out_path, index=False)
        return 0
    df = pd.read_csv(src)
    # COD is commissioning date; status indicates operational vs preferred-bidder
    df = _apply_2023_filter(df.assign(_dec=None), "COD", "_dec")
    df = df.drop(columns=["_dec"], errors="ignore")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return len(df)


def build_reipppp_wind_audit(pypsa_rsa_root: Path, out_path: Path) -> int:
    src = Path(pypsa_rsa_root) / "pre_processing" / "resource_processing" / "reipppp_wind_data.csv"
    if not src.exists():
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame().to_csv(out_path, index=False)
        return 0
    df = pd.read_csv(src)
    df = _apply_2023_filter(df.assign(_dec=None), "COD", "_dec")
    df = df.drop(columns=["_dec"], errors="ignore")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return len(df)


def _melt_workbook_to_long(path: Path, scenario_set: str) -> pd.DataFrame:
    """Read every sheet of an xlsx and return a long-format frame."""
    if not path.exists():
        return pd.DataFrame()
    out = []
    for sheet in pd.ExcelFile(path).sheet_names:
        df = pd.read_excel(path, sheet_name=sheet)
        df.insert(0, "scenario_set", scenario_set)
        df.insert(1, "sheet", sheet)
        out.append(df)
    if not out:
        return pd.DataFrame()
    return pd.concat(out, ignore_index=True, sort=False)


def build_availability_audit(pypsa_rsa_root: Path, out_path: Path) -> int:
    base = Path(pypsa_rsa_root)
    workbooks = [
        ("ME IRP 2024", base / "scenarios" / "ME IRP 2024" / "sub_scenarios" / "plant_availability.xlsx"),
        ("Coal_Flexibilisation", base / "scenarios" / "Coal_Flexibilisation" / "sub_scenarios" / "plant_availability.xlsx"),
    ]
    frames = [_melt_workbook_to_long(p, s) for s, p in workbooks]
    df = pd.concat([f for f in frames if not f.empty], ignore_index=True, sort=False) if frames else pd.DataFrame()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return len(df)


def build_operational_constraints_audit(pypsa_rsa_root: Path, out_path: Path) -> int:
    base = Path(pypsa_rsa_root)
    workbooks = [
        ("ME IRP 2024", base / "scenarios" / "ME IRP 2024" / "sub_scenarios" / "operational_constraints.xlsx"),
        ("Coal_Flexibilisation", base / "scenarios" / "Coal_Flexibilisation" / "sub_scenarios" / "operational_constraints.xlsx"),
    ]
    frames = [_melt_workbook_to_long(p, s) for s, p in workbooks]
    df = pd.concat([f for f in frames if not f.empty], ignore_index=True, sort=False) if frames else pd.DataFrame()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return len(df)


def build_reserve_margin_audit(pypsa_rsa_root: Path, out_path: Path) -> int:
    base = Path(pypsa_rsa_root)
    workbooks = [
        ("ME IRP 2024", base / "scenarios" / "ME IRP 2024" / "sub_scenarios" / "reserve_margin.xlsx"),
        ("Coal_Flexibilisation", base / "scenarios" / "Coal_Flexibilisation" / "sub_scenarios" / "reserve_margin.xlsx"),
    ]
    frames = [_melt_workbook_to_long(p, s) for s, p in workbooks]
    df = pd.concat([f for f in frames if not f.empty], ignore_index=True, sort=False) if frames else pd.DataFrame()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return len(df)
