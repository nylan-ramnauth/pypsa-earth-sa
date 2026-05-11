# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Post-``build_powerplants`` normalization smoke diff.

Compares ``data/custom_powerplants.csv`` against
``resources/<run>/powerplants.csv`` and reports every:
- canonical row dropped by ``powerplants_filter``
- carrier remapping (Fueltype/Technology → carrier translation)
- capacity shift > 1 MW
- unintended addition (row present in resources but absent from custom)

Does NOT invoke Snakemake itself — the smoke is run from
``build_za_fleet_reconciliation.py`` after the rest of the artifacts are
materialised. If ``resources/<run>/powerplants.csv`` does not yet exist
(initial build), every custom row is logged as ``pending_smoke``.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DIFF_COLUMNS = [
    "canonical_name",
    "carrier",
    "fueltype_custom",
    "technology_custom",
    "p_nom_custom",
    "p_nom_pm",
    "delta_mw",
    "bus_assigned",
    "max_hours_pm",
    "status",
    "notes",
]


def build_smoke_diff(
    custom_csv: Path,
    resources_powerplants_csv: Path,
) -> list[dict]:
    if not custom_csv.exists():
        return []
    custom = pd.read_csv(custom_csv)
    if "Name" not in custom.columns:
        return []
    custom["_name_lc"] = custom["Name"].astype(str).str.lower()

    rows: list[dict] = []

    if not resources_powerplants_csv.exists():
        for _, c in custom.iterrows():
            rows.append({
                "canonical_name":    c["Name"],
                "carrier":           "",
                "fueltype_custom":   c.get("Fueltype", ""),
                "technology_custom": c.get("Technology", ""),
                "p_nom_custom":      float(c.get("Capacity") or 0.0),
                "p_nom_pm":          "",
                "delta_mw":          "",
                "bus_assigned":      "",
                "max_hours_pm":      "",
                "status":            "pending_smoke",
                "notes":             "resources/<run>/powerplants.csv not yet built",
            })
        return rows

    pm = pd.read_csv(resources_powerplants_csv)
    # build_powerplants writes the Name-indexed frame back with the index
    # column unnamed (header is blank). The Name values are preserved if the
    # original Name index survived; if not, the column is the integer position.
    # Detect: if first column header is empty or "Unnamed: 0", treat as Name.
    first_col = pm.columns[0]
    if first_col in ("", "Unnamed: 0"):
        pm = pm.rename(columns={first_col: "Name"})
    # Match key: prefer Name if available + non-integer; fall back to a
    # (Capacity, lat, lon) tuple-based key that survives the upstream index reset.
    pm.columns = [str(c).lower() if str(c) != "Name" else "Name" for c in pm.columns]
    if "Name" in pm.columns and not pd.api.types.is_integer_dtype(pm["Name"]):
        pm["_name_lc"] = pm["Name"].astype(str).str.lower()
        custom_key = custom["_name_lc"]
    else:
        # Fallback: match on (capacity, lat, lon) tuple.
        pm["_key"] = (
            pd.to_numeric(pm.get("capacity"), errors="coerce").round(3).astype(str)
            + "|" + pd.to_numeric(pm.get("lat"), errors="coerce").round(4).astype(str)
            + "|" + pd.to_numeric(pm.get("lon"), errors="coerce").round(4).astype(str)
        )
        custom["_key"] = (
            pd.to_numeric(custom["Capacity"], errors="coerce").round(3).astype(str)
            + "|" + pd.to_numeric(custom["lat"], errors="coerce").round(4).astype(str)
            + "|" + pd.to_numeric(custom["lon"], errors="coerce").round(4).astype(str)
        )
        pm["_name_lc"] = pm["_key"]
        custom["_name_lc"] = custom["_key"]
    name_col = "Name" if "Name" in pm.columns else pm.columns[0]

    custom_names = set(custom["_name_lc"])
    pm_names = set(pm["_name_lc"])

    for _, c in custom.iterrows():
        nm = c["_name_lc"]
        p_nom_custom = float(c.get("Capacity") or 0.0)
        match = pm[pm["_name_lc"] == nm]
        if match.empty:
            rows.append({
                "canonical_name":    c["Name"],
                "carrier":           "",
                "fueltype_custom":   c.get("Fueltype", ""),
                "technology_custom": c.get("Technology", ""),
                "p_nom_custom":      p_nom_custom,
                "p_nom_pm":          "",
                "delta_mw":          "",
                "bus_assigned":      "",
                "max_hours_pm":      "",
                "status":            "dropped_by_filter",
                "notes":             "row absent from resources/<run>/powerplants.csv after build_powerplants",
            })
            continue
        m = match.iloc[0]
        p_nom_pm = float(m.get("p_nom") or m.get("capacity") or 0.0)
        delta = p_nom_pm - p_nom_custom
        carrier_pm = m.get("carrier", "") if "carrier" in match.columns else ""
        bus_assigned = m.get("bus", "") if "bus" in match.columns else ""
        max_hours_pm = m.get("max_hours", "") if "max_hours" in match.columns else ""
        status = "ok"
        notes_parts = []
        if abs(delta) > 1.0:
            status = "capacity_shifted"
            notes_parts.append(f"|delta|={abs(delta):.2f} MW > 1 MW tolerance")
        rows.append({
            "canonical_name":    c["Name"],
            "carrier":           carrier_pm,
            "fueltype_custom":   c.get("Fueltype", ""),
            "technology_custom": c.get("Technology", ""),
            "p_nom_custom":      p_nom_custom,
            "p_nom_pm":          p_nom_pm,
            "delta_mw":          delta,
            "bus_assigned":      bus_assigned,
            "max_hours_pm":      max_hours_pm,
            "status":            status,
            "notes":             "; ".join(notes_parts),
        })

    # Unintended additions: pm rows that did NOT originate from custom.
    for _, m in pm.iterrows():
        nm = m["_name_lc"]
        if nm in custom_names:
            continue
        rows.append({
            "canonical_name":    m[name_col],
            "carrier":           m.get("carrier", "") if "carrier" in pm.columns else "",
            "fueltype_custom":   "",
            "technology_custom": "",
            "p_nom_custom":      "",
            "p_nom_pm":          float(m.get("p_nom") or m.get("capacity") or 0.0),
            "delta_mw":          "",
            "bus_assigned":      m.get("bus", "") if "bus" in pm.columns else "",
            "max_hours_pm":      m.get("max_hours", "") if "max_hours" in pm.columns else "",
            "status":            "unintended_addition",
            "notes":             "row present in resources but absent from custom (suspect powerplantmatching IRENA leak under custom_powerplants:replace)",
        })

    return rows


def write_diff_csv(rows: list[dict], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=DIFF_COLUMNS)
    df.to_csv(out_path, index=False, float_format="%.4f")
    return len(df)
