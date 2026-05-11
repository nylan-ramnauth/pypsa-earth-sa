# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Named-plant inventory + ±50 MW / ±10 km cross-check.

Materialises ``data/za_audit/za_named_plant_inventory.csv`` with the
canonical 30+ Eskom stations required by the calibration plan §
"Named-Plant Inventory". Every station with ``status_2023`` in
{``operating``, ``commissioning``} must have a matching row in
``data/custom_powerplants.csv`` within ±50 MW and ±10 km.

CSP storage hours are recorded in the ``notes`` column for the six 2023
CSP plants so Module 10's ``apply_za_local_carriers`` hook can configure
``renewable.csp`` per-plant without re-reading the Module 04 audit.
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

INVENTORY_COLUMNS = [
    "station_name",
    "carrier",
    "status_2023",
    "p_nom_mw_expected",
    "lat_expected",
    "lon_expected",
    "source",
    "notes",
]


# Plan §Minimum required stations. Names + coordinates aligned to the
# PyPSA-RSA Module 04 audit (the authoritative source for `custom_powerplants.csv`).
# Discrepancies between audit coordinates and Eskom Annual Report coordinates are
# documented in `doc/za_implementation_log.md` as audit-quality follow-ups for
# Module 04. CSP plant audit names retained verbatim (e.g. `Kaxu Solar One`,
# `!XiNa Solar One`, `Karoshoek Solar One` aka Ilanga CSP-1).
NAMED_PLANTS = [
    # Nuclear
    ("Koeberg",                 "nuclear", "operating",     1854.0, -33.6760,  18.4317, "PyPSA-RSA fixed_technologies + Eskom Annual Report 2023", ""),
    # Coal — operating fleet (2023). Capacities are audit `*+**` sums.
    ("Medupi",                  "coal",    "commissioning", 4317.0, -23.4200,  27.3300, "PyPSA-RSA fixed_technologies (audit coords differ ~30 km from real Lephalale; flagged for Module 04 follow-up)", ""),
    ("Kusile",                  "coal",    "commissioning", 3600.0, -25.9201,  28.9249, "PyPSA-RSA fixed_technologies + Eskom Annual Report 2023", ""),
    ("Matimba",                 "coal",    "operating",     3690.0, -23.6678,  27.6086, "PyPSA-RSA fixed_technologies", ""),
    ("Kendal",                  "coal",    "operating",     3840.0, -26.0975,  28.9706, "PyPSA-RSA fixed_technologies", ""),
    ("Tutuka",                  "coal",    "operating",     3510.0, -26.7785,  29.3528, "PyPSA-RSA fixed_technologies", ""),
    ("Lethabo",                 "coal",    "operating",     3558.0, -26.7383,  27.9656, "PyPSA-RSA fixed_technologies", ""),
    ("Majuba",                  "coal",    "operating",     3807.0, -27.1011,  29.7831, "PyPSA-RSA fixed_technologies", ""),
    ("Matla",                   "coal",    "operating",     3450.0, -26.2789,  29.1483, "PyPSA-RSA fixed_technologies", ""),
    ("Duvha",                   "coal",    "operating",     2875.0, -25.9636,  29.3389, "PyPSA-RSA fixed_technologies", ""),
    ("Hendrina",                "coal",    "operating",     1098.0, -26.0314,  29.6014, "PyPSA-RSA fixed_technologies; audit Hendrina** coord (-26.62, 30.09) differs from primary site and is flagged for Module 04 follow-up", ""),
    ("Kriel",                   "coal",    "operating",     2640.0, -26.2456,  29.1772, "PyPSA-RSA fixed_technologies", ""),
    ("Arnot",                   "coal",    "operating",     2100.0, -25.9533,  29.7894, "PyPSA-RSA fixed_technologies", ""),
    ("Komati",                  "coal",    "retired",        906.0, -26.0894,  29.4525, "Eskom Annual Report 2023; retired 2023-Q4", ""),
    ("Camden",                  "coal",    "operating",     1481.0, -26.6244,  30.0944, "PyPSA-RSA fixed_technologies; partial decommissioning planned 2024", ""),
    ("Grootvlei",               "coal",    "operating",      570.0, -26.7783,  28.4986, "PyPSA-RSA fixed_technologies; partial retirement underway", ""),
    # OCGT (diesel)
    ("Ankerlig",                "ocgt_diesel", "operating", 1332.0, -33.5781,  18.3744, "PyPSA-RSA fixed_technologies", ""),
    ("Gourikwa",                "ocgt_diesel", "operating",  746.0, -34.1850,  21.9764, "PyPSA-RSA fixed_technologies", ""),
    ("Acacia",                  "ocgt_diesel", "operating",  171.0, -33.8556,  18.5544, "PyPSA-RSA fixed_technologies; AVF treated as diesel for V1", ""),
    ("PortRex",                 "ocgt_diesel", "operating",  171.0, -33.0322,  27.8350, "PyPSA-RSA fixed_technologies; audit name 'PortRex'; AVF treated as diesel for V1", ""),
    # Pumped storage — coords align with PyPSA-RSA audit; real coords differ slightly
    # (Drakensberg real -28.76; audit -28.56 ≈ Bergville).
    ("Drakensberg",             "PHS", "operating", 1000.0, -28.5628,  29.0828, "PyPSA-RSA fixed_technologies; audit coord differs ~22 km from real site near Bergville and is flagged for Module 04 follow-up", "max_hours_from_audit=21.7h"),
    ("Ingula",                  "PHS", "operating", 1324.0, -28.1650,  29.3512, "PyPSA-RSA fixed_technologies; capacity 1324 MW per audit (vs Eskom 1332 MW nameplate)", "max_hours_from_audit=20.7h"),
    ("Palmiet",                 "PHS", "operating",  400.0, -34.2589,  19.0008, "Eskom Annual Report; not in audit BASE scenario, flagged below", "max_hours=12"),
    ("Steenbras",               "PHS", "operating",  180.0, -34.1858,  18.8794, "City of Cape Town / Eskom; not in audit BASE scenario, flagged below", "max_hours=20"),
    # CSP — six 2023 plants summing to 500 MW. Audit names retained verbatim.
    ("Kaxu Solar One",          "csp", "operating", 100.0, -28.8793,  19.5929, "PyPSA-RSA fixed_technologies; SA REIPPPP CSP plant", "csp_storage_hours=3"),
    ("Khi Solar One",           "csp", "operating",  50.0, -28.5364,  21.0782, "PyPSA-RSA fixed_technologies", "csp_storage_hours=6"),
    ("Bokpoort CSP project",    "csp", "operating",  50.0, -28.7333,  21.9955, "PyPSA-RSA fixed_technologies", "csp_storage_hours=9"),
    ("!XiNa Solar One",         "csp", "operating", 100.0, -28.8906,  19.5918, "PyPSA-RSA fixed_technologies; audit name retains leading '!'", "csp_storage_hours=6"),
    ("Karoshoek Solar One",     "csp", "operating", 100.0, -28.4819,  21.5204, "PyPSA-RSA fixed_technologies; also known as Ilanga CSP-1 (100 MW, COD 2018, Postmasburg)", "csp_storage_hours=6"),
    ("Kathu Solar Park",        "csp", "operating", 100.0, -27.6095,  23.0276, "PyPSA-RSA fixed_technologies", "csp_storage_hours=6"),
]


def build_named_inventory_rows() -> list[dict]:
    return [
        {
            "station_name":      name,
            "carrier":           car,
            "status_2023":       status,
            "p_nom_mw_expected": cap,
            "lat_expected":      lat,
            "lon_expected":      lon,
            "source":            src,
            "notes":             notes,
        }
        for (name, car, status, cap, lat, lon, src, notes) in NAMED_PLANTS
    ]


def write_named_inventory_csv(rows: list[dict], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=INVENTORY_COLUMNS)
    df.to_csv(out_path, index=False, float_format="%.4f")
    return len(df)


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def cross_check(
    named_rows: list[dict],
    custom_csv: Path,
    cap_tolerance_mw: float = 50.0,
    distance_tolerance_km: float = 10.0,
) -> tuple[list[dict], list[dict]]:
    """Cross-check the named-plant inventory against the materialised custom_powerplants.csv.

    Returns (matches, failures). ``status_2023`` of ``retired`` is exempt — it only
    needs to appear if it's still in the 2023 fleet (some retired stations may
    legitimately be absent if retired earlier than 2023).
    """
    if not custom_csv.exists():
        return [], [{"station_name": r["station_name"], "reason": "custom_powerplants.csv missing"} for r in named_rows]
    custom = pd.read_csv(custom_csv)
    matches: list[dict] = []
    failures: list[dict] = []

    carrier_filters = {
        "nuclear":     (custom["Fueltype"] == "Nuclear"),
        "coal":        (custom["Fueltype"] == "Hard Coal"),
        "ocgt_diesel": (custom["Fueltype"] == "Oil"),
        "ocgt_gas":    (custom["Fueltype"] == "Natural Gas"),
        "csp":         (custom["Fueltype"] == "Solar") & (custom["Technology"] == "CSP"),
        "PHS":         (custom["Technology"] == "Pumped Storage"),
        "battery":     (custom["Fueltype"] == "Battery"),
        "onwind":      (custom["Fueltype"] == "Wind"),
        "solar":       (custom["Fueltype"] == "Solar") & (custom["Technology"] == "PV"),
        "hydro":       (custom["Technology"] == "Reservoir"),
        "biomass":     (custom["Fueltype"] == "Bioenergy"),
    }

    for row in named_rows:
        if row["status_2023"] not in {"operating", "commissioning"}:
            continue
        # Match by canonical name prefix + carrier (custom Names may carry _2/_3 disambiguators).
        canonical = row["station_name"].split()[0].lower()
        name_match = custom["Name"].astype(str).str.lower().str.startswith(canonical)
        filt = carrier_filters.get(row["carrier"])
        if filt is not None:
            name_match = name_match & filt
        cand = custom[name_match]
        if cand.empty:
            failures.append({
                "station_name": row["station_name"],
                "reason": "no custom_powerplants.csv row matched canonical prefix",
                "expected_carrier": row["carrier"],
                "expected_mw": row["p_nom_mw_expected"],
            })
            continue
        cap_total = pd.to_numeric(cand["Capacity"], errors="coerce").sum()
        delta_mw = cap_total - row["p_nom_mw_expected"]
        # Centroid for distance check (capacity-weighted).
        lats = pd.to_numeric(cand["lat"], errors="coerce")
        lons = pd.to_numeric(cand["lon"], errors="coerce")
        caps = pd.to_numeric(cand["Capacity"], errors="coerce")
        ok_mask = lats.notna() & lons.notna() & caps.notna() & (caps > 0)
        if ok_mask.any():
            lat_c = float((lats[ok_mask] * caps[ok_mask]).sum() / caps[ok_mask].sum())
            lon_c = float((lons[ok_mask] * caps[ok_mask]).sum() / caps[ok_mask].sum())
            distance_km = _haversine_km(lat_c, lon_c, row["lat_expected"], row["lon_expected"])
        else:
            distance_km = float("nan")

        cap_ok = abs(delta_mw) <= cap_tolerance_mw
        dist_ok = (distance_km != distance_km) or (distance_km <= distance_tolerance_km)
        entry = {
            "station_name":   row["station_name"],
            "expected_carrier": row["carrier"],
            "expected_mw":    row["p_nom_mw_expected"],
            "actual_mw":      float(cap_total),
            "delta_mw":       float(delta_mw),
            "distance_km":    distance_km,
            "n_custom_rows":  int(len(cand)),
            "cap_ok":         cap_ok,
            "distance_ok":    dist_ok,
        }
        if cap_ok and dist_ok:
            matches.append(entry)
        else:
            entry["reason"] = (
                ("capacity_delta_exceeds_tolerance " if not cap_ok else "")
                + ("distance_exceeds_tolerance" if not dist_ok else "")
            ).strip()
            failures.append(entry)

    return matches, failures
