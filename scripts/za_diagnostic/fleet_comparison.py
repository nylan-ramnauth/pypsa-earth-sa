# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Comparison 1 — PPM vs RSA powerplant fleet.

Queries `powerplantmatching` live for ZA, fuzzy-matches against the
RSA reconciliation table, back-fills `capacity_mw_ppm` / `source_ppm`,
and emits per-carrier aggregate + appendix CSVs.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from za_fleet.named_inventory import _haversine_km

logger = logging.getLogger("za_diagnostic.fleet_comparison")

PPM_CARRIER_MAP = {
    # PPM Fueltype -> ZA carrier (broad)
    "Hard Coal":   "coal",
    "Lignite":     "coal",
    "Nuclear":     "nuclear",
    "Oil":         "ocgt_diesel",
    "Natural Gas": "ocgt_gas",
    "Hydro":       "hydro",
    "Solar":       "solar",
    "Wind":        "onwind",
    "Bioenergy":   "bioenergy",
    "Battery":     "battery",
    "Other":       "other",
    "Waste":       "bioenergy",
    "Geothermal":  "other",
}
# PPM Technology refines a few carriers
PPM_TECH_OVERRIDE = {
    "Run-Of-River":   "ror",
    "Pumped Storage": "PHS",
    "CCGT":           "ocgt_gas",
    "OCGT":           "ocgt_gas",
    "Steam Turbine":  None,  # carrier determined by fuel
    "CSP":            "csp",
    "PV":             "solar",
    "Onshore":        "onwind",
    "Offshore":       "offwind",
}

OUT_FLEET_COMPARISON = "za_ppm_vs_rsa_fleet_comparison.csv"
OUT_PPM_ONLY = "za_ppm_plants_not_in_rsa.csv"
OUT_RSA_ONLY = "za_rsa_plants_not_in_ppm.csv"

DISTANCE_TOLERANCE_KM = 20.0
CAPACITY_TOLERANCE_FRAC = 0.30


def _ppm_country_subset(pm_config_path: Path) -> pd.DataFrame:
    """Live powerplantmatching query for ZA.

    Uses PyPSA-Earth's PPM config and forces `target_countries=["South Africa"]`
    + `update=True` so PPM rebuilds the matched DB from the external sources
    declared in the config (GEM/GPD/etc.). The default cached PPM DB is
    Europe-only and contains zero ZA rows.
    """
    try:
        import powerplantmatching as pm
    except ImportError as e:
        raise SystemExit(
            "powerplantmatching not installed in current env. "
            "Run from the pypsa-earth conda env (which pins powerplantmatching>=0.8)."
        ) from e

    import yaml
    with open(pm_config_path, "r", encoding="utf-8") as fh:
        pm_cfg = yaml.safe_load(fh)

    pm_cfg["target_countries"] = ["South Africa"]
    pm_cfg["main_query"] = ""
    # Drop EXTERNAL_DATABASE from sources if present (it's the OSM2PM bridge
    # used by build_powerplants and is not relevant here).
    for k in ("matching_sources", "fully_included_sources"):
        if k in pm_cfg and pm_cfg[k]:
            pm_cfg[k] = [s for s in pm_cfg[k] if s != "EXTERNAL_DATABASE"]

    try:
        ppl = pm.powerplants(from_url=False, update=True, config_update=pm_cfg)
    except Exception as e:
        raise SystemExit(
            f"powerplantmatching query failed: {e}. "
            "Check network connectivity (PPM scrapes GEM/GPD/etc. when update=True)."
        ) from e

    # PPM returns full country names; filter then convert to alpha2 for parity
    # with the RSA reconciliation CSV.
    za = ppl[ppl["Country"] == "South Africa"].copy()
    try:
        za = za.powerplant.convert_country_to_alpha2()
    except Exception:
        za["Country"] = "ZA"
    logger.info("PPM live query returned %d ZA rows", len(za))
    return za


def _normalize_carrier(fueltype, technology) -> str:
    # Handle NaN / pd.NA / None robustly
    if pd.notna(technology):
        tech = str(technology)
        if tech in PPM_TECH_OVERRIDE and PPM_TECH_OVERRIDE[tech] is not None:
            return PPM_TECH_OVERRIDE[tech]
    if pd.notna(fueltype):
        return PPM_CARRIER_MAP.get(str(fueltype), "other")
    return "other"


def _attach_normalized_carrier(za_ppm: pd.DataFrame) -> pd.DataFrame:
    df = za_ppm.copy()
    fueltypes = df.get("Fueltype", pd.Series([""] * len(df))).fillna("Other")
    techs = df.get("Technology", pd.Series([None] * len(df)))
    df["carrier_ppm"] = [_normalize_carrier(f, t) for f, t in zip(fueltypes, techs)]
    return df


def _match_rsa_to_ppm(rsa: pd.DataFrame, za_ppm: pd.DataFrame) -> pd.DataFrame:
    """For each RSA row, find best PPM match (carrier + distance + capacity).

    Returns RSA-shaped frame with added `_match_ppm_idx`, `_match_ppm_cap`, `_match_distance_km`.
    `_match_ppm_idx == -1` means unmatched.
    """
    matched_idx = np.full(len(rsa), -1, dtype=int)
    matched_cap = np.full(len(rsa), np.nan)
    matched_dist = np.full(len(rsa), np.nan)
    ppm_used = set()

    rsa_arr = rsa.reset_index(drop=True)
    ppm_arr = za_ppm.reset_index(drop=True)

    for i, row in rsa_arr.iterrows():
        car = row["carrier"]
        rsa_cap = float(row.get("capacity_mw_final") or 0.0)
        rsa_lat, rsa_lon = row.get("lat_final"), row.get("lon_final")
        if pd.isna(rsa_lat) or pd.isna(rsa_lon) or rsa_cap <= 0:
            continue
        cap_tol = max(rsa_cap * CAPACITY_TOLERANCE_FRAC, 5.0)
        best_idx, best_dist = -1, float("inf")
        for j, pp in ppm_arr.iterrows():
            if j in ppm_used:
                continue
            if pp["carrier_ppm"] != car:
                continue
            ppm_cap = pp.get("Capacity")
            ppm_lat = pp.get("lat")
            ppm_lon = pp.get("lon")
            if pd.isna(ppm_cap) or pd.isna(ppm_lat) or pd.isna(ppm_lon):
                continue
            if abs(float(ppm_cap) - rsa_cap) > cap_tol:
                continue
            d = _haversine_km(rsa_lat, rsa_lon, float(ppm_lat), float(ppm_lon))
            if d <= DISTANCE_TOLERANCE_KM and d < best_dist:
                best_idx, best_dist = j, d
        if best_idx >= 0:
            matched_idx[i] = best_idx
            matched_cap[i] = float(ppm_arr.iloc[best_idx]["Capacity"])
            matched_dist[i] = best_dist
            ppm_used.add(best_idx)

    rsa_out = rsa_arr.copy()
    rsa_out["_match_ppm_idx"] = matched_idx
    rsa_out["_match_ppm_cap"] = matched_cap
    rsa_out["_match_distance_km"] = matched_dist
    return rsa_out


def _aggregate_by_carrier(rsa_matched: pd.DataFrame, za_ppm: pd.DataFrame) -> pd.DataFrame:
    carriers = sorted(set(rsa_matched["carrier"].dropna()) | set(za_ppm["carrier_ppm"]))
    rows = []
    matched_ppm_idxs = set(int(i) for i in rsa_matched["_match_ppm_idx"] if i >= 0)

    for car in carriers:
        rsa_sub = rsa_matched[rsa_matched["carrier"] == car]
        ppm_sub = za_ppm[za_ppm["carrier_ppm"] == car]

        rsa_cap_total = float(rsa_sub["capacity_mw_final"].fillna(0).sum())
        ppm_cap_total = float(ppm_sub["Capacity"].fillna(0).sum())

        n_matched_rsa = int((rsa_sub["_match_ppm_idx"] >= 0).sum())
        n_rsa_only = int(len(rsa_sub) - n_matched_rsa)
        n_ppm_only = int(
            sum(1 for i in ppm_sub.index if i not in matched_ppm_idxs)
        )

        notes = []
        delta = ppm_cap_total - rsa_cap_total
        if abs(delta) > 500:
            notes.append(f"delta>500MW: {delta:+.0f}")
        rows.append({
            "carrier": car,
            "capacity_mw_ppm_total": round(ppm_cap_total, 2),
            "capacity_mw_rsa_total": round(rsa_cap_total, 2),
            "delta_mw": round(delta, 2),
            "n_plants_ppm_only": n_ppm_only,
            "n_plants_rsa_only": n_rsa_only,
            "n_plants_matched": n_matched_rsa,
            "notes": "; ".join(notes),
        })
    return pd.DataFrame(rows)


def run_fleet_comparison(
    reconciliation_csv: Path,
    audit_dir: Path,
    pm_config_path: Path,
) -> dict[str, Path]:
    """Execute Comparison 1.

    - Live PPM query for ZA
    - Fuzzy-match RSA rows against PPM
    - Back-fill `capacity_mw_ppm` / `source_ppm` in reconciliation_csv in-place
    - Write per-carrier aggregate + two appendix CSVs
    """
    audit_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Loading RSA reconciliation: %s", reconciliation_csv)
    rsa = pd.read_csv(reconciliation_csv)

    za_ppm = _ppm_country_subset(pm_config_path)
    za_ppm = _attach_normalized_carrier(za_ppm)

    logger.info("Fuzzy-matching %d RSA rows against %d PPM rows", len(rsa), len(za_ppm))
    rsa_matched = _match_rsa_to_ppm(rsa, za_ppm)

    # Back-fill reconciliation in-place
    matched_mask = rsa_matched["_match_ppm_idx"] >= 0
    rsa_to_write = rsa.copy()
    rsa_to_write["capacity_mw_ppm"] = np.where(
        matched_mask, rsa_matched["_match_ppm_cap"], rsa_to_write.get("capacity_mw_ppm")
    )

    def _src(i):
        if i < 0:
            return "no_ppm_match"
        pp = za_ppm.iloc[int(i)]
        return f"ppm_live:{pp.get('projectID','?')}"

    rsa_to_write["source_ppm"] = [_src(i) for i in rsa_matched["_match_ppm_idx"]]
    rsa_to_write.to_csv(reconciliation_csv, index=False, float_format="%.4f")
    logger.info("Back-filled %d/%d RSA rows with PPM match",
                int(matched_mask.sum()), len(rsa_to_write))

    # Aggregate per carrier
    fleet_df = _aggregate_by_carrier(rsa_matched, za_ppm)
    out_fleet = audit_dir / OUT_FLEET_COMPARISON
    fleet_df.to_csv(out_fleet, index=False, float_format="%.2f")
    logger.info("Wrote %s (%d carriers)", out_fleet, len(fleet_df))

    # PPM-only appendix
    matched_ppm_idxs = set(int(i) for i in rsa_matched["_match_ppm_idx"] if i >= 0)
    ppm_only = za_ppm[~za_ppm.index.isin(matched_ppm_idxs)].copy()
    ppm_only_cols = [c for c in ("projectID", "Fueltype", "Technology",
                                 "Capacity", "lat", "lon", "DateIn", "carrier_ppm")
                     if c in ppm_only.columns]
    out_ppm_only = audit_dir / OUT_PPM_ONLY
    ppm_only[ppm_only_cols].to_csv(out_ppm_only, index=False, float_format="%.4f")
    logger.info("Wrote %s (%d PPM-only rows)", out_ppm_only, len(ppm_only))

    # RSA-only appendix
    rsa_only = rsa_matched[rsa_matched["_match_ppm_idx"] < 0].copy()
    rsa_only_cols = ["canonical_name", "carrier", "capacity_mw_final",
                     "lat_final", "lon_final", "status_2023", "decision"]
    rsa_only_cols = [c for c in rsa_only_cols if c in rsa_only.columns]
    out_rsa_only = audit_dir / OUT_RSA_ONLY
    rsa_only[rsa_only_cols].to_csv(out_rsa_only, index=False, float_format="%.4f")
    logger.info("Wrote %s (%d RSA-only rows)", out_rsa_only, len(rsa_only))

    return {
        "fleet_comparison": out_fleet,
        "ppm_only": out_ppm_only,
        "rsa_only": out_rsa_only,
        "n_matched": int(matched_mask.sum()),
        "n_rsa_total": int(len(rsa)),
        "n_ppm_total": int(len(za_ppm)),
    }
