# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Materialise ``data/custom_powerplants.csv`` from the reconciliation rows.

Schema (Name-indexed; loaded upstream via
``read_csv_nafix(custom_powerplants, index_col=0, dtype={'bus': 'str'})``)::

    Name, Fueltype, Technology, Set, Country, Capacity, Efficiency, Duration,
    Volume_Mm3, DamHeight_m, StorageCapacity_MWh, DateIn, DateRetrofit,
    DateOut, lat, lon, EIC, projectID, bus

Module 08 leaves ``bus`` blank for all rows — the upstream KDTree assignment
handles the smoke; Module 09 finalises explicit bus assignments.

PHS storage hours: per-station ``StorageCapacity_MWh`` values are sourced
from the Module 04 ``Max Storage (GWh)`` column when present, falling back
to the Module 08 reference table (Drakensberg=24h, Ingula=14h, Palmiet=12h,
Steenbras=20h × p_nom_mw).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .reconciliation import V1_TO_FUELTYPE, make_unique_names

CUSTOM_COLUMNS = [
    "Name",
    "Fueltype",
    "Technology",
    "Set",
    "Country",
    "Capacity",
    "Efficiency",
    "Duration",
    "Volume_Mm3",
    "DamHeight_m",
    "StorageCapacity_MWh",
    "DateIn",
    "DateRetrofit",
    "DateOut",
    "lat",
    "lon",
    "EIC",
    "projectID",
    "bus",
]

PHS_REFERENCE_HOURS = {
    "Drakensberg": 24,
    "Ingula":      14,
    "Palmiet":     12,
    "Steenbras":   20,
}


def _csp_plant_keys() -> set:
    """Canonical lowercase keys for the six 2023 CSP plants."""
    return {"kaxu solar one", "khi solar one", "bokpoort", "kathu", "xina solar one", "ilanga csp", "ilanga-1 csp", "ilanga 1"}


def _is_csp_2023_plant(name: str) -> bool:
    return name.lower().strip() in _csp_plant_keys()


def _phs_storage_mwh(canonical_name: str, p_nom_mw: float, notes_text: str) -> tuple:
    """Return (StorageCapacity_MWh, source_note) for a PHS station.

    Order of preference:
      1. ``Max Storage (GWh)`` parsed from reconciliation notes (Module 04 audit).
      2. Reference fallback table.
    """
    # Try parsing Max Storage (GWh) from notes
    for kv in (notes_text or "").split(";"):
        if "storage_gwh=" in kv:
            v = kv.split("=", 1)[1].strip()
            try:
                gwh = float(v)
                if gwh > 0:
                    return gwh * 1000.0, "Module 04 audit Max Storage (GWh)"
            except (ValueError, TypeError):
                pass
    # Fallback to reference table
    hours = PHS_REFERENCE_HOURS.get(canonical_name)
    if hours is None or not p_nom_mw:
        return "", "no storage data available; Module 10 must address"
    return float(hours) * float(p_nom_mw), f"Module 08 reference table (hours={hours})"


def _csp_storage_mwh(notes_text: str) -> tuple:
    """CSP storage hours stored in notes only; left blank in custom_powerplants
    per plan. Return ('', note)."""
    return "", "CSP storage hours preserved in za_named_plant_inventory.csv notes for Module 10 csp_model"


def build_custom_rows(reconciliation_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Convert include-decision reconciliation rows to custom_powerplants schema.

    Returns (custom_rows, phs_audit_rows).
    """
    rows = make_unique_names(reconciliation_rows)
    custom: list[dict] = []
    phs_audit: list[dict] = []

    seen_names: set = set()
    for r in rows:
        if r.get("decision") != "include":
            continue
        v1 = r["carrier"]
        if v1 not in V1_TO_FUELTYPE:
            # hydro_import, imports, exports, other_re — not custom_powerplants rows.
            continue
        fueltype, technology, set_kind = V1_TO_FUELTYPE[v1]
        name = r["unique_name"]
        if not name or name in seen_names:
            continue
        seen_names.add(name)

        cap = float(r.get("capacity_mw_final") or 0.0)
        if cap <= 0:
            continue

        # Upstream KDTree bus assignment requires finite lat/lon — drop rows
        # without coordinates. Documented as V1 limitation in the reconciliation
        # doc + implementation log.
        lat_v = r.get("lat_final")
        lon_v = r.get("lon_final")
        if lat_v in (None, "") or lon_v in (None, "") or pd.isna(lat_v) or pd.isna(lon_v):
            continue

        # Storage handling.
        storage_mwh = ""
        if v1 == "PHS":
            storage_mwh, src_note = _phs_storage_mwh(r["canonical_name"], cap, r.get("notes", ""))
            phs_audit.append({
                "station_name": r["canonical_name"],
                "p_nom_mw": cap,
                "max_hours": (storage_mwh / cap) if (isinstance(storage_mwh, (int, float)) and storage_mwh and cap) else "",
                "storage_capacity_mwh": storage_mwh if storage_mwh != "" else "",
                "source_path": r.get("source_rsa", ""),
                "source_note": src_note,
            })
        elif v1 == "csp":
            storage_mwh, _ = _csp_storage_mwh(r.get("notes", ""))

        custom.append({
            "Name": name,
            "Fueltype": fueltype,
            "Technology": technology,
            "Set": set_kind,
            "Country": "ZA",
            "Capacity": cap,
            "Efficiency": "",
            "Duration": "",
            "Volume_Mm3": "",
            "DamHeight_m": "",
            "StorageCapacity_MWh": storage_mwh,
            "DateIn": r.get("date_in_final") or 1990,
            "DateRetrofit": "",
            "DateOut": r.get("date_out_final") if r.get("date_out_final") not in (None, "") else "",
            "lat": r.get("lat_final") if r.get("lat_final") not in (None, "") else "",
            "lon": r.get("lon_final") if r.get("lon_final") not in (None, "") else "",
            "EIC": "",
            "projectID": _project_id(r),
            "bus": "",
        })

    return custom, phs_audit


def _project_id(r: dict) -> str:
    parts = []
    if r.get("source_rsa"):
        parts.append("RSA_FIXED_TECHNOLOGIES")
    if r.get("source_reipppp"):
        parts.append("REIPPPP")
    if r.get("source_ppm"):
        parts.append("PPM")
    return "|".join(parts) or "RSA_FIXED_TECHNOLOGIES"


def write_custom_powerplants_csv(rows: list[dict], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=CUSTOM_COLUMNS)
    df.to_csv(out_path, index=False, float_format="%.6f")
    return len(df)


PHS_AUDIT_COLUMNS = [
    "station_name",
    "p_nom_mw",
    "max_hours",
    "storage_capacity_mwh",
    "source_path",
    "source_note",
]


def write_phs_audit_csv(rows: list[dict], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=PHS_AUDIT_COLUMNS)
    df.to_csv(out_path, index=False, float_format="%.3f")
    return len(df)
