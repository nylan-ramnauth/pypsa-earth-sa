# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Shared plotting helpers for Module 10 diagnostic report + notebook.

All functions return a `matplotlib.Figure`. Save with `fig.savefig(...)`
externally; do not call plt.show() — keep these pure.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logger = logging.getLogger("za_diagnostic.plots")

CARRIER_ORDER = [
    "coal", "nuclear", "ocgt_diesel", "ocgt_gas", "hydro", "ror", "PHS",
    "solar", "onwind", "csp", "battery", "bioenergy", "other",
]
VOLTAGE_ORDER = ["220kV", "275kV", "400kV", "765kV", "other_kv"]


def plot_fleet_capacity_by_carrier(df: pd.DataFrame) -> plt.Figure:
    """Grouped bar: PPM total vs RSA total per carrier."""
    df_plot = df.copy()
    df_plot["carrier"] = df_plot["carrier"].astype(str)
    if "carrier" in df_plot.columns:
        ordered = [c for c in CARRIER_ORDER if c in set(df_plot["carrier"])]
        extras = [c for c in df_plot["carrier"] if c not in CARRIER_ORDER]
        df_plot = df_plot.set_index("carrier").loc[ordered + extras].reset_index()

    fig, ax = plt.subplots(figsize=(11, 5))
    x = np.arange(len(df_plot))
    w = 0.4
    ax.bar(x - w / 2, df_plot["capacity_mw_ppm_total"], w,
           label="PPM (Earth default)", color="#4477AA")
    ax.bar(x + w / 2, df_plot["capacity_mw_rsa_total"], w,
           label="RSA (override)", color="#CC3311")
    for i, d in enumerate(df_plot["delta_mw"]):
        ax.annotate(f"{d:+.0f}",
                    xy=(i, max(df_plot.iloc[i]["capacity_mw_ppm_total"],
                               df_plot.iloc[i]["capacity_mw_rsa_total"])),
                    xytext=(0, 4), textcoords="offset points",
                    ha="center", fontsize=8, color="#333333")
    ax.set_xticks(x, df_plot["carrier"], rotation=30, ha="right")
    ax.set_ylabel("Capacity (MW)")
    ax.set_title("Fleet capacity by carrier — PPM vs RSA")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend()
    fig.tight_layout()
    return fig


def _bucket_plot(df: pd.DataFrame, value_osm: str, value_rsa: str,
                 ylabel: str, title: str) -> plt.Figure:
    df_plot = df[df["voltage_bucket"].isin(VOLTAGE_ORDER)].copy()
    df_plot["voltage_bucket"] = pd.Categorical(
        df_plot["voltage_bucket"], categories=VOLTAGE_ORDER, ordered=True)
    df_plot = df_plot.sort_values("voltage_bucket")

    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(df_plot))
    w = 0.4
    osm_vals = pd.to_numeric(df_plot[value_osm], errors="coerce").fillna(0)
    rsa_vals = pd.to_numeric(df_plot[value_rsa], errors="coerce").fillna(0)
    ax.bar(x - w / 2, osm_vals, w, label="OSM (Earth)", color="#4477AA")
    ax.bar(x + w / 2, rsa_vals, w, label="RSA", color="#CC3311")
    ax.set_xticks(x, df_plot["voltage_bucket"].astype(str))
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend()
    fig.tight_layout()
    return fig


def plot_line_count_per_voltage(df_grid: pd.DataFrame) -> plt.Figure:
    return _bucket_plot(
        df_grid, "osm_line_count", "rsa_line_count",
        "Line count", "Transmission line count per voltage — OSM vs RSA",
    )


def plot_line_length_per_voltage(df_grid: pd.DataFrame) -> plt.Figure:
    return _bucket_plot(
        df_grid, "osm_length_km", "rsa_length_km",
        "Total length (km)", "Transmission line length per voltage — OSM vs RSA",
    )


def plot_substation_count_per_voltage(df_subs: pd.DataFrame) -> plt.Figure:
    return _bucket_plot(
        df_subs, "osm_substation_count", "rsa_substation_count",
        "Substation count", "Substation count per voltage — OSM vs RSA (derived)",
    )


def plot_substation_map(
    rsa_lines_geojson: Path,
    rsa_subs_df: pd.DataFrame,
    osm_subs_geojson: Path,
    out_dir_for_basemap: Path | None = None,
) -> plt.Figure:
    """Geographic map: RSA lines (grey), OSM 220kV+ subs (blue), RSA derived (red)."""
    fig, ax = plt.subplots(figsize=(9, 9))

    # RSA lines as grey traces
    with open(rsa_lines_geojson, "r", encoding="utf-8") as fh:
        fc = json.load(fh)
    for f in fc["features"]:
        geom = f["geometry"]
        if geom["type"] == "LineString":
            xs = [c[0] for c in geom["coordinates"]]
            ys = [c[1] for c in geom["coordinates"]]
            ax.plot(xs, ys, color="#BBBBBB", linewidth=0.6, alpha=0.7)

    # OSM 220kV+ substations as blue dots
    with open(osm_subs_geojson, "r", encoding="utf-8") as fh:
        fc_subs = json.load(fh)
    osm_xs, osm_ys = [], []
    for f in fc_subs["features"]:
        props = f.get("properties", {})
        if props.get("country") != "ZA":
            continue
        v = props.get("voltage")
        try:
            v_kv = max(float(p) for p in str(v).replace(";", ",").split(",")
                       if p.strip()) / 1000.0
        except Exception:
            continue
        if v_kv < 220:
            continue
        osm_xs.append(props.get("lon"))
        osm_ys.append(props.get("lat"))
    ax.scatter(osm_xs, osm_ys, s=12, c="#4477AA", alpha=0.6,
               label=f"OSM substations ≥220 kV (n={len(osm_xs)})")

    # RSA derived substations: take a point per name from a representative line.
    # We don't have substation coords directly; use line endpoint as approximation.
    rsa_point_xs, rsa_point_ys = [], []
    seen = set()
    for f in fc["features"]:
        props = f.get("properties", {})
        for endpoint, idx in (("LINE_START", 0), ("LINE_END", -1)):
            name = (props.get(endpoint) or "").strip().upper()
            if not name or name in seen:
                continue
            seen.add(name)
            coords = f["geometry"]["coordinates"]
            pt = coords[idx]
            rsa_point_xs.append(pt[0])
            rsa_point_ys.append(pt[1])
    ax.scatter(rsa_point_xs, rsa_point_ys, s=22, marker="^", c="#CC3311",
               alpha=0.8, label=f"RSA substations (derived, n={len(rsa_point_xs)})")

    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Substation coverage — Earth OSM vs PyPSA-RSA (220 kV+)")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(linestyle="--", alpha=0.3)
    ax.legend(loc="lower right")
    fig.tight_layout()
    return fig


def plot_network_map(
    elec_s_34_nc: Path,
    rsa_lines_geojson: Path,
    supply_regions_geojson: Path | None = None,
) -> plt.Figure:
    import pypsa
    n = pypsa.Network(str(elec_s_34_nc))
    fig, ax = plt.subplots(figsize=(10, 10))

    # 34 Eskom supply-area polygons (drawn first, behind everything)
    if supply_regions_geojson is not None:
        with open(supply_regions_geojson, "r", encoding="utf-8") as fh:
            fc_regions = json.load(fh)
        for f in fc_regions["features"]:
            geom = f["geometry"]
            name = f["properties"].get("name", "")
            cx = f["properties"].get("x")
            cy = f["properties"].get("y")
            rings = []
            if geom["type"] == "Polygon":
                rings = [geom["coordinates"][0]]
            elif geom["type"] == "MultiPolygon":
                rings = [poly[0] for poly in geom["coordinates"]]
            for ring in rings:
                xs = [c[0] for c in ring]
                ys = [c[1] for c in ring]
                ax.fill(xs, ys, alpha=0.06, color="#AAAAAA")
                ax.plot(xs, ys, color="#888888", linewidth=0.8, alpha=0.6)
            if cx is not None and cy is not None:
                ax.text(cx, cy, name, fontsize=5.5, ha="center", va="center",
                        color="#444444", zorder=4)

    # RSA lines as red traces
    with open(rsa_lines_geojson, "r", encoding="utf-8") as fh:
        fc = json.load(fh)
    for f in fc["features"]:
        geom = f["geometry"]
        if geom["type"] == "LineString":
            xs = [c[0] for c in geom["coordinates"]]
            ys = [c[1] for c in geom["coordinates"]]
            ax.plot(xs, ys, color="#CC3311", linewidth=0.6, alpha=0.5)

    # PyPSA elec_s_34 lines as blue traces
    for _, ln in n.lines.iterrows():
        b0 = n.buses.loc[ln["bus0"]]
        b1 = n.buses.loc[ln["bus1"]]
        ax.plot([b0["x"], b1["x"]], [b0["y"], b1["y"]],
                color="#4477AA", linewidth=1.2, alpha=0.8)

    # Buses
    ax.scatter(n.buses["x"], n.buses["y"], s=35, c="#222277", zorder=5,
               label=f"PyPSA-Earth elec_s_34 buses (n={len(n.buses)})")

    if supply_regions_geojson is not None:
        ax.plot([], [], color="#888888", label="34 Eskom supply areas")
    ax.plot([], [], color="#CC3311", label=f"PyPSA-RSA lines (n=324)")
    ax.plot([], [], color="#4477AA", label=f"PyPSA-Earth elec_s_34 lines (n={len(n.lines)})")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Network overlay — PyPSA-Earth clustered vs PyPSA-RSA reference")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(linestyle="--", alpha=0.3)
    ax.legend(loc="lower right")
    fig.tight_layout()
    return fig


def plot_ratings_ratio_distribution(df_ratings: pd.DataFrame) -> plt.Figure:
    df = df_ratings[df_ratings["bus0"] != "_summary_"].copy()
    df = df[df["ratio_osm_to_stclair"].notna()]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.hist(df["ratio_osm_to_stclair"], bins=30, color="#4477AA", alpha=0.8,
            edgecolor="white")
    ax.axvline(0.8, color="#CC3311", linestyle="--", label="under-rated < 0.8")
    ax.axvline(1.2, color="#CC3311", linestyle="--", label="over-rated > 1.2")
    ax.set_xlabel("OSM s_nom / St Clair N-1 ratio")
    ax.set_ylabel("Number of corridors")
    ax.set_title("Per-corridor line-rating ratio distribution")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend()
    fig.tight_layout()
    return fig


def plot_ratings_scatter(df_ratings: pd.DataFrame) -> plt.Figure:
    df = df_ratings[df_ratings["bus0"] != "_summary_"].copy()
    df = df.dropna(subset=["osm_s_nom_total_mw", "st_clair_n1_mw"])
    fig, ax = plt.subplots(figsize=(7, 7))
    colors = df["direction"].map({
        "osm_over": "#CC3311",
        "osm_under": "#EE9966",
        "within_20pct": "#4477AA",
        "unmatched": "#888888",
    })
    ax.scatter(df["st_clair_n1_mw"], df["osm_s_nom_total_mw"],
               c=colors, alpha=0.7, s=40)
    mx = max(df["st_clair_n1_mw"].max(), df["osm_s_nom_total_mw"].max()) * 1.05
    ax.plot([0, mx], [0, mx], color="black", linestyle="-", linewidth=0.7,
            label="y = x")
    ax.plot([0, mx], [0, 1.2 * mx], color="#CC3311", linestyle="--",
            linewidth=0.7, label="±20%")
    ax.plot([0, mx], [0, 0.8 * mx], color="#CC3311", linestyle="--",
            linewidth=0.7)
    ax.set_xlim(0, mx)
    ax.set_ylim(0, mx)
    ax.set_xlabel("St Clair N-1 (MW)")
    ax.set_ylabel("OSM s_nom total (MW)")
    ax.set_title("OSM thermal rating vs St Clair N-1 per corridor")
    ax.grid(linestyle="--", alpha=0.4)
    ax.legend()
    fig.tight_layout()
    return fig
