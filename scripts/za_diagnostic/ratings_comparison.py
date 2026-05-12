# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Comparison 4 — OSM s_nom vs St Clair N-1 per corridor.

Loads the clustered network (`elec_s_34.nc`) and sums `n.lines.s_nom` per
(bus0, bus1) corridor in `za_rsa_interregional_transfer_limits.csv`.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger("za_diagnostic.ratings_comparison")

OUT_RATINGS = "za_osm_vs_stclair_ratings_comparison.csv"


def _match_corridor(lines: pd.DataFrame, bus0: str, bus1: str) -> pd.DataFrame:
    mask_fwd = (lines["bus0"] == bus0) & (lines["bus1"] == bus1)
    mask_rev = (lines["bus0"] == bus1) & (lines["bus1"] == bus0)
    return lines[mask_fwd | mask_rev]


def _direction(ratio: float | None) -> str:
    if ratio is None or pd.isna(ratio):
        return "unmatched"
    if ratio > 1.2:
        return "osm_over"
    if ratio < 0.8:
        return "osm_under"
    return "within_20pct"


def run_ratings_comparison(
    transfer_limits_csv: Path,
    elec_s_34_nc: Path,
    audit_dir: Path,
) -> Path:
    audit_dir.mkdir(parents=True, exist_ok=True)
    try:
        import pypsa
    except ImportError as e:
        raise SystemExit("pypsa not installed in current env") from e

    logger.info("Loading PyPSA network: %s", elec_s_34_nc)
    n = pypsa.Network(str(elec_s_34_nc))
    lines = n.lines.reset_index()  # adds 'name' column
    logger.info("Network has %d lines, %d buses (post-cluster)",
                len(lines), len(n.buses))

    corridors = pd.read_csv(transfer_limits_csv)
    logger.info("Loaded %d corridors from %s", len(corridors), transfer_limits_csv)

    rows = []
    for _, c in corridors.iterrows():
        bus0, bus1 = c["bus0"], c["bus1"]
        matched = _match_corridor(lines, bus0, bus1)
        if matched.empty:
            rows.append({
                "bus0": bus0, "bus1": bus1,
                "n_lines": int(c.get("n_lines", 0)),
                "voltage_max_kv": int(c.get("voltage_max_kv", 0)),
                "osm_s_nom_total_mw": np.nan,
                "n_osm_lines": 0,
                "st_clair_n1_mw": float(c.get("st_clair_n1_mw", float("nan"))),
                "ratio_osm_to_stclair": np.nan,
                "direction": "unmatched",
                "notes": "no_osm_lines_found",
            })
            continue
        osm_s_nom_total = float(matched["s_nom"].sum())
        stclair_n1 = float(c.get("st_clair_n1_mw", float("nan")))
        ratio = osm_s_nom_total / stclair_n1 if stclair_n1 else None
        rows.append({
            "bus0": bus0, "bus1": bus1,
            "n_lines": int(c.get("n_lines", 0)),
            "voltage_max_kv": int(c.get("voltage_max_kv", 0)),
            "osm_s_nom_total_mw": round(osm_s_nom_total, 2),
            "n_osm_lines": int(len(matched)),
            "st_clair_n1_mw": round(stclair_n1, 2) if not pd.isna(stclair_n1) else stclair_n1,
            "ratio_osm_to_stclair": round(ratio, 4) if ratio is not None else None,
            "direction": _direction(ratio),
            "notes": "",
        })

    df = pd.DataFrame(rows)

    # Summary footer rows
    matched_df = df[df["direction"] != "unmatched"]
    summary_rows = []
    for label in ("osm_over", "within_20pct", "osm_under", "unmatched"):
        sub = df[df["direction"] == label]
        summary_rows.append({
            "bus0": "_summary_",
            "bus1": label,
            "n_lines": int(sub["n_lines"].sum()),
            "voltage_max_kv": 0,
            "osm_s_nom_total_mw": round(float(sub["osm_s_nom_total_mw"].fillna(0).sum()), 2),
            "n_osm_lines": int(sub["n_osm_lines"].sum()),
            "st_clair_n1_mw": round(float(sub["st_clair_n1_mw"].fillna(0).sum()), 2),
            "ratio_osm_to_stclair": None,
            "direction": label,
            "notes": f"n_corridors={len(sub)}",
        })

    out_df = pd.concat([df, pd.DataFrame(summary_rows)], ignore_index=True)
    out_path = audit_dir / OUT_RATINGS
    out_df.to_csv(out_path, index=False, float_format="%.4f")
    logger.info(
        "Wrote %s — over=%d, under=%d, within=%d, unmatched=%d",
        out_path,
        int((df["direction"] == "osm_over").sum()),
        int((df["direction"] == "osm_under").sum()),
        int((df["direction"] == "within_20pct").sum()),
        int((df["direction"] == "unmatched").sum()),
    )
    return out_path
