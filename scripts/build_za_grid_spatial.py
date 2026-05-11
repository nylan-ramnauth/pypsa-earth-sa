# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Master orchestrator for ZA Calibration Plan Module 09 — Grid Spatial Model.

Usage:
    snakemake --configfile configs/za/za_2023_fixed_validation.yaml build_za_grid_spatial
or directly:
    python scripts/build_za_grid_spatial.py --configfile configs/za/za_2023_fixed_validation.yaml
"""
import argparse
import logging
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from za_grid_spatial import (  # noqa: E402
    bus_attachments,
    busmap as busmap_mod,
    lock as lock_mod,
    osm_summary as osm_mod,
    reconciliation,
    rsa_corridors,
    supply_regions,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("build_za_grid_spatial")

DATA_AUDIT = Path("data/za_audit")
DATA_DIR = Path("data")
DOC_DIR = Path("doc")


def _load_config(configfile: Path) -> dict:
    with open(configfile, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _resolve_pypsa_rsa_root(config: dict) -> Path:
    raw = config.get("pypsa_rsa_root")
    if not raw:
        raise SystemExit("config missing required key 'pypsa_rsa_root'")
    path = Path(raw).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"pypsa_rsa_root does not exist: {path}")
    return path


def _resolve_run_name(config: dict) -> str:
    run_cfg = config.get("run", {}) or {}
    name = run_cfg.get("name", "default")
    if isinstance(name, dict):
        name = name.get("default", "default")
    return str(name)


def run(configfile: Path) -> dict:
    config = _load_config(configfile)
    pypsa_rsa_root = _resolve_pypsa_rsa_root(config)
    run_name = _resolve_run_name(config)

    grid_cfg = config.get("za_grid_spatial", {})
    if not grid_cfg:
        raise SystemExit("config missing required block 'za_grid_spatial'")

    level = int(grid_cfg.get("spatial_level", 34))
    if level != 34:
        raise SystemExit(f"Module 09 V1 locked to level 34, got {level}")

    sil_mw = {int(k): float(v) for k, v in grid_cfg["sil_mw"].items()}
    thermal_mw = {int(k): float(v) for k, v in grid_cfg["thermal_mw"].items()}
    n1 = float(grid_cfg.get("n1_approx_single_lines", 0.7))
    st_clair = grid_cfg.get("st_clair_coefficients", [53.736, -0.65])

    # --- inputs ---
    base_nc = Path(f"networks/{run_name}/base.nc")
    elec_s_nc = Path(f"networks/{run_name}/elec_s.nc")
    existing_lines = DATA_AUDIT / "za_rsa_existing_lines_220kv_plus.geojson"
    custom_powerplants = DATA_DIR / "custom_powerplants.csv"
    load_weights = DATA_AUDIT / "za_2023_load_allocation_weights.csv"
    import_export = DATA_AUDIT / "za_2023_import_export_attachment.csv"
    other_re = DATA_AUDIT / "za_2023_other_re_attachment.csv"

    for required in (base_nc, elec_s_nc, existing_lines, custom_powerplants,
                     load_weights, import_export, other_re):
        if not required.exists():
            raise SystemExit(f"missing required input: {required}")

    # --- outputs ---
    out_custom_busmap = DATA_DIR / "custom_busmap_elec_s_34.csv"
    out_osm_summary = DATA_AUDIT / "za_pypsa_earth_osm_grid_summary.csv"
    out_rsa_corridors = DATA_AUDIT / "za_rsa_interregional_transfer_limits.csv"
    out_reconciliation = DATA_AUDIT / "za_grid_reconciliation.csv"
    out_lock = DATA_AUDIT / "za_spatial_level_lock.csv"
    out_plant_bus = DATA_AUDIT / "za_plant_bus_assignment.csv"
    out_demand_bus = DATA_AUDIT / "za_demand_bus_attachment.csv"
    out_ie_bus = DATA_AUDIT / "za_import_export_bus_attachment.csv"
    out_other_re_bus = DATA_AUDIT / "za_other_re_bus_attachment.csv"
    out_busmap_coverage = DATA_AUDIT / "za_custom_busmap_coverage.csv"
    out_reconciliation_md = DOC_DIR / "za_grid_reconciliation.md"

    DATA_AUDIT.mkdir(parents=True, exist_ok=True)

    # --- stage 1: load 34-region supply layer ---
    logger.info("Loading pypsa-rsa 34-region supply layer")
    regions = supply_regions.load_34_layer(pypsa_rsa_root)
    layer_path = pypsa_rsa_root / supply_regions.SUPPLY_REGION_GPKG_REL

    # --- stage 2: spatial lock ---
    logger.info("Writing spatial level lock CSV")
    lock_mod.write_lock_csv(
        out_lock,
        level=level,
        source_decision=grid_cfg.get("source_decision", "Stage 4b"),
        layer_path=layer_path,
        layer_features=len(regions),
    )

    # --- stage 3: OSM summary ---
    logger.info("Summarising PyPSA-Earth OSM base network")
    osm_summary_df = osm_mod.summarise_base_network(base_nc)
    osm_summary_df.to_csv(out_osm_summary, index=False)

    # --- stage 4: RSA corridor table ---
    logger.info("Building RSA interregional corridor benchmark")
    corridor_df = rsa_corridors.build_corridor_table(
        existing_lines,
        regions,
        sil_mw=sil_mw,
        thermal_mw=thermal_mw,
        n1_factor=n1,
        st_clair_a=float(st_clair[0]),
        st_clair_b=float(st_clair[1]),
    )
    corridor_df.to_csv(out_rsa_corridors, index=False)

    # --- stage 5: custom busmap ---
    logger.info("Building custom busmap from simplified network")
    busmap_df, coverage_df = busmap_mod.assign_buses_to_regions(elec_s_nc, regions)
    busmap_mod.write_busmap_csv(busmap_df, out_custom_busmap)
    coverage_df.to_csv(out_busmap_coverage, index=False)

    # --- stage 6: bus attachments ---
    logger.info("Building plant bus assignments + back-filling custom_powerplants.csv")
    plant_audit, updated_pp, n_backfilled = bus_attachments.assign_plants(
        custom_powerplants, regions
    )
    plant_audit.to_csv(out_plant_bus, index=False)
    updated_pp.to_csv(custom_powerplants)
    logger.info("Back-filled bus on %d plants", n_backfilled)

    logger.info("Building demand/import-export/other_re bus attachments")
    demand_df = bus_attachments.build_demand_attachment(load_weights, regions)
    demand_df.to_csv(out_demand_bus, index=False)
    ie_df = bus_attachments.build_import_export_attachment(import_export, regions)
    ie_df.to_csv(out_ie_bus, index=False)
    other_re_df = bus_attachments.build_other_re_attachment(other_re, regions)
    other_re_df.to_csv(out_other_re_bus, index=False)

    # --- stage 7: reconciliation table + markdown ---
    logger.info("Writing reconciliation table and markdown report")
    import geopandas as gpd
    existing_count = int(len(gpd.read_file(existing_lines)))
    recon_df = reconciliation.build_reconciliation_table(
        osm_summary_df, corridor_df, existing_count
    )
    recon_df.to_csv(out_reconciliation, index=False)
    reconciliation.write_markdown(
        out_reconciliation_md, osm_summary_df, corridor_df, recon_df, grid_cfg
    )

    summary = {
        "level": level,
        "regions": int(len(regions)),
        "osm_summary_rows": int(len(osm_summary_df)),
        "rsa_corridors": int(len(corridor_df)),
        "busmap_buses": int(len(busmap_df)),
        "busmap_regions_used": int(busmap_df["region_id"].nunique()),
        "plant_assignments": int(len(plant_audit)),
        "plants_backfilled": n_backfilled,
        "demand_rows": int(len(demand_df)),
        "import_export_rows": int(len(ie_df)),
        "other_re_rows": int(len(other_re_df)),
    }
    logger.info("Module 09 summary: %s", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--configfile", required=True, type=Path)
    args = parser.parse_args(argv)
    summary = run(args.configfile)
    print(summary)
    return 0


def _main_from_snakemake() -> int:
    """Snakemake-driven invocation. Resolves merged config from `snakemake.config`."""
    snake = globals().get("snakemake", None)
    if snake is None:
        return 2
    cfg = dict(snake.config)
    pypsa_rsa_root = _resolve_pypsa_rsa_root(cfg)
    run_name = _resolve_run_name(cfg)

    grid_cfg = cfg.get("za_grid_spatial", {})
    if not grid_cfg:
        raise SystemExit("config missing required block 'za_grid_spatial'")
    level = int(grid_cfg.get("spatial_level", 34))
    if level != 34:
        raise SystemExit(f"Module 09 V1 locked to level 34, got {level}")

    sil_mw = {int(k): float(v) for k, v in grid_cfg["sil_mw"].items()}
    thermal_mw = {int(k): float(v) for k, v in grid_cfg["thermal_mw"].items()}
    n1 = float(grid_cfg.get("n1_approx_single_lines", 0.7))
    st_clair = grid_cfg.get("st_clair_coefficients", [53.736, -0.65])

    base_nc = Path(snake.input.base_network)
    elec_s_nc = Path(snake.input.elec_s)
    existing_lines = Path(snake.input.existing_lines)
    custom_powerplants = Path(snake.input.custom_powerplants)
    load_weights = Path(snake.input.load_weights)
    import_export = Path(snake.input.import_export)
    other_re = Path(snake.input.other_re)

    out_custom_busmap = Path(snake.output.custom_busmap)
    out_osm_summary = Path(snake.output.osm_summary)
    out_rsa_corridors = Path(snake.output.rsa_corridors)
    out_reconciliation = Path(snake.output.reconciliation)
    out_lock = Path(snake.output.level_lock)
    out_plant_bus = Path(snake.output.plant_bus)
    out_demand_bus = Path(snake.output.demand_bus)
    out_ie_bus = Path(snake.output.ie_bus)
    out_other_re_bus = Path(snake.output.other_re_bus)
    out_busmap_coverage = Path(snake.output.busmap_coverage)
    out_reconciliation_md = Path(snake.output.reconciliation_md)

    return _run_stages(
        pypsa_rsa_root, run_name, grid_cfg, sil_mw, thermal_mw, n1, st_clair,
        base_nc, elec_s_nc, existing_lines, custom_powerplants,
        load_weights, import_export, other_re,
        out_custom_busmap, out_osm_summary, out_rsa_corridors, out_reconciliation,
        out_lock, out_plant_bus, out_demand_bus, out_ie_bus, out_other_re_bus,
        out_busmap_coverage, out_reconciliation_md,
    )


def _run_stages(
    pypsa_rsa_root, run_name, grid_cfg, sil_mw, thermal_mw, n1, st_clair,
    base_nc, elec_s_nc, existing_lines, custom_powerplants,
    load_weights, import_export, other_re,
    out_custom_busmap, out_osm_summary, out_rsa_corridors, out_reconciliation,
    out_lock, out_plant_bus, out_demand_bus, out_ie_bus, out_other_re_bus,
    out_busmap_coverage, out_reconciliation_md,
) -> int:
    DATA_AUDIT.mkdir(parents=True, exist_ok=True)

    logger.info("Loading pypsa-rsa 34-region supply layer")
    regions = supply_regions.load_34_layer(pypsa_rsa_root)
    layer_path = pypsa_rsa_root / supply_regions.SUPPLY_REGION_GPKG_REL

    logger.info("Writing spatial level lock CSV")
    lock_mod.write_lock_csv(
        out_lock,
        level=int(grid_cfg.get("spatial_level", 34)),
        source_decision=grid_cfg.get("source_decision", "Stage 4b"),
        layer_path=layer_path,
        layer_features=len(regions),
    )

    logger.info("Summarising PyPSA-Earth OSM base network")
    osm_summary_df = osm_mod.summarise_base_network(base_nc)
    osm_summary_df.to_csv(out_osm_summary, index=False)

    logger.info("Building RSA interregional corridor benchmark")
    corridor_df = rsa_corridors.build_corridor_table(
        existing_lines, regions,
        sil_mw=sil_mw, thermal_mw=thermal_mw,
        n1_factor=n1,
        st_clair_a=float(st_clair[0]), st_clair_b=float(st_clair[1]),
    )
    corridor_df.to_csv(out_rsa_corridors, index=False)

    logger.info("Building custom busmap from simplified network")
    busmap_df, coverage_df = busmap_mod.assign_buses_to_regions(elec_s_nc, regions)
    busmap_mod.write_busmap_csv(busmap_df, out_custom_busmap)
    coverage_df.to_csv(out_busmap_coverage, index=False)

    logger.info("Building plant bus assignments + back-filling custom_powerplants.csv")
    plant_audit, updated_pp, n_backfilled = bus_attachments.assign_plants(
        custom_powerplants, regions
    )
    plant_audit.to_csv(out_plant_bus, index=False)
    updated_pp.to_csv(custom_powerplants)
    logger.info("Back-filled bus on %d plants", n_backfilled)

    logger.info("Building demand/import-export/other_re bus attachments")
    demand_df = bus_attachments.build_demand_attachment(load_weights, regions)
    demand_df.to_csv(out_demand_bus, index=False)
    ie_df = bus_attachments.build_import_export_attachment(import_export, regions)
    ie_df.to_csv(out_ie_bus, index=False)
    other_re_df = bus_attachments.build_other_re_attachment(other_re, regions)
    other_re_df.to_csv(out_other_re_bus, index=False)

    logger.info("Writing reconciliation table and markdown report")
    import geopandas as gpd
    existing_count = int(len(gpd.read_file(existing_lines)))
    recon_df = reconciliation.build_reconciliation_table(
        osm_summary_df, corridor_df, existing_count
    )
    recon_df.to_csv(out_reconciliation, index=False)
    reconciliation.write_markdown(
        out_reconciliation_md, osm_summary_df, corridor_df, recon_df, grid_cfg
    )

    summary = {
        "regions": int(len(regions)),
        "osm_summary_rows": int(len(osm_summary_df)),
        "rsa_corridors": int(len(corridor_df)),
        "busmap_buses": int(len(busmap_df)),
        "busmap_regions_used": int(busmap_df["region_id"].nunique()),
        "plant_assignments": int(len(plant_audit)),
        "plants_backfilled": n_backfilled,
        "demand_rows": int(len(demand_df)),
        "import_export_rows": int(len(ie_df)),
        "other_re_rows": int(len(other_re_df)),
    }
    logger.info("Module 09 summary: %s", summary)
    return 0


if "snakemake" in globals():
    raise SystemExit(_main_from_snakemake())


if __name__ == "__main__":
    sys.exit(main())
