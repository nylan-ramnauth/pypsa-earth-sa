# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Module 13g/13h — replace aggregated coal with named Eskom coal generators.

This script is a drop-in replacement for ``scripts/za_fleet/apply_coal_eaf.py``
when ``za_coal_disaggregation.enable`` is true. It keeps the same Snakemake
input/output contract and mutates only coal generator rows plus their hourly
``generators_t.p_max_pu`` profiles. Module 13h optionally enables coal-only
linearised unit commitment.
"""

import argparse
import logging
import shutil
import sys
from pathlib import Path

import pandas as pd
import pypsa

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from za_fleet.fleet_calibration import resolved_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("build_za_coal_plants_network")


P_NOM_TOLERANCE_MW = 0.5

REQUIRED_PLANT_COLUMNS = {
    "station_name",
    "generator_name",
    "carrier",
    "bus",
    "p_nom_mw",
    "station_p_nom_mw",
    "avg_heat_rate_gj_per_mwh",
    "marginal_cost_eur_per_mwh",
}
REQUIRED_METADATA_COLUMNS = {
    "fleet_mode",
    "availability_mode",
    "outage_profiles_scenario",
    "annual_availability_scenario",
}
REQUIRED_UC_COLUMNS = {
    "ramp_limit_up_per_h",
    "ramp_limit_down_per_h",
    "ramp_limit_start_up_per_h",
    "ramp_limit_shut_down_per_h",
    "start_up_cost_eur",
    "shut_down_cost_eur",
    "min_up_time_h",
    "min_down_time_h",
    "ramp_multiplier_applied",
}
COAL_TARGET_OVERRIDE_SOURCE = (
    "config:za_coal_disaggregation.annual_availability_target_override.coal"
)


def _require_columns(df: pd.DataFrame, columns: set, source: str) -> None:
    missing = columns.difference(df.columns)
    if missing:
        raise SystemExit(f"{source} missing required columns: {sorted(missing)}")


def _unique_non_empty_values(df: pd.DataFrame, column: str) -> set[str]:
    return {
        str(value)
        for value in df[column].dropna().astype(str)
        if str(value).strip()
    }


def _check_csv_value(
    df: pd.DataFrame,
    column: str,
    expected: str | None,
    source: str,
) -> None:
    if expected is None or str(expected).strip() == "":
        return
    if column not in df.columns:
        raise SystemExit(f"{source} missing required metadata column {column!r}")
    actual = _unique_non_empty_values(df, column)
    expected_set = {str(expected)}
    if actual != expected_set:
        raise SystemExit(
            f"Coal CSV {column} {actual} does not match config {str(expected)!r}"
        )


def _check_config_target_override(
    plants: pd.DataFrame,
    plants_csv: Path,
    disagg_config: dict,
) -> None:
    override = disagg_config.get("annual_availability_target_override", {}) or {}
    if not override:
        return
    unsupported = sorted(set(map(str, override)).difference({"coal"}))
    if unsupported:
        raise SystemExit(
            "za_coal_disaggregation.annual_availability_target_override supports "
            f"active Eskom coal only; unsupported carriers: {unsupported}"
        )
    if "coal" not in override:
        return
    required = {
        "annual_availability_target",
        "annual_availability_target_source",
        "annual_availability_target_override_carrier",
        "annual_availability_target_override_value",
    }
    _require_columns(plants, required, str(plants_csv))
    expected = float(override["coal"])
    actual_targets = pd.to_numeric(plants["annual_availability_target"], errors="coerce")
    actual_overrides = pd.to_numeric(
        plants["annual_availability_target_override_value"], errors="coerce"
    )
    if actual_targets.isna().any() or not ((actual_targets - expected).abs() <= 1e-9).all():
        actual = sorted({round(float(v), 12) for v in actual_targets.dropna()})
        raise SystemExit(
            "Coal CSV annual_availability_target "
            f"{actual} does not match config override {expected}"
        )
    if actual_overrides.isna().any() or not ((actual_overrides - expected).abs() <= 1e-9).all():
        actual = sorted({round(float(v), 12) for v in actual_overrides.dropna()})
        raise SystemExit(
            "Coal CSV annual_availability_target_override_value "
            f"{actual} does not match config override {expected}"
        )
    sources = _unique_non_empty_values(plants, "annual_availability_target_source")
    if sources != {COAL_TARGET_OVERRIDE_SOURCE}:
        raise SystemExit(
            "Coal CSV annual_availability_target_source "
            f"{sources} does not match expected {COAL_TARGET_OVERRIDE_SOURCE!r}"
        )
    carriers = _unique_non_empty_values(plants, "annual_availability_target_override_carrier")
    if carriers != {"coal"}:
        raise SystemExit(
            "Coal CSV annual_availability_target_override_carrier "
            f"{carriers} does not match expected 'coal'"
        )


def _normalise_uc_config(disagg_config: dict | None) -> dict:
    disagg_config = disagg_config or {}
    uc = disagg_config.get("uc", {}) or {}
    enabled = bool(uc.get("enable", False))
    msl_mode = str(uc.get("msl_mode", "scale_by_p_max_pu"))
    if enabled and msl_mode != "scale_by_p_max_pu":
        raise SystemExit(f"Unsupported za_coal_disaggregation.uc.msl_mode={msl_mode!r}")
    return {
        "enable": enabled,
        "msl_mode": msl_mode,
        "p_min_pu_base": float(uc.get("p_min_pu_base", 0.7)),
        "ramp_multiplier": float(uc.get("ramp_multiplier", 1.5)),
        "apply_min_up_down_time": bool(uc.get("apply_min_up_down_time", False)),
        "clean_pu_profiles": bool(uc.get("clean_pu_profiles", True)),
        "min_ramp_limit_threshold": float(uc.get("min_ramp_limit_threshold", 0.05)),
    }


def validate_csv_metadata(
    plants: pd.DataFrame,
    plants_csv: Path,
    disagg_config: dict | None,
    uc_config: dict,
) -> None:
    disagg_config = disagg_config or {}
    _require_columns(plants, REQUIRED_METADATA_COLUMNS, str(plants_csv))
    expected_mode = disagg_config.get("availability_mode")
    expected_fleet_mode = disagg_config.get("fleet_mode")
    expected_outage = disagg_config.get("outage_profiles_scenario")
    expected_annual = disagg_config.get("annual_availability_scenario")
    _check_csv_value(plants, "fleet_mode", expected_fleet_mode, str(plants_csv))
    _check_csv_value(plants, "availability_mode", expected_mode, str(plants_csv))
    _check_csv_value(plants, "outage_profiles_scenario", expected_outage, str(plants_csv))
    if expected_mode == "rsa_eaf_projected":
        _check_csv_value(
            plants,
            "annual_availability_scenario",
            expected_annual,
            str(plants_csv),
        )
        _check_config_target_override(plants, plants_csv, disagg_config)

    if not uc_config["enable"]:
        return
    _require_columns(plants, REQUIRED_UC_COLUMNS, str(plants_csv))
    actual_multipliers = pd.to_numeric(plants["ramp_multiplier_applied"], errors="coerce")
    if actual_multipliers.isna().any():
        raise SystemExit(f"{plants_csv} has non-numeric ramp_multiplier_applied values")
    expected_multiplier = float(uc_config["ramp_multiplier"])
    if not ((actual_multipliers - expected_multiplier).abs() <= 1e-9).all():
        actual = sorted({round(float(v), 12) for v in actual_multipliers})
        raise SystemExit(
            "Coal CSV ramp_multiplier_applied "
            f"{actual} does not match config {expected_multiplier}"
        )


def _non_coal_p_max_pu(n: pypsa.Network) -> pd.DataFrame:
    non_coal = n.generators.index[n.generators["carrier"] != "coal"]
    existing = n.generators_t.p_max_pu.columns.intersection(non_coal)
    return n.generators_t.p_max_pu.reindex(index=n.snapshots, columns=existing).copy()


def load_inputs(
    plants_csv: Path,
    eaf_csv: Path,
    bus_assignment_csv: Path,
    snapshots: pd.Index,
    disagg_config: dict | None,
    uc_config: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    plants = pd.read_csv(plants_csv)
    _require_columns(plants, REQUIRED_PLANT_COLUMNS, str(plants_csv))
    plants = plants[plants["carrier"] == "coal"].copy()
    plants["station_name"] = plants["station_name"].astype(str)
    plants["generator_name"] = plants["generator_name"].astype(str)
    plants["bus"] = plants["bus"].astype(str)
    validate_csv_metadata(plants, plants_csv, disagg_config, uc_config)

    if plants["generator_name"].duplicated().any():
        duplicates = sorted(plants.loc[plants["generator_name"].duplicated(), "generator_name"])
        raise SystemExit(f"Duplicate generator_name values in {plants_csv}: {duplicates}")
    total_p_nom = float(pd.to_numeric(plants["p_nom_mw"], errors="raise").sum())
    expected_total = float(
        plants[["station_name", "station_p_nom_mw"]]
        .drop_duplicates()["station_p_nom_mw"]
        .astype(float)
        .sum()
    )
    if abs(total_p_nom - expected_total) > P_NOM_TOLERANCE_MW:
        raise SystemExit(
            f"Coal p_nom gate failed: expected {expected_total:.1f} MW, "
            f"found {total_p_nom:.3f} MW"
        )

    eaf = pd.read_csv(eaf_csv, index_col=0, parse_dates=True)
    missing_eaf = sorted(set(plants["station_name"]).difference(eaf.columns))
    if missing_eaf:
        raise SystemExit(f"{eaf_csv} missing station EAF columns: {missing_eaf}")
    station_cols = plants["station_name"].drop_duplicates().astype(str).tolist()
    eaf = eaf.reindex(snapshots)[station_cols]
    if eaf.isna().any().any():
        first_missing = eaf.index[eaf.isna().any(axis=1)][0]
        raise SystemExit(f"{eaf_csv} does not cover all network snapshots; first missing {first_missing}")
    eaf = eaf.astype(float).clip(lower=0.0, upper=1.0)

    bus_df = pd.read_csv(bus_assignment_csv)
    _require_columns(bus_df, {"station_name", "generator_name", "bus"}, str(bus_assignment_csv))
    bus_df["station_name"] = bus_df["station_name"].astype(str)
    bus_df["generator_name"] = bus_df["generator_name"].astype(str)
    bus_df["bus"] = bus_df["bus"].astype(str)
    if bus_df["generator_name"].duplicated().any():
        duplicates = sorted(bus_df.loc[bus_df["generator_name"].duplicated(), "generator_name"])
        raise SystemExit(f"Duplicate generator_name values in {bus_assignment_csv}: {duplicates}")

    merged = plants.merge(
        bus_df[["generator_name", "station_name", "bus"]],
        on="generator_name",
        suffixes=("", "_bus_csv"),
        how="left",
    )
    if merged[["station_name_bus_csv", "bus_bus_csv"]].isna().any().any():
        missing = merged.loc[merged["bus_bus_csv"].isna(), "generator_name"].tolist()
        raise SystemExit(f"{bus_assignment_csv} missing generator assignments: {missing}")
    mismatch = merged[
        (merged["station_name"] != merged["station_name_bus_csv"]) | (merged["bus"] != merged["bus_bus_csv"])
    ]
    if not mismatch.empty:
        raise SystemExit(
            "plants_csv and bus_assignment_csv disagree:\n"
            + mismatch[["generator_name", "station_name", "station_name_bus_csv", "bus", "bus_bus_csv"]].to_string(
                index=False
            )
        )

    return plants.sort_values(["station_name", "generator_name"]).reset_index(drop=True), eaf


def _ensure_generator_timeseries(n: pypsa.Network, attr: str) -> pd.DataFrame:
    frame = getattr(n.generators_t, attr)
    if frame.empty:
        frame = pd.DataFrame(index=n.snapshots)
    else:
        frame = frame.reindex(index=n.snapshots)
    setattr(n.generators_t, attr, frame)
    return frame


def _numeric(row: pd.Series, column: str) -> float:
    value = pd.to_numeric(pd.Series([row[column]]), errors="raise").iloc[0]
    return float(value)


def attach_za_coal_plants(
    n: pypsa.Network,
    plants: pd.DataFrame,
    eaf: pd.DataFrame,
    uc_config: dict,
) -> None:
    existing_coal = n.generators[n.generators["carrier"] == "coal"].index
    if existing_coal.empty:
        raise SystemExit("No coal generators found in input network; refusing to disaggregate")
    logger.info("Removing %d aggregated coal generator rows", len(existing_coal))
    n.mremove("Generator", existing_coal)

    uc_enabled = bool(uc_config["enable"])
    missing_buses: list[tuple[str, str]] = []
    for _, row in plants.iterrows():
        name = str(row["generator_name"])
        station = str(row["station_name"])
        bus = str(row["bus"])
        if bus not in n.buses.index:
            missing_buses.append((name, bus))
            continue
        heat_rate = float(row["avg_heat_rate_gj_per_mwh"])
        if heat_rate <= 0:
            raise SystemExit(f"Non-positive heat rate for {name}: {heat_rate}")
        n.add(
            "Generator",
            name,
            bus=bus,
            carrier="coal",
            p_nom=float(row["p_nom_mw"]),
            marginal_cost=float(row["marginal_cost_eur_per_mwh"]),
            efficiency=3.6 / heat_rate,
            p_min_pu=0.0,
            committable=uc_enabled,
        )
        n.generators.at[name, "station_name"] = station
        n.generators.at[name, "za_generator_name"] = name
        n.generators.at[name, "za_bus_assignment_source"] = row.get("bus_assignment_source", "")
        n.generators.at[name, "za_split_capacity_share"] = float(row.get("split_capacity_share", 1.0))
        if uc_enabled:
            mean_p_max_pu = float(eaf[station].mean())
            ramp_up = _numeric(row, "ramp_limit_up_per_h") * mean_p_max_pu
            ramp_down = _numeric(row, "ramp_limit_down_per_h") * mean_p_max_pu
            if uc_config["clean_pu_profiles"]:
                threshold = float(uc_config["min_ramp_limit_threshold"])
                ramp_up = max(ramp_up, threshold)
                ramp_down = max(ramp_down, threshold)
            n.generators.at[name, "ramp_limit_up"] = ramp_up
            n.generators.at[name, "ramp_limit_down"] = ramp_down
            n.generators.at[name, "ramp_limit_start_up"] = _numeric(
                row, "ramp_limit_start_up_per_h"
            )
            n.generators.at[name, "ramp_limit_shut_down"] = _numeric(
                row, "ramp_limit_shut_down_per_h"
            )
            n.generators.at[name, "start_up_cost"] = _numeric(row, "start_up_cost_eur")
            n.generators.at[name, "shut_down_cost"] = _numeric(row, "shut_down_cost_eur")
            n.generators.at[name, "min_up_time"] = int(_numeric(row, "min_up_time_h"))
            n.generators.at[name, "min_down_time"] = int(_numeric(row, "min_down_time_h"))
    if missing_buses:
        raise SystemExit(f"Bus IDs missing from network: {missing_buses}")

    if n.generators_t.p_max_pu.empty:
        n.generators_t.p_max_pu = pd.DataFrame(index=n.snapshots)
    else:
        n.generators_t.p_max_pu = n.generators_t.p_max_pu.reindex(index=n.snapshots)

    for _, row in plants.iterrows():
        generator = str(row["generator_name"])
        station = str(row["station_name"])
        n.generators_t.p_max_pu.loc[:, generator] = eaf[station].to_numpy(dtype=float)

    if uc_enabled:
        apply_coal_uc_profiles(n, plants, uc_config)


def apply_coal_uc_profiles(
    n: pypsa.Network,
    plants: pd.DataFrame,
    uc_config: dict,
) -> None:
    generators = plants["generator_name"].astype(str).tolist()
    pmax = n.generators_t.p_max_pu.reindex(index=n.snapshots, columns=generators).astype(float)
    if pmax.isna().any().any():
        missing = sorted(pmax.columns[pmax.isna().any()].tolist())
        raise SystemExit(f"Coal UC p_max_pu contains NaN values for generators: {missing}")
    if uc_config["clean_pu_profiles"]:
        pmax = pmax.clip(lower=0.0, upper=1.0)
        pmax = pmax.mask(pmax < 0.01, 0.0)
        for generator in generators:
            n.generators_t.p_max_pu.loc[:, generator] = pmax[generator].to_numpy(dtype=float)

    p_min_base = float(uc_config["p_min_pu_base"])
    pmin = pmax * p_min_base
    if uc_config["clean_pu_profiles"]:
        pmin = pmin.mask(pmin < 0.01, 0.0)
        errors = pmin > pmax
        if errors.any().any():
            pmin = pmin.where(~errors, pmax)
    elif (pmin > pmax).any().any():
        bad = sorted(pmin.columns[(pmin > pmax).any()].tolist())
        raise SystemExit(f"Coal UC p_min_pu exceeds p_max_pu for generators: {bad}")

    pmin_frame = _ensure_generator_timeseries(n, "p_min_pu")
    for generator in generators:
        pmin_frame.loc[:, generator] = pmin[generator].to_numpy(dtype=float)
    n.generators_t.p_min_pu = pmin_frame


def build_audit_rows(
    plants: pd.DataFrame,
    eaf: pd.DataFrame,
    source_file: Path,
    uc_config: dict,
) -> pd.DataFrame:
    total_p_nom = float(plants["p_nom_mw"].sum())
    station_count = int(plants["station_name"].nunique())
    generator_count = int(len(plants))
    weighted_availability = 0.0
    for _, row in plants.iterrows():
        weighted_availability += float(row["p_nom_mw"]) * float(eaf[str(row["station_name"])].mean())
    weighted_availability /= total_p_nom

    rows = []
    for _, row in plants.iterrows():
        station = str(row["station_name"])
        generator = str(row["generator_name"])
        availability_mode = str(row.get("availability_mode", ""))
        uc_enabled = bool(uc_config["enable"])
        mean_p_max_pu = float(eaf[station].mean())
        rows.append(
            {
                "record_type": "generator",
                "Name": generator,
                "station_key": station,
                "station_name": station,
                "generator_name": generator,
                "bus": str(row["bus"]),
                "Capacity": float(row["p_nom_mw"]),
                "matched": True,
                "fallback_used": bool(row.get("fallback_used", False)),
                "gen_name": generator,
                "mean_p_max_pu": float(eaf[station].mean()),
                "p_nom_mw": float(row["p_nom_mw"]),
                "station_p_nom_mw": float(row["station_p_nom_mw"]),
                "split_capacity_share": float(row.get("split_capacity_share", 1.0)),
                "station_generator_count": int(row.get("station_generator_count", 1)),
                "bus_assignment_source": str(row.get("bus_assignment_source", "")),
                "custom_powerplant_rows": str(row.get("custom_powerplant_rows", "")),
                "ambiguous_station_mapping": bool(row.get("ambiguous_station_mapping", False)),
                "marginal_cost_eur_per_mwh": float(row["marginal_cost_eur_per_mwh"]),
                "availability_mode": availability_mode,
                "outage_profiles_scenario": str(row.get("outage_profiles_scenario", "")),
                "annual_availability_scenario": str(row.get("annual_availability_scenario", "")),
                "annual_availability_target": row.get("annual_availability_target", ""),
                "raw_base_mean": row.get("raw_base_mean", ""),
                "planned_mean": row.get("planned_mean", ""),
                "unplanned_mean": row.get("unplanned_mean", ""),
                "unplanned_scale": row.get("unplanned_scale", ""),
                "uc_enabled": uc_enabled,
                "p_min_pu_base": uc_config["p_min_pu_base"] if uc_enabled else "",
                "ramp_limit_up": (
                    float(row["ramp_limit_up_per_h"]) * mean_p_max_pu if uc_enabled else ""
                ),
                "ramp_limit_down": (
                    float(row["ramp_limit_down_per_h"]) * mean_p_max_pu if uc_enabled else ""
                ),
                "ramp_limit_start_up": row.get("ramp_limit_start_up_per_h", ""),
                "ramp_limit_shut_down": row.get("ramp_limit_shut_down_per_h", ""),
                "start_up_cost": row.get("start_up_cost_eur", ""),
                "shut_down_cost": row.get("shut_down_cost_eur", ""),
                "min_up_time": row.get("min_up_time_h", ""),
                "min_down_time": row.get("min_down_time_h", ""),
                "apply_min_up_down_time": (
                    uc_config["apply_min_up_down_time"] if uc_enabled else ""
                ),
            }
        )

    audit = pd.DataFrame(rows)
    metadata = {
        "source_workbook": str(source_file),
        "sheet": "fixed_technologies+fuel_prices+outage_profiles+annual_availability",
        "scenario": str(plants["fleet_mode"].iloc[0]) + "+BASE_PMR1b",
        "outage_types": "planned+unplanned",
        "station_to_bus_mapping_rule": "custom_powerplants_bus_mapping_selected_fleet_capacity",
        "any_fallback_used": bool(audit["fallback_used"].any()),
        "unmatched_mw": 0.0,
        "coal_stations_overlaid": station_count,
        "coal_generators_overlaid": generator_count,
        "coal_p_nom_mw": total_p_nom,
        "n_snapshots": int(len(eaf)),
        "mean_fleet_availability": weighted_availability,
        "non_coal_p_max_pu_changed": False,
        "disaggregation_active": True,
        "uc_enabled": bool(uc_config["enable"]),
    }
    for key, value in metadata.items():
        audit[key] = value
    ordered = list(metadata.keys()) + [c for c in audit.columns if c not in metadata]
    return audit[ordered]


def main(
    network_in: Path,
    network_out: Path,
    plants_csv: Path,
    eaf_csv: Path,
    bus_assignment_csv: Path,
    audit_out: Path,
    backup: Path | None,
    disagg_config: dict | None = None,
) -> int:
    uc_config = _normalise_uc_config(disagg_config)
    if backup is not None:
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(network_in, backup)
        logger.info("Backed up %s -> %s", network_in, backup)

    logger.info("Loading network %s", network_in)
    n = pypsa.Network(str(network_in))
    non_coal_before = _non_coal_p_max_pu(n)

    plants, eaf = load_inputs(
        plants_csv,
        eaf_csv,
        bus_assignment_csv,
        n.snapshots,
        disagg_config,
        uc_config,
    )
    attach_za_coal_plants(n, plants, eaf, uc_config)

    non_coal_after = _non_coal_p_max_pu(n).reindex(columns=non_coal_before.columns)
    if not non_coal_before.equals(non_coal_after):
        raise SystemExit("GATE FAIL: non-coal generators_t.p_max_pu changed during 13g")

    coal = n.generators[n.generators["carrier"] == "coal"]
    expected_stations = int(plants["station_name"].nunique())
    expected_generators = int(len(plants))
    expected_total = float(
        plants[["station_name", "station_p_nom_mw"]]
        .drop_duplicates()["station_p_nom_mw"]
        .astype(float)
        .sum()
    )
    if coal["station_name"].nunique() != expected_stations:
        raise SystemExit(
            f"GATE FAIL: coal station count is not {expected_stations} after 13m"
        )
    if len(coal) != expected_generators:
        raise SystemExit(
            f"GATE FAIL: coal generator row count is not {expected_generators} after 13m"
        )
    if abs(float(coal["p_nom"].sum()) - expected_total) > P_NOM_TOLERANCE_MW:
        raise SystemExit(
            f"GATE FAIL: coal p_nom is not {expected_total:.1f} MW after 13m"
        )
    coal_committable = coal["committable"].fillna(False).astype(bool)
    if uc_config["enable"] and not bool(coal_committable.all()):
        raise SystemExit("GATE FAIL: Module 13h UC requires all coal rows committable")
    if not uc_config["enable"] and bool(coal_committable.any()):
        raise SystemExit("GATE FAIL: Module 13g must not enable coal UC")
    if uc_config["enable"]:
        non_coal = n.generators[n.generators["carrier"] != "coal"]
        if bool(non_coal["committable"].fillna(False).any()):
            offenders = sorted(non_coal.index[non_coal["committable"].fillna(False)].tolist())
            raise SystemExit(f"GATE FAIL: non-coal generators are committable: {offenders}")
        if not (coal["p_min_pu"].fillna(0.0).astype(float) == 0.0).all():
            raise SystemExit("GATE FAIL: static coal p_min_pu must be zero for Module 13h UC")
        missing_pmin = sorted(set(coal.index).difference(n.generators_t.p_min_pu.columns))
        if missing_pmin:
            raise SystemExit(f"GATE FAIL: missing p_min_pu columns for coal UC: {missing_pmin}")
        pmax = n.generators_t.p_max_pu.loc[:, coal.index].astype(float)
        pmin = n.generators_t.p_min_pu.loc[:, coal.index].astype(float)
        if (pmin > pmax + 1e-9).any().any():
            bad = sorted(pmin.columns[(pmin > pmax + 1e-9).any()].tolist())
            raise SystemExit(f"GATE FAIL: coal p_min_pu exceeds p_max_pu for: {bad}")
    missing_pmax = sorted(set(coal.index).difference(n.generators_t.p_max_pu.columns))
    if missing_pmax:
        raise SystemExit(f"GATE FAIL: missing p_max_pu columns for coal generators: {missing_pmax}")

    network_out.parent.mkdir(parents=True, exist_ok=True)
    n.export_to_netcdf(str(network_out))
    logger.info("Saved 13g EAF network to %s", network_out)

    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit_rows(plants, eaf, eaf_csv, uc_config)
    audit.to_csv(audit_out, index=False)
    logger.info("Wrote 13g coal audit (%d rows) to %s", len(audit), audit_out)
    return 0


def _main_from_snakemake() -> int:
    sm = globals()["snakemake"]
    log_path = Path(sm.log[0])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(str(log_path), mode="w")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.getLogger().addHandler(handler)
    return main(
        network_in=Path(sm.input.network_in),
        network_out=Path(sm.output.network_out),
        plants_csv=Path(sm.input.plants_csv),
        eaf_csv=Path(sm.input.eaf_csv),
        bus_assignment_csv=Path(sm.input.buses_csv),
        audit_out=Path(sm.output.audit),
        backup=Path(sm.output.backup),
        disagg_config={
            **(sm.config.get("za_coal_disaggregation", {}) or {}),
            "fleet_mode": resolved_config(sm.config)["effective_mode"],
        },
    )


def _main_from_cli() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--network-in", required=True, type=Path)
    parser.add_argument("--network-out", required=True, type=Path)
    parser.add_argument("--plants-csv", required=True, type=Path)
    parser.add_argument("--eaf-csv", required=True, type=Path)
    parser.add_argument("--bus-assignment-csv", required=True, type=Path)
    parser.add_argument("--audit", default=Path("data/za_audit/za_coal_eaf_audit.csv"), type=Path)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--availability-mode", default="raw_base")
    parser.add_argument("--outage-profiles-scenario", default="BASE")
    parser.add_argument("--annual-availability-scenario", default="EAF_48")
    parser.add_argument("--uc-enable", action="store_true")
    parser.add_argument("--uc-p-min-pu-base", default=0.7, type=float)
    parser.add_argument("--uc-ramp-multiplier", default=1.5, type=float)
    parser.add_argument("--uc-apply-min-up-down-time", action="store_true")
    parser.add_argument(
        "--uc-clean-pu-profiles",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--uc-min-ramp-limit-threshold", default=0.05, type=float)
    args = parser.parse_args()
    disagg_config = {
        "availability_mode": args.availability_mode,
        "outage_profiles_scenario": args.outage_profiles_scenario,
        "annual_availability_scenario": args.annual_availability_scenario,
        "uc": {
            "enable": args.uc_enable,
            "msl_mode": "scale_by_p_max_pu",
            "p_min_pu_base": args.uc_p_min_pu_base,
            "ramp_multiplier": args.uc_ramp_multiplier,
            "apply_min_up_down_time": args.uc_apply_min_up_down_time,
            "clean_pu_profiles": args.uc_clean_pu_profiles,
            "min_ramp_limit_threshold": args.uc_min_ramp_limit_threshold,
        },
    }
    return main(
        network_in=args.network_in,
        network_out=args.network_out,
        plants_csv=args.plants_csv,
        eaf_csv=args.eaf_csv,
        bus_assignment_csv=args.bus_assignment_csv,
        audit_out=args.audit,
        backup=args.backup,
        disagg_config=disagg_config,
    )


if __name__ == "__main__":
    if "snakemake" in globals():
        sys.exit(_main_from_snakemake())
    sys.exit(_main_from_cli())
