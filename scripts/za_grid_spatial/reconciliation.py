# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""OSM vs RSA grid reconciliation report (CSV + Markdown)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


def build_reconciliation_table(
    osm_summary: pd.DataFrame,
    rsa_corridors: pd.DataFrame,
    existing_lines_220kv_plus_count: int,
) -> pd.DataFrame:
    rows: list[dict] = []
    # OSM per-voltage-bucket lines
    osm_per_bucket = osm_summary[osm_summary["metric"] == "lines_per_voltage_bucket"]
    for _, r in osm_per_bucket.iterrows():
        rows.append(
            {
                "voltage_bucket": r["voltage_bucket"],
                "osm_line_count": r["line_count"],
                "osm_length_km": r["total_length_km"],
                "rsa_line_count": "",
                "rsa_length_km": "",
            }
        )
    # RSA roll-up
    if not rsa_corridors.empty:
        rsa_total_length = rsa_corridors["total_length_km"].sum()
        rsa_line_count = int(rsa_corridors["n_lines"].sum())
        rows.append(
            {
                "voltage_bucket": "rsa_220kv_plus_aggregate",
                "osm_line_count": "",
                "osm_length_km": "",
                "rsa_line_count": rsa_line_count,
                "rsa_length_km": float(rsa_total_length),
            }
        )
    rows.append(
        {
            "voltage_bucket": "rsa_existing_lines_220kv_plus_input",
            "osm_line_count": "",
            "osm_length_km": "",
            "rsa_line_count": existing_lines_220kv_plus_count,
            "rsa_length_km": "",
        }
    )
    return pd.DataFrame(rows)


def write_markdown(
    md_path: Path,
    osm_summary: pd.DataFrame,
    rsa_corridors: pd.DataFrame,
    reconciliation_df: pd.DataFrame,
    config_block: dict,
) -> Path:
    md_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# ZA Grid Reconciliation — Module 09",
        "",
        f"_Generated: {now}_",
        "",
        "## Spatial level",
        "",
        f"- Locked level: **{config_block.get('spatial_level')}** Eskom local areas",
        f"- Source decision: {config_block.get('source_decision')}",
        f"- Voltage threshold: ≥ {config_block.get('line_voltage_threshold_kv')} kV",
        f"- St Clair coefficients: {config_block.get('st_clair_coefficients')}",
        "",
        "## St Clair coefficient note",
        "",
        "PyPSA-RSA uses `(53.736, -0.65)` digitised from the St Clair curve reference "
        "linked in `pypsa-rsa/scripts/build_topology.py:241-253`. This differs from "
        "the literature-standard Dunlop fit `(43.261, -0.6678)`. Module 09 uses the "
        "pypsa-rsa value verbatim for consistency with the reference model.",
        "",
        "## OSM grid summary (PyPSA-Earth `base.nc`)",
        "",
        osm_summary.to_markdown(index=False),
        "",
        "## RSA interregional corridor capacities (≥220 kV, N-1 derated)",
        "",
        rsa_corridors.head(60).to_markdown(index=False) if not rsa_corridors.empty else "_no corridors_",
        "",
        "## Reconciliation",
        "",
        reconciliation_df.to_markdown(index=False) if not reconciliation_df.empty else "_no rows_",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path
