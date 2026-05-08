# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""ZA Module 04 — PyPSA-RSA source registry + discovery sweep."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .io import (
    REGISTRY_COLUMNS,
    count_lines_csv,
    list_xlsx_sheets,
    registry_row,
    sha256_of_dir_listing,
    sha256_of_file,
    write_registry_csv,
)


# Minimum coverage list per Calibration Plan §"Core PyPSA-RSA Data Registry"
# plus candidate-missing-files §6.
# Fields: (rel_path, port_policy, owning_module, baseline_use, expansion_use, notes)
MIN_COVERAGE = [
    ("README.md",                                                  "audit_only",                  "04", "audit_only",            "audit_only",                       "PyPSA-RSA repo README at pinned commit"),
    ("config.yaml",                                                "validation_reference",        "04", "audit_only",            "audit_only",                       "PyPSA-RSA Snakemake config; reference for grid/load options"),
    ("Snakefile",                                                  "audit_only",                  "04", "audit_only",            "audit_only",                       "PyPSA-RSA Snakefile"),
    ("scripts/add_electricity.py",                                 "validation_reference",        "07", "validation_reference",  "audit_only",                       "Cost/fuel/heat-rate transformation reference"),
    ("scripts/build_topology.py",                                  "validation_reference",        "09", "audit_only",            "audit_only",                       "Supply-region topology reference"),
    ("scripts/base_network.py",                                    "validation_reference",        "09", "audit_only",            "audit_only",                       "Base network construction reference"),
    ("scripts/_helpers.py",                                        "audit_only",                  "04", "audit_only",            "audit_only",                       "Shared helpers"),
    ("scripts/custom_constraints.py",                              "audit_only",                  "13", "audit_only",            "audit_only",                       "Custom constraint examples (expansion handoff)"),
    ("scripts/prepare_and_solve_network.py",                       "audit_only",                  "13", "audit_only",            "audit_only",                       "Workflow constraint logic; expansion handoff candidate"),
    ("envs/environment.yaml",                                      "audit_only",                  "04", "audit_only",            "audit_only",                       "PyPSA-RSA conda env; version reference"),
    ("data/eskom_data.csv",                                        "validation_reference",        "02", "validation_reference",  "audit_only",                       "Validation reference; not first-choice 2023 input"),
    ("data/eskom_pu_profiles.csv",                                 "validation_reference",        "03", "validation_reference",  "audit_only",                       "Profile reference; consumed by Module 03 Gate B"),
    ("data/bundle/SystemEnergy2009_22.csv",                        "validation_reference",        "06", "validation_reference",  "audit_only",                       "Historical system energy series"),
    ("data/bundle/Supply area normalised power feed-in for Wind.xlsx", "validation_reference",     "03", "validation_reference",  "audit_only",                       "PyPSA-RSA wind reference profiles by supply area"),
    ("data/bundle/Supply area normalised power feed-in for PV.xlsx",   "validation_reference",     "03", "validation_reference",  "audit_only",                       "PyPSA-RSA PV reference profiles by supply area"),
    ("data/turbine_power_curves.csv",                              "audit_only",                  "03", "audit_only",            "audit_only",                       "Turbine power curve library"),
    ("data/ambitions_validation.xlsx",                             "audit_only",                  "12", "audit_only",            "audit_only",                       "Ambition/validation workbook"),
    ("data/bundle/renewable_profiles_updated.nc",                  "validation_reference",        "03", "validation_reference",  "audit_only",                       "Aggregated renewable profile NetCDF"),
    # Scenario workbooks (ME IRP 2024)
    ("scenarios/ME IRP 2024/scenarios_to_run.xlsx",                "validation_reference",        "08", "audit_only",            "expansion_input_after_review",     "ME IRP 2024 master scenario workbook"),
    ("scenarios/ME IRP 2024/sub_scenarios/annual_load.xlsx",       "validation_reference",        "06", "audit_only",            "expansion_input_after_review",     "ME IRP annual load"),
    ("scenarios/ME IRP 2024/sub_scenarios/carbon_constraints.xlsx", "validation_reference",       "07", "audit_only",            "expansion_input_after_review",     "ME IRP carbon constraints"),
    ("scenarios/ME IRP 2024/sub_scenarios/fixed_technologies.xlsx", "validation_reference",       "08", "baseline_input_after_review", "expansion_input_after_review", "ME IRP fixed technologies — fleet candidates"),
    ("scenarios/ME IRP 2024/sub_scenarios/extendable_technologies.xlsx", "validation_reference",  "13", "audit_only",            "expansion_input_after_review",     "ME IRP extendable techs"),
    ("scenarios/ME IRP 2024/sub_scenarios/operational_constraints.xlsx", "validation_reference",  "11", "validation_reference",  "expansion_input_after_review",     "Operational constraints"),
    ("scenarios/ME IRP 2024/sub_scenarios/plant_availability.xlsx", "validation_reference",       "11", "validation_reference",  "expansion_input_after_review",     "Plant availability"),
    ("scenarios/ME IRP 2024/sub_scenarios/reserve_margin.xlsx",    "validation_reference",        "11", "validation_reference",  "expansion_input_after_review",     "Reserve margin"),
    ("scenarios/ME IRP 2024/sub_scenarios/transmission_expansion.xlsx", "validation_reference",   "13", "audit_only",            "expansion_input_after_review",     "TDP corridor evidence; expansion handoff"),
    # Scenario workbooks (Coal Flexibilisation)
    ("scenarios/Coal_Flexibilisation/scenarios_to_run.xlsx",       "validation_reference",        "08", "audit_only",            "expansion_input_after_review",     "Coal flex master scenario workbook"),
    ("scenarios/Coal_Flexibilisation/sub_scenarios/annual_load.xlsx", "validation_reference",     "06", "audit_only",            "expansion_input_after_review",     "Coal flex annual load"),
    ("scenarios/Coal_Flexibilisation/sub_scenarios/aux_stg_feed.xlsx","audit_only",               "08", "audit_only",            "audit_only",                       "Auxiliary storage feed"),
    ("scenarios/Coal_Flexibilisation/sub_scenarios/emissions.xlsx","validation_reference",        "07", "audit_only",            "expansion_input_after_review",     "Emissions factors"),
    ("scenarios/Coal_Flexibilisation/sub_scenarios/extendable_technologies.xlsx","validation_reference","13","audit_only",       "expansion_input_after_review",     "Coal flex extendable techs"),
    ("scenarios/Coal_Flexibilisation/sub_scenarios/fixed_technologies.xlsx","validation_reference","08","baseline_input_after_review","expansion_input_after_review", "Coal flex fixed technologies — fleet candidates"),
    ("scenarios/Coal_Flexibilisation/sub_scenarios/fuel_prices.xlsx","validation_reference",      "07", "validation_reference",  "expansion_input_after_review",     "Fuel prices"),
    ("scenarios/Coal_Flexibilisation/sub_scenarios/operational_constraints.xlsx","validation_reference","11","validation_reference","expansion_input_after_review", "Operational constraints"),
    ("scenarios/Coal_Flexibilisation/sub_scenarios/phased_decommissioning.xlsx","validation_reference","08","baseline_input_after_review","expansion_input_after_review","IRP-style coal retirement schedule analogue"),
    ("scenarios/Coal_Flexibilisation/sub_scenarios/plant_availability.xlsx","validation_reference","11","validation_reference",   "expansion_input_after_review",     "Plant availability"),
    ("scenarios/Coal_Flexibilisation/sub_scenarios/reserve_margin.xlsx","validation_reference",   "11", "validation_reference",  "expansion_input_after_review",     "Reserve margin"),
    ("scenarios/Coal_Flexibilisation/sub_scenarios/transmission_expansion.xlsx","validation_reference","13","audit_only",        "expansion_input_after_review",     "Coal flex TDP corridors"),
    ("scenarios/Coal_Flexibilisation/sub_scenarios/weather.xlsx",  "audit_only",                  "03", "audit_only",            "audit_only",                       "Weather year toggles"),
    # REIPPPP + pre_processing
    ("pre_processing/resource_processing/reipppp_solar_data.csv",  "validation_reference",        "08", "baseline_input_after_review", "expansion_input_after_review", "REIPPPP solar plants"),
    ("pre_processing/resource_processing/reipppp_wind_data.csv",   "validation_reference",        "08", "baseline_input_after_review", "expansion_input_after_review", "REIPPPP wind plants"),
    ("pre_processing/resource_processing/csir_fise_SWA_data.xlsx", "audit_only",                  "03", "audit_only",            "audit_only",                       "CSIR FISE SWA workbook"),
    # GIS layers
    ("data/bundle/supply_regions/rsa_supply_regions.gpkg",         "validation_reference",        "09", "validation_reference",  "expansion_input_after_review",     "Primary supply-region GeoPackage"),
    ("data/bundle/supply_regions/rsa_supply_regions2.gpkg",        "validation_reference",        "09", "validation_reference",  "expansion_input_after_review",     "Secondary supply-region GeoPackage"),
    ("data/bundle/CSIR/Mesozones",                                 "audit_only",                  "06", "audit_only",            "audit_only",                       "CSIR Mesozones directory; traversed by load_weights audit"),
    ("data/bundle/GCCA 2025 GIS/AREAS_GCCA2025.gpkg",              "audit_only",                  "09", "audit_only",            "audit_only",                       "GCCA 2025 supply areas"),
    ("data/bundle/GCCA 2025 GIS/SUPPLY_AREA_GCCA2025.shp",         "audit_only",                  "09", "audit_only",            "audit_only",                       "GCCA 2025 supply-area shapefile"),
    ("data/bundle/GCCA 2025 GIS/LOCAL_AREA_GCCA2025.shp",          "audit_only",                  "09", "audit_only",            "audit_only",                       "GCCA 2025 local-area shapefile"),
    ("data/bundle/GCCA 2025 GIS/MTS_ZONES_GCCA2025.shp",           "audit_only",                  "09", "audit_only",            "audit_only",                       "GCCA 2025 MTS zones"),
    ("data/bundle/Shapefiles/Existing_Lines.shp",                  "validation_reference",        "09", "validation_reference",  "expansion_input_after_review",     "Existing transmission lines"),
    ("data/bundle/Shapefiles/Planned_Lines.shp",                   "validation_reference",        "13", "audit_only",            "expansion_input_after_review",     "Planned transmission lines"),
    ("data/bundle/Shapefiles/Existing_Substations.shp",            "audit_only",                  "09", "audit_only",            "audit_only",                       "Existing substations"),
    ("data/bundle/Shapefiles/Planned_Substations.shp",             "audit_only",                  "13", "audit_only",            "audit_only",                       "Planned substations"),
    ("data/bundle/Shapefiles/MTS_Subs2022.shp",                    "audit_only",                  "09", "audit_only",            "audit_only",                       "Main Transmission Substations 2022"),
    ("data/bundle/transmission_grid/eskom_gcca_2022/Existing_Lines.shp", "audit_only",            "09", "audit_only",            "audit_only",                       "GCCA 2022 existing lines (deeper copy)"),
    ("data/bundle/transmission_grid/tdp_digitised/TDP_2023_32.shp","audit_only",                  "13", "audit_only",            "expansion_input_after_review",     "TDP 2023 digitised corridors"),
    # Resource siting evidence
    ("data/bundle/Power_corridors",                                "audit_only",                  "13", "audit_only",            "expansion_input_after_review",     "Power corridors directory"),
    ("data/bundle/REDZ_DEA_Unpublished_Draft_2015",                "audit_only",                  "13", "audit_only",            "expansion_input_after_review",     "REDZ DEA unpublished draft"),
    ("data/bundle/Phase2_REDZs",                                   "audit_only",                  "13", "audit_only",            "expansion_input_after_review",     "Phase 2 REDZs"),
    ("data/bundle/SAPAD_OR_2023_Q3.shp",                           "audit_only",                  "13", "audit_only",            "expansion_input_after_review",     "Protected areas (SAPAD)"),
    ("data/bundle/SACAD_OR_2023_Q3.shp",                           "audit_only",                  "13", "audit_only",            "expansion_input_after_review",     "Conservation areas (SACAD)"),
    ("data/bundle/SALandCover_OriginalUTM35North_2013_GTI_72Classes", "audit_only",               "13", "audit_only",            "expansion_input_after_review",     "SA land cover classification raster set"),
    ("data/bundle/ZAF_wind-speed_100m.tif",                        "audit_only",                  "13", "audit_only",            "expansion_input_after_review",     "ZAF wind speed @100m"),
    ("data/bundle/ZAF15adjv4.tif",                                 "audit_only",                  "13", "audit_only",            "expansion_input_after_review",     "ZAF 15s adjusted DEM"),
    ("data/bundle/Shapefiles/RE_IPP_1_to_4b.shp",                  "audit_only",                  "08", "audit_only",            "expansion_input_after_review",     "REIPPPP rounds 1–4b siting"),
    # Duplicate flat copy designations
    ("data/bundle/Existing_Lines.shp",                             "do_not_port",                 "09", "audit_only",            "audit_only",                       "Flat copy; canonical lives at data/bundle/Shapefiles/Existing_Lines.shp"),
    ("data/bundle/TDP_2023_32.shp",                                "do_not_port",                 "13", "audit_only",            "audit_only",                       "Flat copy; canonical at data/bundle/transmission_grid/tdp_digitised/TDP_2023_32.shp"),
    # Candidate-missing absent at pin
    ("scripts/solve_network.py",                                   "do_not_port",                 "11", "audit_only",            "audit_only",                       "Not present at pinned commit"),
    ("scripts/add_extra_components.py",                            "do_not_port",                 "08", "audit_only",            "audit_only",                       "Not present at pinned commit"),
    ("scripts/build_renewable_profiles.py",                        "do_not_port",                 "03", "audit_only",            "audit_only",                       "Not present at pinned commit"),
    ("pre_processing/resource_processing/reipppp_phs_data.csv",    "do_not_port",                 "08", "audit_only",            "audit_only",                       "Not present at pinned commit"),
]


def _classify_path(rel: str) -> str:
    rel_lower = rel.lower()
    if rel_lower.endswith(".gpkg") or rel_lower.endswith(".shp"):
        return "spatial"
    if rel_lower.endswith(".xlsx"):
        return "workbook"
    if rel_lower.endswith(".csv"):
        return "tabular"
    if rel_lower.endswith(".nc"):
        return "netcdf"
    if rel_lower.endswith(".tif"):
        return "raster"
    if rel_lower.endswith(".py"):
        return "script"
    if rel_lower.endswith(".ipynb"):
        return "notebook"
    if rel_lower.endswith(".md"):
        return "markdown"
    if rel_lower.endswith((".pdf", ".xml", ".yaml", ".yml")):
        return "documentation"
    return "other"


def _row_count_for(abs_path: Path) -> int:
    """Best-effort row count for a single file. -1 if not applicable."""
    try:
        suffix = abs_path.suffix.lower()
        if abs_path.is_dir():
            return -1
        if suffix == ".csv":
            return count_lines_csv(abs_path)
        if suffix == ".xlsx":
            sheets = list_xlsx_sheets(abs_path)
            return sum(max(s["n_rows"] - 1, 0) for s in sheets)  # exclude headers
        if suffix in {".shp", ".gpkg"}:
            try:
                import geopandas as gpd

                if suffix == ".gpkg":
                    import fiona

                    with fiona.Env():
                        layers = fiona.listlayers(str(abs_path))
                    total = 0
                    for layer in layers:
                        gdf = gpd.read_file(abs_path, layer=layer)
                        total += len(gdf)
                    return int(total)
                return int(len(gpd.read_file(abs_path)))
            except Exception:
                return -1
    except Exception:
        return -1
    return -1


def _hash_for(abs_path: Path) -> str:
    if abs_path.is_dir():
        return sha256_of_dir_listing(abs_path)
    if abs_path.is_file():
        return sha256_of_file(abs_path)
    return ""


def build_source_registry(pypsa_rsa_root: Path, out_path: Path) -> int:
    rows: list[dict] = []
    for rel, port_policy, owning, baseline, expansion, notes in MIN_COVERAGE:
        abs_path = pypsa_rsa_root / rel
        present = abs_path.exists()
        tracked = "external" if rel.startswith("data/bundle/") else "tracked"
        if not present:
            rows.append(
                registry_row(
                    source_path=rel,
                    tracked_or_external=tracked,
                    file_hash="",
                    sheet_or_layer="",
                    row_count=-1,
                    port_policy=port_policy,
                    owning_module=owning,
                    baseline_use=baseline,
                    expansion_use=expansion,
                    notes=f"ABSENT at pin: {notes}",
                )
            )
            continue
        sheet_or_layer = ""
        row_count = _row_count_for(abs_path)
        if abs_path.suffix.lower() == ".xlsx":
            sheet_or_layer = ";".join(s["sheet"] for s in list_xlsx_sheets(abs_path))
        elif abs_path.suffix.lower() == ".gpkg":
            try:
                import fiona

                sheet_or_layer = ";".join(fiona.listlayers(str(abs_path)))
            except Exception:
                pass
        elif abs_path.is_dir():
            sheet_or_layer = "<directory>"
        rows.append(
            registry_row(
                source_path=rel,
                tracked_or_external=tracked,
                file_hash=_hash_for(abs_path),
                sheet_or_layer=sheet_or_layer,
                row_count=row_count,
                port_policy=port_policy,
                owning_module=owning,
                baseline_use=baseline,
                expansion_use=expansion,
                notes=notes,
            )
        )
    return write_registry_csv(rows, out_path)


def build_discovery_sweep(pypsa_rsa_root: Path, out_path: Path, threshold_bytes: int = 10 * 1024) -> int:
    """Walk the pypsa-rsa repo and record every ≥10 KB candidate file."""
    base = Path(pypsa_rsa_root)
    suffixes = {".py", ".xlsx", ".csv", ".gpkg", ".shp", ".nc", ".tif", ".ipynb"}
    covered = {rel for rel, *_ in MIN_COVERAGE}
    records: list[dict] = []
    for p in base.rglob("*"):
        if not p.is_file():
            continue
        if ".git" in p.parts or "__pycache__" in p.parts:
            continue
        if p.suffix.lower() not in suffixes:
            continue
        try:
            size = p.stat().st_size
        except Exception:
            continue
        if size < threshold_bytes:
            continue
        rel = str(p.relative_to(base))
        records.append(
            {
                "rel_path": rel,
                "size_bytes": size,
                "suffix": p.suffix.lower(),
                "kind": _classify_path(rel),
                "in_min_coverage": rel in covered,
                "classification": "covered" if rel in covered else "audit_only",
            }
        )
    df = pd.DataFrame(records).sort_values(["kind", "rel_path"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return len(df)
