# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Per-carrier 2023 installed-capacity anchors derived from Eskom hourly data.

Reads ``data/za_audit/raw/eskom_data_2023_full.csv`` (raw hourly Eskom data),
filters to 2023-01-01 .. 2023-12-31, and emits
``data/za_audit/za_eskom_2023_capacity_anchors.csv``.

The Eskom hourly file exposes ``*_Installed_Capacity`` columns only for
renewable carriers (Wind, PV, CSP, Other RE, Total RE) plus the aggregate
``Installed Eskom Capacity``. Per-carrier conventional anchors (coal /
nuclear / OCGT / Sasol) are NOT split in the raw file and are recorded as
``available: False`` in the anchor CSV. Module 12 must source those
anchors elsewhere (Eskom Annual Report 2023, IRP 2023).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd


ANCHOR_COLUMNS = [
    "carrier",
    "p_nom_mw_2023_max",
    "p_nom_mw_2023_min",
    "p_nom_mw_2023_mean",
    "available",
    "source_column",
    "source_path",
    "source_hash",
    "notes",
]

CARRIER_TO_COLUMN = {
    "onwind": "Wind Installed Capacity",
    "solar": "PV Installed Capacity",
    "csp": "CSP Installed Capacity",
    "other_re": "Other RE Installed Capacity",
    "total_re": "Total RE Installed Capacity",
    "eskom_total": "Installed Eskom Capacity",
}

# Carriers without per-carrier anchors in the raw hourly feed.
UNAVAILABLE_CARRIERS = [
    "coal",
    "nuclear",
    "ocgt_diesel",
    "ocgt_gas",
    "sasol_coal",
    "sasol_gas",
    "hydro",
    "ror",
    "PHS",
    "battery",
    "biomass",
]


def build_anchor_rows(
    eskom_raw_csv: Path,
    source_hash: str,
    timestamp_col: str = "Date Time Hour Beginning",
) -> list[dict]:
    df = pd.read_csv(eskom_raw_csv, low_memory=False)
    df[timestamp_col] = pd.to_datetime(df[timestamp_col], errors="coerce")
    df = df.loc[(df[timestamp_col] >= "2023-01-01") & (df[timestamp_col] < "2024-01-01")].copy()

    rows: list[dict] = []
    for carrier, col in CARRIER_TO_COLUMN.items():
        if col not in df.columns:
            rows.append({
                "carrier": carrier,
                "p_nom_mw_2023_max": "",
                "p_nom_mw_2023_min": "",
                "p_nom_mw_2023_mean": "",
                "available": False,
                "source_column": col,
                "source_path": str(eskom_raw_csv),
                "source_hash": source_hash,
                "notes": f"column '{col}' not present in raw file",
            })
            continue
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if series.empty:
            rows.append({
                "carrier": carrier,
                "p_nom_mw_2023_max": "",
                "p_nom_mw_2023_min": "",
                "p_nom_mw_2023_mean": "",
                "available": False,
                "source_column": col,
                "source_path": str(eskom_raw_csv),
                "source_hash": source_hash,
                "notes": "no numeric observations in 2023 window",
            })
            continue
        rows.append({
            "carrier": carrier,
            "p_nom_mw_2023_max": float(series.max()),
            "p_nom_mw_2023_min": float(series.min()),
            "p_nom_mw_2023_mean": float(series.mean()),
            "available": True,
            "source_column": col,
            "source_path": str(eskom_raw_csv),
            "source_hash": source_hash,
            "notes": f"derived from {len(series)} hourly observations 2023-01-01..2023-12-31",
        })

    for carrier in UNAVAILABLE_CARRIERS:
        rows.append({
            "carrier": carrier,
            "p_nom_mw_2023_max": "",
            "p_nom_mw_2023_min": "",
            "p_nom_mw_2023_mean": "",
            "available": False,
            "source_column": "",
            "source_path": str(eskom_raw_csv),
            "source_hash": source_hash,
            "notes": (
                "Eskom hourly feed does not expose per-carrier installed capacity for this carrier; "
                "use Eskom Annual Report 2023 / IRP 2023 as anchor source for Module 12"
            ),
        })

    return rows


def write_anchors_csv(rows: list[dict], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=ANCHOR_COLUMNS)
    df.to_csv(out_path, index=False, float_format="%.3f")
    return len(df)
