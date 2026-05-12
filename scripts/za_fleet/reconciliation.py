# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build ``data/za_audit/za_powerplant_reconciliation.csv``.

Reads the Module 04 audit CSVs:

- ``data/za_audit/pypsa_rsa_fixed_technologies_2023_candidates.csv``
- ``data/za_audit/reipppp_wind_2023_candidates.csv``
- ``data/za_audit/reipppp_solar_2023_candidates.csv``

Filters the PyPSA-RSA fixed-technology fleet to scenario_set='ME IRP 2024' /
Scenario='BASE' (canonical view), retains rows operational in 2023 by
commissioning_year/decommissioning_year, and joins REIPPPP wind/solar
candidates flagged ``included_2023 == True``. Emits one canonical
reconciliation row per plant, retaining provenance back to the source CSVs.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RECONCILIATION_COLUMNS = [
    "canonical_name",
    "carrier",
    "technology",
    "capacity_mw_final",
    "capacity_mw_ppm",
    "capacity_mw_rsa",
    "capacity_mw_reipppp",
    "eskom_anchor_capacity_mw",
    "anchor_delta_mw",
    "date_in_final",
    "date_out_final",
    "lat_final",
    "lon_final",
    "source_ppm",
    "source_rsa",
    "source_reipppp",
    "status_2023",
    "included_2023",
    "decision",
    "decision_reason",
    "notes",
]

# PyPSA-RSA carrier strings to V1 calibration plan carriers.
RSA_TO_V1 = {
    "coal": "coal",
    "nuclear": "nuclear",
    "sasol_coal": "sasol_coal",
    "sasol_gas": "sasol_gas",
    "ocgt_diesel": "ocgt_diesel",
    "ocgt_gas": "ocgt_gas",
    "ocgt_avf": "ocgt_diesel",       # AVF (aviation fuel) treated as diesel for V1
    "wind": "onwind",
    "solar_pv": "solar",
    "solar_pv_rooftop": "solar",
    "solar_csp": "csp",
    "hydro": "hydro",
    "ror": "ror",
    "phs": "PHS",
    "battery_4h": "battery",
    "bioenergy": "biomass",
    "hydro_import": "hydro_import",   # excluded from custom_powerplants by Module 08
    "rmippp": "ocgt_diesel",          # Risk Mitigation IPP — peaker diesel for V1
}

# V1 carrier → (Fueltype, Technology, Set) tuple for custom_powerplants.csv.
V1_TO_FUELTYPE = {
    "coal":         ("Hard Coal",   "Steam Turbine",    "PP"),
    "nuclear":      ("Nuclear",     "Steam Turbine",    "PP"),
    "sasol_coal":   ("Hard Coal",   "Steam Turbine",    "PP"),
    "sasol_gas":    ("Natural Gas", "OCGT",             "PP"),
    "ocgt_diesel":  ("Oil",         "OCGT",             "PP"),
    "ocgt_gas":     ("Natural Gas", "OCGT",             "PP"),
    "onwind":       ("Wind",        "Onshore",          "PP"),
    "solar":        ("Solar",       "PV",               "PP"),
    "csp":          ("Solar",       "CSP",              "PP"),
    "hydro":        ("Hydro",       "Reservoir",        "PP"),
    "ror":          ("Hydro",       "Run-Of-River",     "PP"),
    "PHS":          ("Hydro",       "Pumped Storage",   "Store"),
    "battery":      ("Battery",     "Battery Storage",  "Store"),
    "biomass":      ("Bioenergy",   "Steam Turbine",    "PP"),
}


def _canonical_name(raw: str) -> str:
    """Strip trailing decommissioning markers (`*`, `**`, whitespace)."""
    if pd.isna(raw):
        return ""
    s = str(raw).strip()
    while s.endswith("*"):
        s = s[:-1]
    return s.strip()


def _to_year(value, default_in: int = None, default_out: int = None):
    if pd.isna(value):
        return None
    try:
        v = float(value)
        if np.isnan(v):
            return None
        return int(v)
    except (ValueError, TypeError):
        return None


def _filter_rsa_2023_active(rsa: pd.DataFrame) -> pd.DataFrame:
    """Keep BASE scenario rows operational in 2023.

    A row is operational in 2023 if commissioning_year <= 2023 (or NaN) AND
    decommissioning_year >= 2023 (or NaN).
    """
    df = rsa[(rsa["scenario_set"] == "ME IRP 2024") & (rsa["Scenario"] == "BASE")].copy()
    cy = pd.to_numeric(df["commissioning_year"], errors="coerce")
    dy = pd.to_numeric(df["decommissioning_year"], errors="coerce")
    active = ((cy.isna()) | (cy <= 2023)) & ((dy.isna()) | (dy >= 2023))
    return df.loc[active].copy()


def build_reconciliation_rows(
    rsa_csv: Path,
    reipppp_wind_csv: Path,
    reipppp_solar_csv: Path,
) -> list[dict]:
    rsa = pd.read_csv(rsa_csv, low_memory=False)
    wind = pd.read_csv(reipppp_wind_csv, low_memory=False)
    solar = pd.read_csv(reipppp_solar_csv, low_memory=False)

    rsa_active = _filter_rsa_2023_active(rsa)
    rows: list[dict] = []

    # --- 1. PyPSA-RSA fixed_technologies rows ---
    for _, r in rsa_active.iterrows():
        rsa_carrier = str(r.get("Carrier", "")).strip()
        v1_carrier = RSA_TO_V1.get(rsa_carrier)
        if v1_carrier is None or v1_carrier == "hydro_import":
            continue
        # Skip onwind/solar — REIPPPP loops (2 and 3) are authoritative for these
        # carriers. Keeping RSA rows duplicates every wind/solar plant (~2× capacity
        # error) and adds 4,439 MW of `Existing distributed solar PV` aggregates that
        # are already netted into `RSA Contracted Demand` (double-count). CSP stays
        # because Loop 3 skips CSP — RSA is its only source.
        if v1_carrier in ("onwind", "solar"):
            continue
        raw_name = str(r.get("Power Station Name", "")).strip()
        canonical = _canonical_name(raw_name)
        if not canonical:
            continue
        cy = _to_year(r.get("commissioning_year"))
        dy = _to_year(r.get("decommissioning_year"))
        # date_in_final: ground in canonical 2023 fleet; if commissioning_year missing,
        # assume the unit predates 2023 — use a sentinel year (1990) for upstream filter.
        date_in_final = cy if cy is not None else 1990
        # date_out_final: leave blank if station operates beyond 2023.
        date_out_final = "" if (dy is None or dy > 2023) else dy
        # status_2023
        if dy is not None and dy < 2023:
            status = "retired"
        elif cy is not None and cy == 2023:
            status = "commissioning"
        elif dy is not None and dy == 2023:
            status = "retiring"
        else:
            status = "operating"
        rows.append({
            "canonical_name": canonical,
            "raw_name": raw_name,
            "carrier": v1_carrier,
            "rsa_carrier": rsa_carrier,
            "technology": V1_TO_FUELTYPE.get(v1_carrier, ("","","" ))[1],
            "capacity_mw_final": float(r.get("Capacity (MW)") or 0.0),
            "capacity_mw_ppm": "",
            "capacity_mw_rsa": float(r.get("Capacity (MW)") or 0.0),
            "capacity_mw_reipppp": "",
            "eskom_anchor_capacity_mw": "",
            "anchor_delta_mw": "",
            "date_in_final": date_in_final,
            "date_out_final": date_out_final,
            "lat_final": r.get("GPS Latitude") if pd.notna(r.get("GPS Latitude")) else "",
            "lon_final": r.get("GPS Longitude") if pd.notna(r.get("GPS Longitude")) else "",
            "source_ppm": "",
            "source_rsa": f"{rsa_csv} (scenario_set=ME IRP 2024, Scenario=BASE, sheet={r.get('sheet','')})",
            "source_reipppp": "",
            "status_2023": status,
            "included_2023": True,
            "decision": "include",
            "decision_reason": "active 2023 by commissioning/decommissioning year in PyPSA-RSA BASE scenario",
            "notes": (
                f"raw_name='{raw_name}'; csp_storage_hours="
                f"{r.get('CSP Storage Hours','')}; max_storage_hours="
                f"{r.get('Max Storage (hours)','')}; storage_gwh="
                f"{r.get('Max Storage (GWh)','')}"
            ),
        })

    # --- 2. REIPPPP wind rows (included_2023 == True) ---
    for _, r in wind[wind["included_2023"] == True].iterrows():
        canonical = _canonical_name(r.get("Name"))
        cap = float(r.get("capacity") or 0.0)
        cy = _to_year(r.get("commissioning_year"))
        dy = _to_year(r.get("decommissioning_year"))
        rows.append({
            "canonical_name": canonical,
            "raw_name": canonical,
            "carrier": "onwind",
            "rsa_carrier": "wind",
            "technology": "Onshore",
            "capacity_mw_final": cap,
            "capacity_mw_ppm": "",
            "capacity_mw_rsa": "",
            "capacity_mw_reipppp": cap,
            "eskom_anchor_capacity_mw": "",
            "anchor_delta_mw": "",
            "date_in_final": cy if cy is not None else 2015,
            "date_out_final": "" if (dy is None or dy > 2023) else dy,
            "lat_final": r.get("latitude") if pd.notna(r.get("latitude")) else "",
            "lon_final": r.get("longitude") if pd.notna(r.get("longitude")) else "",
            "source_ppm": "",
            "source_rsa": "",
            "source_reipppp": str(reipppp_wind_csv),
            "status_2023": "operating",
            "included_2023": True,
            "decision": "include",
            "decision_reason": "REIPPPP wind project flagged included_2023 == True in Module 04 audit",
            "notes": f"COD={r.get('COD','')}; status={r.get('status','')}",
        })

    # --- 3. REIPPPP solar (PV only — CSP comes from PyPSA-RSA fixed_tech) ---
    for _, r in solar[solar["included_2023"] == True].iterrows():
        canonical = _canonical_name(r.get("Name"))
        cap = float(r.get("capacity") or 0.0)
        cy = _to_year(r.get("commissioning_year"))
        dy = _to_year(r.get("decommissioning_year"))
        rtype = str(r.get("Type", "")).strip().upper()
        if rtype == "CSP":
            # Skip — CSP plants come from the PyPSA-RSA fixed_tech path to retain storage metadata.
            continue
        rows.append({
            "canonical_name": canonical,
            "raw_name": canonical,
            "carrier": "solar",
            "rsa_carrier": "solar_pv",
            "technology": "PV",
            "capacity_mw_final": cap,
            "capacity_mw_ppm": "",
            "capacity_mw_rsa": "",
            "capacity_mw_reipppp": cap,
            "eskom_anchor_capacity_mw": "",
            "anchor_delta_mw": "",
            "date_in_final": cy if cy is not None else 2015,
            "date_out_final": "" if (dy is None or dy > 2023) else dy,
            "lat_final": r.get("latitude") if pd.notna(r.get("latitude")) else "",
            "lon_final": r.get("longitude") if pd.notna(r.get("longitude")) else "",
            "source_ppm": "",
            "source_rsa": "",
            "source_reipppp": str(reipppp_solar_csv),
            "status_2023": "operating",
            "included_2023": True,
            "decision": "include",
            "decision_reason": "REIPPPP solar PV project flagged included_2023 == True in Module 04 audit",
            "notes": f"COD={r.get('COD','')}; status={r.get('status','')}; type={rtype}",
        })

    return rows


def make_unique_names(rows: list[dict]) -> list[dict]:
    """Ensure `Name` uniqueness for custom_powerplants `index_col=0` requirement.

    PyPSA-RSA emits `Camden*` (570 MW) and `Camden**` (911 MW) as distinct unit
    groups. After canonicalisation both become `Camden`, so we append a
    deterministic disambiguator (`Camden`, `Camden_2`, ...) per (carrier).
    """
    counts: dict[tuple, int] = {}
    for row in rows:
        key = (row["canonical_name"], row["carrier"])
        n = counts.get(key, 0) + 1
        counts[key] = n
        if n == 1:
            row["unique_name"] = row["canonical_name"]
        else:
            row["unique_name"] = f"{row['canonical_name']}_{n}"
    return rows


def write_reconciliation_csv(rows: list[dict], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    # Drop intermediate helper cols that aren't part of the canonical reconciliation schema.
    for c in ("raw_name", "rsa_carrier", "unique_name"):
        if c in df.columns:
            df = df.drop(columns=c)
    df = df.reindex(columns=RECONCILIATION_COLUMNS)
    df.to_csv(out_path, index=False, float_format="%.4f")
    return len(df)
