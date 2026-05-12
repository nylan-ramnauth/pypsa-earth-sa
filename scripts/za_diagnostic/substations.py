# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Comparison 3 — Substations (Earth OSM vs RSA derived from line endpoints).

PyPSA-RSA has no dedicated substations file. We derive an RSA substation set
from the unique union of `LINE_START` and `LINE_END` properties of the
220kV+ existing-lines GeoJSON. PyPSA-Earth's substations come from
`resources/{run}/osm/clean/all_clean_substations.geojson`, filtered to
220kV+ by the `voltage` property (stored in volts, e.g. 275000).
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import pandas as pd

logger = logging.getLogger("za_diagnostic.substations")

STANDARD_BUCKETS_KV = (220, 275, 400, 765)
OUT_SUBS_COMPARISON = "za_substations_comparison.csv"
OUT_RSA_SUBS_DERIVED = "za_rsa_substations_derived.csv"


def _norm_name(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", str(s).strip().upper())


def _parse_voltage_volts(v) -> int:
    """Parse OSM voltage tag, return max voltage in kV (rounded)."""
    if v is None:
        return -1
    try:
        if isinstance(v, (int, float)):
            return int(round(float(v) / 1000.0))
        s = str(v).strip()
        if not s:
            return -1
        # Multi-valued OSM tag: "220000;400000" -> take max
        parts = re.split(r"[;,/]", s)
        vals = []
        for p in parts:
            p = p.strip()
            if not p:
                continue
            try:
                vals.append(float(p))
            except ValueError:
                continue
        if not vals:
            return -1
        return int(round(max(vals) / 1000.0))
    except Exception:
        return -1


def _bucket_label(v_kv: int) -> str:
    if v_kv in STANDARD_BUCKETS_KV:
        return f"{v_kv}kV"
    return "other_kv"


def _load_rsa_substations(existing_lines_geojson: Path) -> pd.DataFrame:
    """Derive the RSA substation set from line endpoints.

    Returns DataFrame with: substation_name, n_incident_lines, voltage_max_kv,
    voltages_kv (comma-separated).
    """
    with open(existing_lines_geojson, "r", encoding="utf-8") as fh:
        fc = json.load(fh)

    by_name: dict[str, dict] = {}
    for f in fc.get("features", []):
        props = f.get("properties", {})
        v = props.get("NOMINAL_VO")
        try:
            v_kv = int(round(float(v)))
        except (TypeError, ValueError):
            v_kv = -1
        for endpoint in ("LINE_START", "LINE_END"):
            name = _norm_name(props.get(endpoint))
            if not name:
                continue
            entry = by_name.setdefault(name, {
                "substation_name": name,
                "n_incident_lines": 0,
                "voltage_max_kv": 0,
                "_voltages": set(),
            })
            entry["n_incident_lines"] += 1
            if v_kv > 0:
                entry["_voltages"].add(v_kv)
                entry["voltage_max_kv"] = max(entry["voltage_max_kv"], v_kv)

    rows = []
    for entry in by_name.values():
        rows.append({
            "substation_name": entry["substation_name"],
            "n_incident_lines": entry["n_incident_lines"],
            "voltage_max_kv": entry["voltage_max_kv"],
            "voltages_kv": ",".join(str(v) for v in sorted(entry["_voltages"])),
        })
    df = pd.DataFrame(rows).sort_values(
        ["voltage_max_kv", "n_incident_lines"], ascending=[False, False]
    ).reset_index(drop=True)
    return df


def _load_osm_substations(clean_substations_geojson: Path) -> pd.DataFrame:
    with open(clean_substations_geojson, "r", encoding="utf-8") as fh:
        fc = json.load(fh)
    rows = []
    for f in fc.get("features", []):
        props = f.get("properties", {})
        v_kv = _parse_voltage_volts(props.get("voltage"))
        if v_kv <= 0:
            continue
        rows.append({
            "bus_id": props.get("bus_id"),
            "voltage_kv": v_kv,
            "lat": props.get("lat"),
            "lon": props.get("lon"),
            "country": props.get("country"),
            "tag_substation": props.get("tag_substation"),
        })
    df = pd.DataFrame(rows)
    if "country" in df.columns:
        df = df[df["country"] == "ZA"]
    return df.reset_index(drop=True)


def _bucket_counts(osm_subs: pd.DataFrame, rsa_subs: pd.DataFrame) -> pd.DataFrame:
    """Aggregate substation counts by voltage bucket. RSA: voltage_max_kv.
    OSM: any substation that carries that voltage (so 400 kV substation with a
    400/275 tap counts in both 400 and 275). For simplicity we use the max
    voltage of the OSM substation (consistent with RSA derivation)."""

    def bucket_for_osm(v_kv: int) -> str:
        return _bucket_label(v_kv)

    osm_buckets = osm_subs["voltage_kv"].apply(bucket_for_osm).value_counts().to_dict()

    def bucket_for_rsa(v_kv: int) -> str:
        return _bucket_label(int(v_kv))

    rsa_buckets = rsa_subs["voltage_max_kv"].apply(bucket_for_rsa).value_counts().to_dict()

    bucket_order = [f"{v}kV" for v in STANDARD_BUCKETS_KV] + ["other_kv"]
    rows = []
    for b in bucket_order:
        osm_n = int(osm_buckets.get(b, 0))
        rsa_n = int(rsa_buckets.get(b, 0))
        delta = osm_n - rsa_n
        ratio = round(osm_n / rsa_n, 3) if rsa_n else None
        rows.append({
            "voltage_bucket": b,
            "osm_substation_count": osm_n,
            "rsa_substation_count": rsa_n,
            "delta_count": delta,
            "osm_coverage_ratio": ratio,
            "notes": "",
        })

    # Aggregate row (220kV+)
    keep = lambda b: b in ("220kV", "275kV", "400kV", "765kV")
    osm_total = sum(int(osm_buckets.get(b, 0)) for b in bucket_order if keep(b))
    rsa_total = sum(int(rsa_buckets.get(b, 0)) for b in bucket_order if keep(b))
    rows.append({
        "voltage_bucket": "220kv_plus_total",
        "osm_substation_count": osm_total,
        "rsa_substation_count": rsa_total,
        "delta_count": osm_total - rsa_total,
        "osm_coverage_ratio": round(osm_total / rsa_total, 3) if rsa_total else None,
        "notes": "sum of 220/275/400/765 buckets",
    })
    return pd.DataFrame(rows)


def run_substations(
    existing_lines_geojson: Path,
    clean_substations_geojson: Path,
    audit_dir: Path,
) -> dict[str, Path]:
    audit_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Deriving RSA substations from line endpoints: %s", existing_lines_geojson)
    rsa_subs = _load_rsa_substations(existing_lines_geojson)
    logger.info("RSA derived substations: %d unique", len(rsa_subs))

    logger.info("Loading OSM clean substations (ZA): %s", clean_substations_geojson)
    osm_subs = _load_osm_substations(clean_substations_geojson)
    logger.info("OSM substations with voltage tag (ZA): %d", len(osm_subs))

    comparison_df = _bucket_counts(osm_subs, rsa_subs)
    out_compare = audit_dir / OUT_SUBS_COMPARISON
    comparison_df.to_csv(out_compare, index=False, float_format="%.4f")
    logger.info("Wrote %s", out_compare)

    out_rsa_derived = audit_dir / OUT_RSA_SUBS_DERIVED
    rsa_subs.to_csv(out_rsa_derived, index=False)
    logger.info("Wrote %s (%d substations)", out_rsa_derived, len(rsa_subs))

    return {
        "substations_comparison": out_compare,
        "rsa_substations_derived": out_rsa_derived,
        "n_rsa": int(len(rsa_subs)),
        "n_osm_220plus": int((osm_subs["voltage_kv"] >= 220).sum()) if len(osm_subs) else 0,
    }
