# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Canonical markdown report writer for Module 10 diagnostic.

Reads the four output CSVs, embeds plot PNGs, and writes
`doc/za_earth_rsa_baseline_diagnostic.md`. Optionally executes the
validation notebook and exports HTML.
"""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

import pandas as pd

from . import plots

logger = logging.getLogger("za_diagnostic.report")


def _df_to_md(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if max_rows is not None:
        df = df.head(max_rows)
    try:
        return df.to_markdown(index=False)
    except Exception:
        return "```\n" + df.to_string(index=False) + "\n```"


def _save(fig, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    import matplotlib.pyplot as plt
    plt.close(fig)


def write_report(
    audit_dir: Path,
    figures_dir: Path,
    out_md: Path,
    existing_lines_geojson: Path,
    clean_substations_geojson: Path,
    elec_s_34_nc: Path,
) -> Path:
    figures_dir.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    fleet_csv = audit_dir / "za_ppm_vs_rsa_fleet_comparison.csv"
    grid_csv = audit_dir / "za_grid_reconciliation.csv"
    subs_csv = audit_dir / "za_substations_comparison.csv"
    rsa_subs_csv = audit_dir / "za_rsa_substations_derived.csv"
    ratings_csv = audit_dir / "za_osm_vs_stclair_ratings_comparison.csv"

    fleet_df = pd.read_csv(fleet_csv)
    grid_df = pd.read_csv(grid_csv)
    subs_df = pd.read_csv(subs_csv)
    rsa_subs_df = pd.read_csv(rsa_subs_csv)
    ratings_df = pd.read_csv(ratings_csv)

    # --- Generate plots ---
    logger.info("Generating plots into %s", figures_dir)
    _save(plots.plot_fleet_capacity_by_carrier(fleet_df),
          figures_dir / "01_fleet_capacity_by_carrier.png")
    _save(plots.plot_line_count_per_voltage(grid_df),
          figures_dir / "02a_line_count_per_voltage.png")
    _save(plots.plot_line_length_per_voltage(grid_df),
          figures_dir / "02b_line_length_per_voltage.png")
    _save(plots.plot_network_map(elec_s_34_nc, existing_lines_geojson),
          figures_dir / "02c_network_overlay.png")
    _save(plots.plot_substation_count_per_voltage(subs_df),
          figures_dir / "03a_substation_count_per_voltage.png")
    _save(plots.plot_substation_map(
              existing_lines_geojson, rsa_subs_df, clean_substations_geojson),
          figures_dir / "03b_substation_map.png")
    _save(plots.plot_ratings_ratio_distribution(ratings_df),
          figures_dir / "04a_ratings_ratio_distribution.png")
    _save(plots.plot_ratings_scatter(ratings_df),
          figures_dir / "04b_ratings_scatter.png")

    # --- Compose summary verdict ---
    ratings_main = ratings_df[ratings_df["bus0"] != "_summary_"]
    n_over = int((ratings_main["direction"] == "osm_over").sum())
    n_under = int((ratings_main["direction"] == "osm_under").sum())
    n_within = int((ratings_main["direction"] == "within_20pct").sum())
    n_unmatched = int((ratings_main["direction"] == "unmatched").sum())

    subs_total_row = subs_df[subs_df["voltage_bucket"] == "220kv_plus_total"].iloc[0]

    rel_figs = "figures/10_diagnostic"

    md = f"""# Earth–RSA Baseline Diagnostic Report

**Module 10 — Calibration Plan.** Audit-only. Quantifies the gap between
what PyPSA-Earth retrieves by default for South Africa (PPM fleet, OSM grid)
and what PyPSA-RSA uses (modules 06–09 overrides).

## Summary

| Dimension | Earth side | RSA side | Verdict |
|---|---|---|---|
| Fleet | PPM live query, {int(fleet_df['n_plants_matched'].sum() + fleet_df['n_plants_ppm_only'].sum())} plants | {int(fleet_df['n_plants_matched'].sum() + fleet_df['n_plants_rsa_only'].sum())} plants | total delta {fleet_df['delta_mw'].sum():+.0f} MW |
| Lines (220kV+) | {int(grid_df[grid_df['voltage_bucket'].isin(['220kV','275kV','400kV','765kV'])]['osm_line_count'].fillna(0).sum())} | {int(grid_df[grid_df['voltage_bucket'].isin(['220kV','275kV','400kV','765kV'])]['rsa_line_count'].fillna(0).sum())} | see Comparison 2 |
| Substations (220kV+) | {int(subs_total_row['osm_substation_count'])} | {int(subs_total_row['rsa_substation_count'])} | ratio {subs_total_row['osm_coverage_ratio']} |
| Ratings (65 corridors) | s_nom from elec_s_34 | St Clair N-1 | over={n_over}, under={n_under}, within={n_within}, unmatched={n_unmatched} |

---

## Comparison 1 — Powerplant fleet (PPM vs RSA)

PPM live query → ZA subset → fuzzy match (same carrier, ±20 km, ±30% capacity)
against `za_powerplant_reconciliation.csv`. Per-carrier aggregate:

{_df_to_md(fleet_df)}

![Fleet capacity by carrier]({rel_figs}/01_fleet_capacity_by_carrier.png)

Appendix files:
- `data/za_audit/za_ppm_plants_not_in_rsa.csv` — PPM rows with no RSA match
- `data/za_audit/za_rsa_plants_not_in_ppm.csv` — RSA rows with no PPM match

Reconciliation back-fill: `capacity_mw_ppm` / `source_ppm` populated in
`data/za_audit/za_powerplant_reconciliation.csv` for matched rows;
unmatched rows tagged `source_ppm="no_ppm_match"`.

---

## Comparison 2 — Transmission lines per voltage

RSA GeoJSON (324 features) bucketed by `NOMINAL_VO`; lengths via haversine over
each feature's `LineString` coords. Standard buckets {{220, 275, 400, 765}} kV;
features outside reported under `other_kv` (informational).

{_df_to_md(grid_df)}

![Line count per voltage]({rel_figs}/02a_line_count_per_voltage.png)
![Line length per voltage]({rel_figs}/02b_line_length_per_voltage.png)
![Network overlay]({rel_figs}/02c_network_overlay.png)

---

## Comparison 3 — Substations (Earth OSM vs RSA derived)

PyPSA-RSA has no dedicated substations file. RSA substations derived as the
unique union of `LINE_START` ∪ `LINE_END` from the 220kV+ existing-lines
GeoJSON. PyPSA-Earth side: OSM `all_clean_substations.geojson` filtered to
ZA + voltage ≥ 220 kV.

{_df_to_md(subs_df)}

Top RSA substations by incident-line count (sample):

{_df_to_md(rsa_subs_df.sort_values("n_incident_lines", ascending=False), max_rows=15)}

![Substation count per voltage]({rel_figs}/03a_substation_count_per_voltage.png)
![Substation map]({rel_figs}/03b_substation_map.png)

---

## Comparison 4 — Line ratings (OSM s_nom vs St Clair N-1)

Per-corridor: sum `n.lines.s_nom` from `elec_s_34.nc` matched by (bus0, bus1)
to the 65-corridor St Clair N-1 table.

**Per-direction summary (corridor count):**

- `osm_over` (ratio > 1.2): {n_over}
- `within_20pct`: {n_within}
- `osm_under` (ratio < 0.8): {n_under}
- `unmatched` (no OSM lines): {n_unmatched}

![Ratings ratio distribution]({rel_figs}/04a_ratings_ratio_distribution.png)
![Ratings scatter]({rel_figs}/04b_ratings_scatter.png)

Top 10 most over-rated corridors (OSM > St Clair):

{_df_to_md(ratings_main.sort_values('ratio_osm_to_stclair', ascending=False), max_rows=10)}

Top 10 most under-rated corridors (OSM < St Clair):

{_df_to_md(ratings_main[ratings_main['ratio_osm_to_stclair'].notna()].sort_values('ratio_osm_to_stclair', ascending=True), max_rows=10)}

---

## Limitations

- Demand profile comparison is intentionally omitted; module 06 already
  overwrote the GEGIS source with the Eskom 2023 measured profile.
- PPM live query may rotate between cache and source database; rerun annually.
- RSA substation set is derived from line endpoints; missing endpoint
  attribution in the GeoJSON will under-count. OSM substation count uses
  `voltage` tag — substations without a voltage tag are excluded.
- Line-ratings comparison maps clustered-network lines (post-`simplify` +
  cluster to 34 regions) to RSA corridors; if cluster topology fails to span
  a corridor it is flagged `unmatched`.

---

## Reproduction

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml \\
    --cores 1 build_za_earth_rsa_diagnostic
```

Or directly:
```bash
python scripts/build_za_earth_rsa_diagnostic.py \\
    --configfile configs/za/za_2023_fixed_validation.yaml
```
"""
    out_md.write_text(md, encoding="utf-8")
    logger.info("Wrote canonical report: %s", out_md)
    return out_md


def _detect_kernel() -> str:
    """Prefer the `pypsa-earth` Jupyter kernelspec; fall back to `python3`."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "jupyter", "kernelspec", "list"],
            capture_output=True, text=True,
        )
        if "pypsa-earth" in result.stdout:
            return "pypsa-earth"
    except Exception:
        pass
    return "python3"


def maybe_execute_notebook(notebook_path: Path, out_html: Path) -> Path | None:
    """Execute the validation notebook and export HTML.

    No-op (logs a warning) if jupyter/nbconvert unavailable.
    """
    if not notebook_path.exists():
        logger.warning("Notebook not found, skipping HTML export: %s", notebook_path)
        return None

    out_html.parent.mkdir(parents=True, exist_ok=True)
    # Use the current interpreter's jupyter (same env as the script) and pick
    # a kernel that has the pypsa-earth dependencies installed. Try the named
    # `pypsa-earth` kernelspec first (preferred), else fall back to `python3`.
    kernel = _detect_kernel()
    cmd = [
        sys.executable, "-m", "jupyter", "nbconvert",
        "--to", "html",
        "--execute",
        "--ExecutePreprocessor.timeout=600",
        f"--ExecutePreprocessor.kernel_name={kernel}",
        f"--output={out_html.stem}",
        f"--output-dir={out_html.parent}",
        str(notebook_path),
    ]
    logger.info("Executing notebook: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning("nbconvert failed (rc=%d): %s",
                       result.returncode, result.stderr[-500:])
        return None
    logger.info("Wrote notebook HTML: %s", out_html)
    return out_html
