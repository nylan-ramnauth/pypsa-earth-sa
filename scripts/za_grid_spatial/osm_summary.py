# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Summarise the PyPSA-Earth OSM grid for ZA from `networks/<run>/base.nc`."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pypsa

VOLTAGE_BUCKETS_KV = [0, 220, 275, 400, 765, 1e6]


def summarise_base_network(base_nc: Path) -> pd.DataFrame:
    n = pypsa.Network(str(base_nc))
    lines = n.lines.copy()
    if "v_nom" not in lines.columns and len(lines) > 0:
        # derive from connected buses if absent
        lines["v_nom"] = lines["bus0"].map(n.buses["v_nom"])

    bucket_labels = ["<220kV", "220kV", "275kV", "400kV", "765kV"]
    if len(lines):
        lines["v_nom_kv"] = lines["v_nom"].astype(float)
        lines["bucket"] = pd.cut(
            lines["v_nom_kv"],
            bins=VOLTAGE_BUCKETS_KV,
            labels=bucket_labels,
            right=False,
            include_lowest=True,
        )
        per_bucket = (
            lines.groupby("bucket", observed=False)
            .agg(line_count=("v_nom_kv", "size"), total_length_km=("length", "sum"))
            .reset_index()
            .rename(columns={"bucket": "voltage_bucket"})
        )
    else:
        per_bucket = pd.DataFrame(
            {"voltage_bucket": bucket_labels, "line_count": 0, "total_length_km": 0.0}
        )

    summary_rows = [
        {"metric": "total_buses", "value": int(len(n.buses))},
        {"metric": "total_lines", "value": int(len(n.lines))},
        {"metric": "total_links_dc", "value": int(len(n.links))},
        {"metric": "total_transformers", "value": int(len(n.transformers))},
        {
            "metric": "total_line_length_km",
            "value": float(n.lines["length"].sum()) if len(n.lines) else 0.0,
        },
        {
            "metric": "unique_v_nom_kv",
            "value": "|".join(
                f"{v:g}" for v in sorted(np.unique(n.buses["v_nom"].astype(float)))
            ),
        },
        {"metric": "source_base_nc", "value": str(base_nc)},
    ]
    summary = pd.DataFrame(summary_rows)
    summary["voltage_bucket"] = ""
    summary["line_count"] = ""
    summary["total_length_km"] = ""

    per_bucket["metric"] = "lines_per_voltage_bucket"
    per_bucket["value"] = ""
    per_bucket = per_bucket[
        ["metric", "value", "voltage_bucket", "line_count", "total_length_km"]
    ]

    return pd.concat([summary, per_bucket], ignore_index=True)
