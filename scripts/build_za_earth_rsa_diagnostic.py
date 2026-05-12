# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Master orchestrator for ZA Calibration Plan Module 10 — Earth-vs-RSA
baseline diagnostic.

Usage:
    snakemake --configfile configs/za/za_2023_fixed_validation.yaml \\
        build_za_earth_rsa_diagnostic

or directly:
    python scripts/build_za_earth_rsa_diagnostic.py \\
        --configfile configs/za/za_2023_fixed_validation.yaml

Audit-only. Modifies in-place:
    - data/za_audit/za_grid_reconciliation.csv (fills NaN per-voltage cells)
    - data/za_audit/za_powerplant_reconciliation.csv (back-fills capacity_mw_ppm)

Writes new:
    - data/za_audit/za_ppm_vs_rsa_fleet_comparison.csv
    - data/za_audit/za_ppm_plants_not_in_rsa.csv
    - data/za_audit/za_rsa_plants_not_in_ppm.csv
    - data/za_audit/za_substations_comparison.csv
    - data/za_audit/za_rsa_substations_derived.csv
    - data/za_audit/za_osm_vs_stclair_ratings_comparison.csv
    - doc/za_earth_rsa_baseline_diagnostic.md
    - doc/za_validation/figures/10_diagnostic/*.png
    - doc/za_validation/figures/10_diagnostic/earth_rsa_diagnostic.html
"""
import argparse
import logging
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from za_diagnostic import (  # noqa: E402
    fleet_comparison,
    grid_voltage,
    substations,
    ratings_comparison,
    report,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("build_za_earth_rsa_diagnostic")

DATA_AUDIT = ROOT / "data" / "za_audit"
DOC_DIR = ROOT / "doc"
FIGURES_DIR = DOC_DIR / "za_validation" / "figures" / "10_diagnostic"
NOTEBOOK = ROOT / "notebooks" / "za_validation" / "10_diagnostic" / "earth_rsa_diagnostic.ipynb"


def _load_config(configfile: Path) -> dict:
    with open(configfile, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _resolve_run_name(config: dict) -> str:
    run_cfg = config.get("run", {}) or {}
    name = run_cfg.get("name", "default")
    if isinstance(name, dict):
        name = name.get("default", "default")
    return str(name)


def _run_stages(
    run_name: str,
    reconciliation_csv: Path,
    grid_reconciliation_csv: Path,
    existing_lines_geojson: Path,
    clean_substations_geojson: Path,
    transfer_limits_csv: Path,
    elec_s_34_nc: Path,
    pm_config_path: Path,
    out_report_md: Path,
) -> int:
    DATA_AUDIT.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("=== Module 10 stage 1/5: Fleet (PPM vs RSA) ===")
    fleet_comparison.run_fleet_comparison(reconciliation_csv, DATA_AUDIT, pm_config_path)

    logger.info("=== Module 10 stage 2/5: Grid lines per voltage ===")
    grid_voltage.run_grid_voltage(existing_lines_geojson, grid_reconciliation_csv)

    logger.info("=== Module 10 stage 3/5: Substations ===")
    substations.run_substations(
        existing_lines_geojson, clean_substations_geojson, DATA_AUDIT
    )

    logger.info("=== Module 10 stage 4/5: Line ratings vs St Clair N-1 ===")
    ratings_comparison.run_ratings_comparison(
        transfer_limits_csv, elec_s_34_nc, DATA_AUDIT
    )

    logger.info("=== Module 10 stage 5/5: Report + plots ===")
    report.write_report(
        audit_dir=DATA_AUDIT,
        figures_dir=FIGURES_DIR,
        out_md=out_report_md,
        existing_lines_geojson=existing_lines_geojson,
        clean_substations_geojson=clean_substations_geojson,
        elec_s_34_nc=elec_s_34_nc,
    )

    out_html = FIGURES_DIR / "earth_rsa_diagnostic.html"
    report.maybe_execute_notebook(NOTEBOOK, out_html)

    logger.info("Module 10 complete. Report: %s", out_report_md)
    return 0


def run(configfile: Path) -> int:
    config = _load_config(configfile)
    run_name = _resolve_run_name(config)

    reconciliation_csv = DATA_AUDIT / "za_powerplant_reconciliation.csv"
    grid_reconciliation_csv = DATA_AUDIT / "za_grid_reconciliation.csv"
    existing_lines_geojson = DATA_AUDIT / "za_rsa_existing_lines_220kv_plus.geojson"
    clean_substations_geojson = (
        ROOT / "resources" / run_name / "osm" / "clean" / "all_clean_substations.geojson"
    )
    transfer_limits_csv = DATA_AUDIT / "za_rsa_interregional_transfer_limits.csv"
    elec_s_34_nc = ROOT / "networks" / run_name / "elec_s_34.nc"
    pm_config_path = ROOT / "configs" / "powerplantmatching_config.yaml"

    for required in (reconciliation_csv, grid_reconciliation_csv,
                     existing_lines_geojson, clean_substations_geojson,
                     transfer_limits_csv, elec_s_34_nc, pm_config_path):
        if not required.exists():
            raise SystemExit(f"missing required input: {required}")

    out_report_md = DOC_DIR / "za_earth_rsa_baseline_diagnostic.md"
    return _run_stages(
        run_name, reconciliation_csv, grid_reconciliation_csv,
        existing_lines_geojson, clean_substations_geojson,
        transfer_limits_csv, elec_s_34_nc, pm_config_path, out_report_md,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--configfile", required=True, type=Path)
    args = parser.parse_args(argv)
    return run(args.configfile)


def _main_from_snakemake() -> int:
    snake = globals().get("snakemake", None)
    if snake is None:
        return 2
    cfg = dict(snake.config)
    run_name = _resolve_run_name(cfg)

    reconciliation_csv = Path(snake.input.reconciliation)
    grid_reconciliation_csv = Path(snake.input.grid_reconciliation)
    existing_lines_geojson = Path(snake.input.existing_lines)
    clean_substations_geojson = Path(snake.input.clean_substations)
    transfer_limits_csv = Path(snake.input.transfer_limits)
    elec_s_34_nc = Path(snake.input.elec_s_34)
    pm_config_path = Path(snake.input.pm_config)
    out_report_md = Path(snake.output.report)

    return _run_stages(
        run_name, reconciliation_csv, grid_reconciliation_csv,
        existing_lines_geojson, clean_substations_geojson,
        transfer_limits_csv, elec_s_34_nc, pm_config_path, out_report_md,
    )


if "snakemake" in globals():
    raise SystemExit(_main_from_snakemake())


if __name__ == "__main__":
    sys.exit(main())
