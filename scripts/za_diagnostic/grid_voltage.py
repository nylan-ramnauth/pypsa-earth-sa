# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Comparison 2 — per-voltage RSA breakdown of the GeoJSON line set.

Fills the NaN cells in `za_grid_reconciliation.csv` for the four standard
voltage buckets {220, 275, 400, 765} kV. Adds delta + coverage columns.

The RSA GeoJSON also contains lines at 110, 132 and 533 kV; those features
are reported in an `other` bucket appended to the table for traceability but
do not participate in the standard 220kV+ comparison.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from za_fleet.named_inventory import _haversine_km

logger = logging.getLogger("za_diagnostic.grid_voltage")

STANDARD_BUCKETS_KV = (220, 275, 400, 765)
OTHER_BUCKET_LABEL = "other_kv"


def _linestring_length_km(coords: list) -> float:
    total = 0.0
    for (a, b) in zip(coords[:-1], coords[1:]):
        lat1, lon1 = a[1], a[0]
        lat2, lon2 = b[1], b[0]
        total += _haversine_km(lat1, lon1, lat2, lon2)
    return total


def _feature_length_km(feature: dict) -> float:
    geom = feature.get("geometry") or {}
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if gtype == "LineString":
        return _linestring_length_km(coords)
    if gtype == "MultiLineString":
        return sum(_linestring_length_km(part) for part in coords)
    return 0.0


def _summarize_features(features: list[dict]) -> dict[str, dict]:
    """Return {bucket_label: {count, length_km, mean_length_km}}."""
    buckets: dict[str, list[float]] = {f"{v}kV": [] for v in STANDARD_BUCKETS_KV}
    buckets[OTHER_BUCKET_LABEL] = []

    for f in features:
        v = f.get("properties", {}).get("NOMINAL_VO")
        try:
            v_int = int(round(float(v)))
        except (TypeError, ValueError):
            v_int = -1
        label = f"{v_int}kV" if v_int in STANDARD_BUCKETS_KV else OTHER_BUCKET_LABEL
        buckets[label].append(_feature_length_km(f))

    out: dict[str, dict] = {}
    for label, lengths in buckets.items():
        n = len(lengths)
        total = float(sum(lengths))
        out[label] = {
            "count": n,
            "length_km": round(total, 4),
            "mean_length_km": round(total / n, 4) if n else 0.0,
        }
    return out


def run_grid_voltage(
    existing_lines_geojson: Path,
    grid_reconciliation_csv: Path,
) -> Path:
    """Fill RSA per-voltage cells in `za_grid_reconciliation.csv` in-place.

    Returns the path to the updated CSV.
    """
    logger.info("Loading RSA existing lines: %s", existing_lines_geojson)
    with open(existing_lines_geojson, "r", encoding="utf-8") as fh:
        fc = json.load(fh)
    features = fc.get("features", [])
    logger.info("Loaded %d features", len(features))

    summary = _summarize_features(features)
    logger.info("Per-voltage summary: %s", {k: v["count"] for k, v in summary.items()})

    df = pd.read_csv(grid_reconciliation_csv)
    # Map existing voltage_bucket labels to our bucket keys
    label_map = {f"{v}kV": f"{v}kV" for v in STANDARD_BUCKETS_KV}

    # Ensure new columns exist
    for col in ("rsa_mean_length_km", "delta_line_count", "delta_length_km",
                "osm_coverage_ratio"):
        if col not in df.columns:
            df[col] = pd.NA

    # Fill standard buckets
    for v in STANDARD_BUCKETS_KV:
        key = f"{v}kV"
        if key not in df["voltage_bucket"].values:
            continue
        idx = df.index[df["voltage_bucket"] == key][0]
        s = summary[key]
        df.at[idx, "rsa_line_count"] = s["count"]
        df.at[idx, "rsa_length_km"] = s["length_km"]
        df.at[idx, "rsa_mean_length_km"] = s["mean_length_km"]

        osm_lines = df.at[idx, "osm_line_count"]
        osm_len = df.at[idx, "osm_length_km"]
        if pd.notna(osm_lines) and pd.notna(s["count"]):
            df.at[idx, "delta_line_count"] = int(osm_lines) - int(s["count"])
        if pd.notna(osm_len) and s["length_km"]:
            df.at[idx, "delta_length_km"] = round(float(osm_len) - s["length_km"], 4)
            df.at[idx, "osm_coverage_ratio"] = round(float(osm_len) / s["length_km"], 4)

    # Append "other" RSA bucket if not present (informational)
    if OTHER_BUCKET_LABEL not in df["voltage_bucket"].values:
        other = summary[OTHER_BUCKET_LABEL]
        df = pd.concat(
            [df, pd.DataFrame([{
                "voltage_bucket": OTHER_BUCKET_LABEL,
                "osm_line_count": pd.NA,
                "osm_length_km": pd.NA,
                "rsa_line_count": other["count"],
                "rsa_length_km": other["length_km"],
                "rsa_mean_length_km": other["mean_length_km"],
            }])],
            ignore_index=True,
        )

    # Cross-check the aggregate row
    agg_row = df[df["voltage_bucket"] == "rsa_220kv_plus_aggregate"]
    bucket_sum = sum(summary[f"{v}kV"]["length_km"] for v in STANDARD_BUCKETS_KV)
    if not agg_row.empty:
        agg_len = float(agg_row.iloc[0]["rsa_length_km"])
        ratio = bucket_sum / agg_len if agg_len else float("nan")
        logger.info(
            "Cross-check: sum of {220,275,400,765} buckets = %.1f km vs aggregate row %.1f km (ratio %.3f)",
            bucket_sum, agg_len, ratio
        )

    df.to_csv(grid_reconciliation_csv, index=False, float_format="%.4f")
    logger.info("Updated %s in place", grid_reconciliation_csv)
    return grid_reconciliation_csv
