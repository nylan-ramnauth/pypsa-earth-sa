# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Master entry point for ZA Calibration Plan Module 04 — Source Data Audits.

Reads `za_source_audits.pypsa_rsa_root` from the active configfile, runs every
audit stage, and writes the full set of audit outputs under `data/za_audit/`.

Usage:
    snakemake --configfile configs/za/za_2023_fixed_validation.yaml build_za_source_audits
or directly:
    python scripts/build_za_source_audits.py --configfile configs/za/za_2023_fixed_validation.yaml
"""

import argparse
import logging
import sys
from pathlib import Path

import yaml

# Allow direct execution (`python scripts/build_za_source_audits.py`)
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from za_audits import (  # noqa: E402
    cost_fuel_emissions,
    fleet_availability,
    grid_spatial,
    load_weights,
    powerplantmatching as ppm_audit,
    profiles,
    registry,
    resource_siting,
    scenario_workbooks,
)
from za_reference_data import source_audit_pypsa_rsa_root  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("build_za_source_audits")

DATA_AUDIT = Path("data/za_audit")
PPM_CONFIG = Path("configs/powerplantmatching_config.yaml")


def _load_config(configfile: Path) -> dict:
    with open(configfile, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _resolve_pypsa_rsa_root(config: dict) -> Path:
    try:
        path = source_audit_pypsa_rsa_root(config)
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc
    if not path.exists():
        raise SystemExit(f"za_source_audits.pypsa_rsa_root does not exist: {path}")
    return path


def _output_paths() -> dict[str, Path]:
    return {
        "registry":                  DATA_AUDIT / "pypsa_rsa_source_registry.csv",
        "discovery":                 DATA_AUDIT / "pypsa_rsa_discovery_sweep.csv",
        "ppm_full":                  DATA_AUDIT / "powerplants_pm_za_full.csv",
        "ppm_audit":                 DATA_AUDIT / "powerplants_pm_za_audit.csv",
        "scenario_workbooks":        DATA_AUDIT / "pypsa_rsa_scenario_workbook_inventory.csv",
        "fixed_tech":                DATA_AUDIT / "pypsa_rsa_fixed_technologies_2023_candidates.csv",
        "reipppp_solar":             DATA_AUDIT / "reipppp_solar_2023_candidates.csv",
        "reipppp_wind":              DATA_AUDIT / "reipppp_wind_2023_candidates.csv",
        "availability":              DATA_AUDIT / "pypsa_rsa_availability_audit.csv",
        "op_constraints":            DATA_AUDIT / "pypsa_rsa_operational_constraints_audit.csv",
        "reserve_margin":            DATA_AUDIT / "pypsa_rsa_reserve_margin_audit.csv",
        "eskom_pu":                  DATA_AUDIT / "pypsa_rsa_eskom_pu_profiles_audit.csv",
        "cost_fuel":                 DATA_AUDIT / "pypsa_rsa_cost_fuel_emissions_audit.csv",
        "load_weights":              DATA_AUDIT / "pypsa_rsa_load_weight_audit.csv",
        "bundle_inv":                DATA_AUDIT / "pypsa_rsa_external_bundle_inventory.csv",
        "supply_regions":            DATA_AUDIT / "za_rsa_supply_regions.geojson",
        "supply_layer_resolution":   DATA_AUDIT / "za_rsa_supply_region_layer_resolution.csv",
        "existing_lines":            DATA_AUDIT / "za_rsa_existing_lines_220kv_plus.geojson",
        "planned_lines":             DATA_AUDIT / "za_rsa_planned_tdp_lines.geojson",
        "supply_area_limits":        DATA_AUDIT / "za_rsa_supply_area_connection_limits.csv",
        "mts_limits":                DATA_AUDIT / "za_rsa_mts_hosting_limits.csv",
        "transmission_expansion":    DATA_AUDIT / "pypsa_rsa_transmission_expansion_audit.csv",
        "resource_siting":           DATA_AUDIT / "pypsa_rsa_resource_siting_audit.csv",
    }


def _stage(name: str, func, *args, **kwargs) -> int:
    logger.info("stage: %s — start", name)
    try:
        n = func(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        logger.exception("stage %s failed: %s", name, exc)
        return -1
    logger.info("stage: %s — wrote %d rows", name, n)
    return n


def main(configfile: Path) -> int:
    config = _load_config(configfile)
    pypsa_rsa_root = _resolve_pypsa_rsa_root(config)
    audit_cfg = config.get("za_source_audits", {}) or {}
    pinned = audit_cfg.get("pypsa_rsa_pinned_commit", config.get("pypsa_rsa_pinned_commit", "<unset>"))
    logger.info("pypsa_rsa_root=%s pinned_commit=%s", pypsa_rsa_root, pinned)

    out = _output_paths()
    DATA_AUDIT.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    counts["registry"] = _stage("source_registry", registry.build_source_registry, pypsa_rsa_root, out["registry"])
    counts["discovery"] = _stage("discovery_sweep", registry.build_discovery_sweep, pypsa_rsa_root, out["discovery"])

    counts["ppm"] = _stage(
        "powerplantmatching",
        ppm_audit.build_powerplantmatching_audit,
        PPM_CONFIG,
        out["ppm_full"],
        out["ppm_audit"],
    )

    counts["scenario_workbooks"] = _stage(
        "scenario_workbooks",
        scenario_workbooks.build_scenario_workbook_inventory,
        pypsa_rsa_root,
        out["scenario_workbooks"],
    )

    counts["fixed_tech"] = _stage("fixed_tech", fleet_availability.build_fixed_technologies_audit, pypsa_rsa_root, out["fixed_tech"])
    counts["reipppp_solar"] = _stage("reipppp_solar", fleet_availability.build_reipppp_solar_audit, pypsa_rsa_root, out["reipppp_solar"])
    counts["reipppp_wind"] = _stage("reipppp_wind", fleet_availability.build_reipppp_wind_audit, pypsa_rsa_root, out["reipppp_wind"])
    counts["availability"] = _stage("availability", fleet_availability.build_availability_audit, pypsa_rsa_root, out["availability"])
    counts["op_constraints"] = _stage("op_constraints", fleet_availability.build_operational_constraints_audit, pypsa_rsa_root, out["op_constraints"])
    counts["reserve_margin"] = _stage("reserve_margin", fleet_availability.build_reserve_margin_audit, pypsa_rsa_root, out["reserve_margin"])

    counts["eskom_pu"] = _stage("eskom_pu_profiles", profiles.build_eskom_pu_profiles_audit, pypsa_rsa_root, out["eskom_pu"])
    counts["cost_fuel"] = _stage("cost_fuel_emissions", cost_fuel_emissions.build_cost_fuel_emissions_audit, pypsa_rsa_root, out["cost_fuel"])
    counts["load_weights"] = _stage("load_weights", load_weights.build_load_weight_audit, pypsa_rsa_root, out["load_weights"])

    counts["bundle_inv"] = _stage("bundle_inventory", grid_spatial.build_external_bundle_inventory, pypsa_rsa_root, out["bundle_inv"])
    counts["supply_layer_resolution"] = _stage(
        "supply_region_layer_resolution",
        grid_spatial.build_supply_region_layer_resolution,
        pypsa_rsa_root,
        out["supply_layer_resolution"],
    )
    counts["supply_regions_geojson"] = _stage(
        "supply_regions_geojson",
        grid_spatial.export_supply_regions_geojson,
        pypsa_rsa_root,
        out["supply_regions"],
    )
    counts["existing_lines_geojson"] = _stage(
        "existing_lines_220kv_plus_geojson",
        grid_spatial.export_existing_lines_220kv_plus,
        pypsa_rsa_root,
        out["existing_lines"],
    )
    counts["planned_tdp_geojson"] = _stage(
        "planned_tdp_lines_geojson",
        grid_spatial.export_planned_tdp_lines,
        pypsa_rsa_root,
        out["planned_lines"],
    )
    counts["supply_area_limits"] = _stage(
        "supply_area_connection_limits",
        grid_spatial.build_supply_area_connection_limits,
        pypsa_rsa_root,
        out["supply_area_limits"],
    )
    counts["mts_limits"] = _stage(
        "mts_hosting_limits",
        grid_spatial.build_mts_hosting_limits,
        pypsa_rsa_root,
        out["mts_limits"],
    )
    counts["transmission_expansion"] = _stage(
        "transmission_expansion",
        grid_spatial.build_transmission_expansion_audit,
        pypsa_rsa_root,
        out["transmission_expansion"],
    )
    counts["resource_siting"] = _stage(
        "resource_siting",
        resource_siting.build_resource_siting_audit,
        pypsa_rsa_root,
        out["resource_siting"],
    )

    logger.info("Module 04 audit summary: %s", counts)
    return 0


def _main_from_snakemake() -> int:
    """Snakemake-driven invocation. Resolves configfile from snakemake.config."""
    snakemake = globals().get("snakemake", None)
    if snakemake is None:
        return 2
    cfg = dict(snakemake.config)
    # Snakemake already merged the configfile; emulate _load_config using cfg.
    pypsa_rsa_root = _resolve_pypsa_rsa_root(cfg)
    audit_cfg = cfg.get("za_source_audits", {}) or {}
    pinned = audit_cfg.get("pypsa_rsa_pinned_commit", cfg.get("pypsa_rsa_pinned_commit", "<unset>"))
    logger.info("pypsa_rsa_root=%s pinned_commit=%s", pypsa_rsa_root, pinned)
    out = _output_paths()
    DATA_AUDIT.mkdir(parents=True, exist_ok=True)

    # Run all stages with the same orchestration as main()
    registry.build_source_registry(pypsa_rsa_root, out["registry"])
    registry.build_discovery_sweep(pypsa_rsa_root, out["discovery"])
    ppm_audit.build_powerplantmatching_audit(PPM_CONFIG, out["ppm_full"], out["ppm_audit"])
    scenario_workbooks.build_scenario_workbook_inventory(pypsa_rsa_root, out["scenario_workbooks"])
    fleet_availability.build_fixed_technologies_audit(pypsa_rsa_root, out["fixed_tech"])
    fleet_availability.build_reipppp_solar_audit(pypsa_rsa_root, out["reipppp_solar"])
    fleet_availability.build_reipppp_wind_audit(pypsa_rsa_root, out["reipppp_wind"])
    fleet_availability.build_availability_audit(pypsa_rsa_root, out["availability"])
    fleet_availability.build_operational_constraints_audit(pypsa_rsa_root, out["op_constraints"])
    fleet_availability.build_reserve_margin_audit(pypsa_rsa_root, out["reserve_margin"])
    profiles.build_eskom_pu_profiles_audit(pypsa_rsa_root, out["eskom_pu"])
    cost_fuel_emissions.build_cost_fuel_emissions_audit(pypsa_rsa_root, out["cost_fuel"])
    load_weights.build_load_weight_audit(pypsa_rsa_root, out["load_weights"])
    grid_spatial.build_external_bundle_inventory(pypsa_rsa_root, out["bundle_inv"])
    grid_spatial.build_supply_region_layer_resolution(pypsa_rsa_root, out["supply_layer_resolution"])
    grid_spatial.export_supply_regions_geojson(pypsa_rsa_root, out["supply_regions"])
    grid_spatial.export_existing_lines_220kv_plus(pypsa_rsa_root, out["existing_lines"])
    grid_spatial.export_planned_tdp_lines(pypsa_rsa_root, out["planned_lines"])
    grid_spatial.build_supply_area_connection_limits(pypsa_rsa_root, out["supply_area_limits"])
    grid_spatial.build_mts_hosting_limits(pypsa_rsa_root, out["mts_limits"])
    grid_spatial.build_transmission_expansion_audit(pypsa_rsa_root, out["transmission_expansion"])
    resource_siting.build_resource_siting_audit(pypsa_rsa_root, out["resource_siting"])
    return 0


if "snakemake" in globals():
    raise SystemExit(_main_from_snakemake())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--configfile", required=True, type=Path)
    args = parser.parse_args()
    raise SystemExit(main(args.configfile))
