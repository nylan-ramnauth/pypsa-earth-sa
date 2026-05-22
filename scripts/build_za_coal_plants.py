# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build Module 13g coal-disaggregation inputs from PyPSA-RSA workbooks.

Capacity is sourced from PyPSA-RSA ``fixed_technologies.xlsx`` scenario
``VAR_HR``. ``custom_powerplants.csv`` is used only for bus mapping and, when a
station spans multiple buses, split weights.
"""

import argparse
import re
from pathlib import Path

import pandas as pd
import yaml

from za_fleet.fleet_calibration import (
    CURRENT_RSA_VAR_HR_MW,
    OFFICIAL_ESKOM_2023_NOMINAL_MW,
    resolved_config,
    selected_coal_capacities,
)


COAL_STATIONS = [
    "Arnot",
    "Camden",
    "Duvha",
    "Grootvlei",
    "Hendrina",
    "Kelvin",
    "Kendal",
    "Kriel",
    "Kusile",
    "Lethabo",
    "Majuba",
    "Matimba",
    "Matla",
    "Medupi",
    "Tutuka",
]

AVAILABILITY_MODES = {"raw_base", "rsa_eaf_projected"}
FUEL_PRICE_YEAR = 2025.0
EUR_ZAR = 20.0
OUTAGE_TYPES = ("planned", "unplanned")
DEFAULT_YEAR = 2023
DEFAULT_RAMP_MULTIPLIER = 1.5
COAL_TARGET_OVERRIDE_SOURCE = (
    "config:za_coal_disaggregation.annual_availability_target_override.coal"
)


def _require_columns(df: pd.DataFrame, columns: set, source: str) -> None:
    missing = columns.difference(df.columns)
    if missing:
        raise SystemExit(f"{source} missing required columns: {sorted(missing)}")


def station_key(name: str) -> str:
    """Normalize custom-powerplant split names such as ``Hendrina_2``."""
    return re.sub(r"_\d+$", "", str(name).strip())


def load_var_hr_coal(fixed_technologies: Path) -> pd.DataFrame:
    df = pd.read_excel(fixed_technologies, sheet_name="conventional")
    required = {
        "scenario",
        "station_name",
        "carrier",
        "capacity (MW)",
        "avg_heat_rate (GJ/MWh)",
        "fuel_price (R/GJ)",
        "variable_om_cost (R/MWh)",
        "max_ramp_up (%/h)",
        "max_ramp_down (%/h)",
        "max_ramp_start_up (%/h)",
        "max_ramp_shut_down (%/h)",
        "min_up_time (h)",
        "min_down_time (h)",
        "start_up_cost (R)",
        "shut_down_cost (R)",
        "gps_lat",
        "gps_lon",
    }
    _require_columns(df, required, str(fixed_technologies))

    coal = df[(df["scenario"] == "VAR_HR") & (df["carrier"] == "coal")].copy()
    coal = coal[coal["station_name"].isin(COAL_STATIONS)].copy()
    if set(coal["station_name"]) != set(COAL_STATIONS):
        missing = sorted(set(COAL_STATIONS).difference(coal["station_name"]))
        extra = sorted(set(coal["station_name"]).difference(COAL_STATIONS))
        raise SystemExit(f"Unexpected VAR_HR coal station set. Missing={missing}, extra={extra}")
    return coal.sort_values("station_name").reset_index(drop=True)


def select_coal_fleet(
    var_hr_coal: pd.DataFrame,
    *,
    mode: str,
    include_kelvin: bool,
) -> pd.DataFrame:
    """Return coal station metadata with p_nom set by the selected fleet mode."""
    caps = selected_coal_capacities(mode, include_kelvin=include_kelvin)
    coal = var_hr_coal[var_hr_coal["station_name"].isin(caps)].copy()
    missing = sorted(set(caps).difference(coal["station_name"]))
    if missing:
        raise SystemExit(f"Selected coal fleet mode {mode} missing metadata for {missing}")
    coal["capacity (MW)"] = coal["station_name"].map(caps).astype(float)
    coal["fleet_mode"] = mode
    coal["official_eskom_2023_nominal_mw"] = coal["station_name"].map(
        OFFICIAL_ESKOM_2023_NOMINAL_MW
    ).fillna(0.0)
    coal["rsa_var_hr_mw"] = coal["station_name"].map(CURRENT_RSA_VAR_HR_MW).fillna(0.0)
    coal["source_class"] = (
        "official_eskom_2023_nominal"
        if mode == "eskom_nominal_2023"
        else "pypsa_rsa_var_hr"
    )
    coal["source_evidence"] = (
        "Eskom Integrated Report 2023 plant information"
        if mode == "eskom_nominal_2023"
        else "pypsa-rsa Benchmark_2023 fixed_technologies.xlsx VAR_HR"
    )
    return coal.sort_values("station_name").reset_index(drop=True)


def load_fuel_prices(fuel_prices: Path) -> dict[str, float]:
    df = pd.read_excel(fuel_prices, sheet_name="fixed_generators")
    required = {"scenario", "station_name", "parameter", FUEL_PRICE_YEAR}
    _require_columns(df, required, str(fuel_prices))

    rows = df[
        (df["scenario"] == "BASE_PMR1b")
        & (df["station_name"].isin(["low_group", "med_group", "high_group"]))
        & (df["parameter"] == "fuel_price (R/GJ)")
    ].copy()
    if len(rows) != 3:
        raise SystemExit(f"Expected 3 BASE_PMR1b coal fuel-price rows, found {len(rows)}")
    rows[FUEL_PRICE_YEAR] = pd.to_numeric(rows[FUEL_PRICE_YEAR], errors="coerce")
    if rows[FUEL_PRICE_YEAR].isna().any():
        raise SystemExit("BASE_PMR1b fuel-price rows contain NaN values for 2025")
    return rows.set_index("station_name")[FUEL_PRICE_YEAR].astype(float).to_dict()


def build_station_specs(
    coal: pd.DataFrame,
    fuel_prices: dict[str, float],
    ramp_multiplier: float,
) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "station_name": coal["station_name"].astype(str),
            "carrier": "coal",
            "station_p_nom_mw": pd.to_numeric(coal["capacity (MW)"], errors="raise"),
            "fleet_mode": coal.get("fleet_mode", "rsa_var_hr_41p419"),
            "official_eskom_2023_nominal_mw": pd.to_numeric(
                coal.get("official_eskom_2023_nominal_mw", pd.Series(0.0, index=coal.index)),
                errors="coerce",
            ).fillna(0.0),
            "rsa_var_hr_mw": pd.to_numeric(
                coal.get("rsa_var_hr_mw", pd.Series(0.0, index=coal.index)),
                errors="coerce",
            ).fillna(0.0),
            "source_class": coal.get("source_class", ""),
            "source_evidence": coal.get("source_evidence", ""),
            "gps_lat": pd.to_numeric(coal["gps_lat"], errors="raise"),
            "gps_lon": pd.to_numeric(coal["gps_lon"], errors="raise"),
            "fuel_group": coal["fuel_price (R/GJ)"].astype(str),
            "avg_heat_rate_gj_per_mwh": pd.to_numeric(
                coal["avg_heat_rate (GJ/MWh)"], errors="raise"
            ),
            "variable_om_r_per_mwh": pd.to_numeric(
                coal["variable_om_cost (R/MWh)"], errors="raise"
            ),
            "p_min_pu": 0.7,
            "ramp_limit_up_per_h": pd.to_numeric(
                coal["max_ramp_up (%/h)"], errors="raise"
            )
            * ramp_multiplier,
            "ramp_limit_down_per_h": pd.to_numeric(
                coal["max_ramp_down (%/h)"], errors="raise"
            )
            * ramp_multiplier,
            "ramp_limit_start_up_per_h": pd.to_numeric(
                coal["max_ramp_start_up (%/h)"], errors="raise"
            ),
            "ramp_limit_shut_down_per_h": pd.to_numeric(
                coal["max_ramp_shut_down (%/h)"], errors="raise"
            ),
            "min_up_time_h": pd.to_numeric(coal["min_up_time (h)"], errors="raise").astype(int),
            "min_down_time_h": pd.to_numeric(
                coal["min_down_time (h)"], errors="raise"
            ).astype(int),
            "start_up_cost_eur": pd.to_numeric(
                coal["start_up_cost (R)"], errors="raise"
            )
            / EUR_ZAR,
            "shut_down_cost_eur": pd.to_numeric(
                coal["shut_down_cost (R)"], errors="raise"
            )
            / EUR_ZAR,
        }
    )
    out["ramp_multiplier_applied"] = float(ramp_multiplier)
    out["fuel_price_r_per_gj"] = out["fuel_group"].map(fuel_prices)
    if out["fuel_price_r_per_gj"].isna().any():
        bad = out.loc[out["fuel_price_r_per_gj"].isna(), ["station_name", "fuel_group"]]
        raise SystemExit(f"Missing fuel-price group values:\n{bad.to_string(index=False)}")
    out["marginal_cost_r_per_mwh"] = (
        out["avg_heat_rate_gj_per_mwh"] * out["fuel_price_r_per_gj"]
        + out["variable_om_r_per_mwh"]
    )
    out["marginal_cost_eur_per_mwh"] = out["marginal_cost_r_per_mwh"] / EUR_ZAR
    return out.sort_values("station_name").reset_index(drop=True)


def load_custom_coal_bus_rows(custom_powerplants: Path) -> pd.DataFrame:
    df = pd.read_csv(custom_powerplants)
    required = {"Name", "Fueltype", "Capacity", "bus"}
    _require_columns(df, required, str(custom_powerplants))

    coal = df[df["Fueltype"] == "Hard Coal"][["Name", "Capacity", "bus"]].copy()
    coal["station_name"] = coal["Name"].map(station_key)
    coal["custom_capacity_mw"] = pd.to_numeric(coal["Capacity"], errors="coerce")
    coal = coal.drop(columns=["Capacity"])
    if coal["custom_capacity_mw"].isna().any():
        bad = coal.loc[coal["custom_capacity_mw"].isna(), "Name"].tolist()
        raise SystemExit(f"{custom_powerplants} has non-numeric Hard Coal capacities: {bad}")
    if (coal["custom_capacity_mw"] <= 0).any():
        bad = coal.loc[coal["custom_capacity_mw"] <= 0, ["Name", "custom_capacity_mw"]]
        raise SystemExit(f"{custom_powerplants} has non-positive Hard Coal split weights:\n{bad}")
    return coal[["Name", "station_name", "bus", "custom_capacity_mw"]].copy()


def build_generator_rows(
    station_specs: pd.DataFrame,
    custom_bus_rows: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create generator rows using VAR_HR capacity and custom bus split shares."""
    generator_rows = []
    bus_rows = []
    station_cols = station_specs.set_index("station_name")

    for station, spec in station_cols.iterrows():
        custom = custom_bus_rows[custom_bus_rows["station_name"] == station].copy()
        if custom.empty:
            raise SystemExit(f"No Hard Coal custom_powerplants bus mapping found for {station}")

        by_bus = (
            custom.groupby("bus", as_index=False)
            .agg(
                custom_capacity_mw=("custom_capacity_mw", "sum"),
                source_rows=("Name", lambda s: "|".join(map(str, s))),
            )
            .sort_values("bus")
            .reset_index(drop=True)
        )
        custom_total = float(by_bus["custom_capacity_mw"].sum())
        if custom_total <= 0:
            raise SystemExit(f"Custom split weights for {station} sum to zero")

        station_p_nom = float(spec["station_p_nom_mw"])
        split_count = len(by_bus)
        for split_idx, row in by_bus.iterrows():
            split_share = float(row["custom_capacity_mw"]) / custom_total
            if split_count == 1:
                generator_name = station
                bus_source = "custom_powerplants_unique_bus"
            else:
                source_names = str(row["source_rows"]).split("|")
                generator_name = source_names[0] if len(source_names) == 1 else f"{station}_{split_idx + 1}"
                bus_source = "custom_powerplants_split_weighted"

            out = spec.to_dict()
            out.update(
                {
                    "station_name": station,
                    "generator_name": generator_name,
                    "bus": str(row["bus"]),
                    "p_nom_mw": station_p_nom * split_share,
                    "station_p_nom_mw": station_p_nom,
                    "custom_capacity_mw": float(row["custom_capacity_mw"]),
                    "custom_station_capacity_mw": custom_total,
                    "split_capacity_share": split_share,
                    "station_generator_count": split_count,
                    "bus_assignment_source": bus_source,
                    "custom_powerplant_rows": str(row["source_rows"]),
                    "fallback_used": False,
                    "ambiguous_station_mapping": False,
                }
            )
            generator_rows.append(out)
            bus_rows.append(
                {
                    "station_name": station,
                    "generator_name": generator_name,
                    "bus": str(row["bus"]),
                    "custom_capacity_mw": float(row["custom_capacity_mw"]),
                    "custom_station_capacity_mw": custom_total,
                    "var_hr_station_p_nom_mw": station_p_nom,
                    "p_nom_mw": station_p_nom * split_share,
                    "split_capacity_share": split_share,
                    "station_generator_count": split_count,
                    "bus_assignment_source": bus_source,
                    "custom_powerplant_rows": str(row["source_rows"]),
                    "fallback_used": False,
                    "ambiguous_station_mapping": False,
                }
            )

    plants = pd.DataFrame(generator_rows).sort_values(["station_name", "generator_name"])
    buses = pd.DataFrame(bus_rows).sort_values(["station_name", "generator_name"])
    if plants["generator_name"].duplicated().any():
        dupes = plants.loc[plants["generator_name"].duplicated(), "generator_name"].tolist()
        raise SystemExit(f"Duplicate generator_name values after bus split: {dupes}")
    return plants.reset_index(drop=True), buses.reset_index(drop=True)


def load_weekly_outage_components(
    plant_availability: Path,
    outage_profiles_scenario: str,
    stations: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    outage = pd.read_excel(plant_availability, sheet_name="outage_profiles", header=1)
    required = {"scenario", "type", "week"}
    _require_columns(outage, required, f"{plant_availability}:outage_profiles")

    outage = outage[
        (outage["scenario"] == outage_profiles_scenario) & (outage["type"].isin(OUTAGE_TYPES))
    ].copy()
    outage["week"] = pd.to_numeric(outage["week"], errors="coerce")
    outage = outage[outage["week"].notna()].copy()
    outage["week"] = outage["week"].astype(int)
    outage = outage[outage["week"].between(1, 53)].copy()
    if outage.empty:
        raise SystemExit(
            f"No outage rows found for scenario={outage_profiles_scenario!r} in {plant_availability}"
        )

    rows = []
    components: dict[str, pd.DataFrame] = {}
    for outage_type in OUTAGE_TYPES:
        subset = outage[outage["type"] == outage_type].set_index("week")
        component = pd.DataFrame(index=sorted(subset.index.unique()))
        for station in stations:
            if station in subset.columns:
                source_col = station
                source_type = "plant_specific"
            elif "coal" in subset.columns:
                source_col = "coal"
                source_type = "coal_group_fallback"
            else:
                source_col = None
                source_type = "missing"
            if source_col is None:
                raise SystemExit(f"No {outage_type} outage profile column found for {station}")
            values = pd.to_numeric(subset[source_col], errors="coerce")
            if values.isna().any():
                raise SystemExit(f"NaN {outage_type} outage values for {station} from {source_col}")
            component[station] = values.reindex(component.index).astype(float)
            rows.append(
                {
                    "station_name": station,
                    "outage_type": outage_type,
                    "outage_profile_column": source_col,
                    "outage_profile_source": source_type,
                }
            )
        components[outage_type] = component

    for outage_type, component in components.items():
        missing_weeks = sorted(set(range(1, 53)).difference(component.index))
        if missing_weeks:
            raise SystemExit(f"Missing {outage_type} outage weeks: {missing_weeks}")
    return components["planned"], components["unplanned"], pd.DataFrame(rows)


def load_annual_availability_targets(
    plant_availability: Path,
    annual_availability_scenario: str,
    stations: list[str],
    year: int,
) -> tuple[pd.Series, pd.DataFrame]:
    annual = pd.read_excel(plant_availability, sheet_name="annual_availability")
    required = {"scenario", "parameter", year}
    _require_columns(annual, required, f"{plant_availability}:annual_availability")
    annual = annual[annual["scenario"] == annual_availability_scenario].copy()
    if annual.empty:
        raise SystemExit(f"No annual availability rows for {annual_availability_scenario}")
    annual[year] = pd.to_numeric(annual[year], errors="coerce")

    targets = {}
    rows = []
    for station in stations:
        candidates = [f"{station}_EAF", station, "coal_EAF", "coal"]
        match = annual[annual["parameter"].isin(candidates)].copy()
        if match.empty:
            raise SystemExit(f"No annual EAF target found for {station} in {annual_availability_scenario}")
        row = match.iloc[0]
        target = float(row[year])
        if not 0 <= target <= 1:
            raise SystemExit(f"Annual EAF target outside [0, 1] for {station}: {target}")
        targets[station] = target
        rows.append(
            {
                "station_name": station,
                "annual_availability_parameter": row["parameter"],
                "annual_availability_source": (
                    "plant_specific" if str(row["parameter"]) == f"{station}_EAF" else "fallback"
                ),
                "annual_availability_target": target,
            }
        )
    return pd.Series(targets, name="annual_availability_target"), pd.DataFrame(rows)


def normalise_annual_target_override(
    override: dict | None,
) -> dict[str, float]:
    if not override:
        return {}
    out = {}
    for carrier, value in override.items():
        carrier_key = str(carrier).strip().lower()
        target = float(value)
        if not 0 <= target <= 1:
            raise SystemExit(
                f"annual_availability_target_override.{carrier_key} outside [0, 1]: {target}"
            )
        out[carrier_key] = target
    unsupported = sorted(set(out).difference({"coal"}))
    if unsupported:
        raise SystemExit(
            "annual_availability_target_override currently supports active Eskom coal only; "
            f"unsupported carriers: {unsupported}"
        )
    return out


def expand_weekly_to_snapshots(weekly: pd.DataFrame, snapshots: pd.DatetimeIndex) -> pd.DataFrame:
    weeks = pd.Series(snapshots.isocalendar().week.to_numpy(dtype=int), index=snapshots)
    if 53 in set(weeks.unique()) and 53 not in set(weekly.index) and 52 in set(weekly.index):
        weeks = weeks.mask(weeks == 53, 52)
    missing = sorted(set(weeks.unique()).difference(set(weekly.index)))
    if missing:
        raise SystemExit(f"Snapshot ISO weeks missing from weekly availability table: {missing}")
    hourly = weekly.reindex(weeks.to_numpy()).copy()
    hourly.index = snapshots
    return hourly


def build_hourly_availability(
    plant_availability: Path,
    stations: list[str],
    year: int,
    availability_mode: str,
    outage_profiles_scenario: str,
    annual_availability_scenario: str,
    annual_availability_target_override: dict | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if availability_mode not in AVAILABILITY_MODES:
        raise SystemExit(f"Unknown availability mode {availability_mode!r}")
    target_override = normalise_annual_target_override(annual_availability_target_override)

    planned_weekly, unplanned_weekly, outage_meta = load_weekly_outage_components(
        plant_availability, outage_profiles_scenario, stations
    )
    snapshots = pd.date_range(
        f"{year}-01-01 00:00",
        f"{year + 1}-01-01 00:00",
        freq="h",
        inclusive="left",
    )
    planned = expand_weekly_to_snapshots(planned_weekly, snapshots)
    unplanned = expand_weekly_to_snapshots(unplanned_weekly, snapshots)
    raw = (1.0 - planned - unplanned).clip(lower=0.0, upper=1.0)

    annual_meta = pd.DataFrame({"station_name": stations})
    targets = pd.Series(index=stations, dtype=float)
    unplanned_scales = pd.Series(1.0, index=stations, dtype=float)
    adjusted_unplanned = unplanned.copy()
    if availability_mode == "rsa_eaf_projected":
        targets, annual_meta = load_annual_availability_targets(
            plant_availability, annual_availability_scenario, stations, year
        )
        annual_meta["annual_availability_workbook_target"] = annual_meta[
            "annual_availability_target"
        ]
        annual_meta["annual_availability_target_source"] = (
            "workbook:" + annual_meta["annual_availability_source"].astype(str)
        )
        annual_meta["annual_availability_target_override_carrier"] = ""
        annual_meta["annual_availability_target_override_value"] = pd.NA
        if "coal" in target_override:
            coal_target = float(target_override["coal"])
            targets.loc[:] = coal_target
            annual_meta["annual_availability_target"] = coal_target
            annual_meta["annual_availability_target_source"] = COAL_TARGET_OVERRIDE_SOURCE
            annual_meta["annual_availability_target_override_carrier"] = "coal"
            annual_meta["annual_availability_target_override_value"] = coal_target
        for station in stations:
            planned_mean = float(planned.loc[str(year), station].mean())
            current_unplanned = float(unplanned.loc[str(year), station].mean())
            target_unplanned = max(0.0, 1.0 - planned_mean - float(targets.loc[station]))
            if current_unplanned > 0:
                scale = target_unplanned / current_unplanned
                adjusted_unplanned.loc[str(year), station] = unplanned.loc[str(year), station] * scale
            else:
                scale = 0.0
                adjusted_unplanned.loc[str(year), station] = target_unplanned
            unplanned_scales.loc[station] = scale
        hourly = (1.0 - planned - adjusted_unplanned).clip(lower=0.0, upper=1.0)
    else:
        hourly = raw
        annual_meta["annual_availability_parameter"] = ""
        annual_meta["annual_availability_source"] = "not_used_for_raw_base"
        annual_meta["annual_availability_target"] = pd.NA
        annual_meta["annual_availability_workbook_target"] = pd.NA
        annual_meta["annual_availability_target_source"] = "not_used_for_raw_base"
        annual_meta["annual_availability_target_override_carrier"] = ""
        annual_meta["annual_availability_target_override_value"] = pd.NA

    meta = pd.DataFrame({"station_name": stations})
    meta["availability_mode"] = availability_mode
    meta["outage_profiles_scenario"] = outage_profiles_scenario
    meta["annual_availability_scenario"] = (
        annual_availability_scenario if availability_mode == "rsa_eaf_projected" else ""
    )
    meta["raw_base_mean"] = [float(raw[s].mean()) for s in stations]
    meta["planned_mean"] = [float(planned[s].mean()) for s in stations]
    meta["unplanned_mean"] = [float(unplanned[s].mean()) for s in stations]
    meta["unplanned_scale"] = [float(unplanned_scales.loc[s]) for s in stations]
    meta["mean_p_max_pu"] = [float(hourly[s].mean()) for s in stations]
    meta = meta.merge(annual_meta, on="station_name", how="left")
    outage_summary = outage_meta.pivot_table(
        index="station_name",
        columns="outage_type",
        values=["outage_profile_column", "outage_profile_source"],
        aggfunc="first",
    )
    outage_summary.columns = [f"{a}_{b}" for a, b in outage_summary.columns]
    meta = meta.merge(outage_summary.reset_index(), on="station_name", how="left")
    return hourly.rename_axis("datetime"), meta


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--configfile",
        default=Path("configs/za/za_2023_fixed_validation.yaml"),
        type=Path,
    )
    parser.add_argument(
        "--rsa-scenarios",
        required=True,
        type=Path,
        help="Path to pypsa-rsa scenarios/Benchmark_2023/sub_scenarios",
    )
    parser.add_argument(
        "--network",
        default=Path("networks/za_2023_fixed_validation/elec_s_34_ec_lc1_NoCO2-1H.nc"),
        type=Path,
        help="Retained for CLI compatibility; bus mapping comes from custom_powerplants.csv",
    )
    parser.add_argument(
        "--custom-powerplants",
        default=Path("data/custom_powerplants.csv"),
        type=Path,
        help="PyPSA-Earth custom_powerplants.csv used only for bus mapping and split weights",
    )
    parser.add_argument(
        "--availability-mode",
        choices=sorted(AVAILABILITY_MODES),
        default="raw_base",
    )
    parser.add_argument("--outage-profiles-scenario", default="BASE")
    parser.add_argument("--annual-availability-scenario", default="EAF_48")
    parser.add_argument("--year", default=DEFAULT_YEAR, type=int)
    parser.add_argument(
        "--ramp-multiplier",
        default=DEFAULT_RAMP_MULTIPLIER,
        type=float,
        help=(
            "RSA coal ramp-rate multiplier to materialize in the CSV. "
            "The network layer must not multiply these ramp fields again."
        ),
    )
    parser.add_argument(
        "--plants-out",
        default=Path("data/za_validation/za_coal_plants_2023.csv"),
        type=Path,
    )
    parser.add_argument(
        "--eaf-out",
        default=Path("data/za_validation/za_coal_eaf_hourly_2023.csv"),
        type=Path,
    )
    parser.add_argument(
        "--bus-out",
        default=Path("data/za_validation/za_coal_bus_assignment.csv"),
        type=Path,
    )
    args = parser.parse_args()

    with open(args.configfile, "r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    fleet_cfg = resolved_config(config)

    rsa = args.rsa_scenarios
    coal = select_coal_fleet(
        load_var_hr_coal(rsa / "fixed_technologies.xlsx"),
        mode=fleet_cfg["effective_mode"],
        include_kelvin=fleet_cfg["include_kelvin"],
    )
    fuel_prices = load_fuel_prices(rsa / "fuel_prices.xlsx")
    station_specs = build_station_specs(coal, fuel_prices, args.ramp_multiplier)
    custom_bus_rows = load_custom_coal_bus_rows(args.custom_powerplants)
    plants, bus_assignment = build_generator_rows(station_specs, custom_bus_rows)
    stations = station_specs["station_name"].astype(str).tolist()
    hourly_eaf, eaf_meta = build_hourly_availability(
        rsa / "plant_availability.xlsx",
        stations,
        args.year,
        args.availability_mode,
        args.outage_profiles_scenario,
        args.annual_availability_scenario,
        (config.get("za_coal_disaggregation", {}) or {}).get(
            "annual_availability_target_override", {}
        ),
    )
    plants = plants.merge(eaf_meta, on="station_name", how="left")

    args.plants_out.parent.mkdir(parents=True, exist_ok=True)
    args.eaf_out.parent.mkdir(parents=True, exist_ok=True)
    args.bus_out.parent.mkdir(parents=True, exist_ok=True)
    plants.to_csv(args.plants_out, index=False)
    hourly_eaf.to_csv(args.eaf_out)
    bus_assignment.to_csv(args.bus_out, index=False)

    jan = hourly_eaf.loc[f"{args.year}-01", "Arnot"].mean()
    jul = hourly_eaf.loc[f"{args.year}-07", "Arnot"].mean()
    print(
        f"Wrote {args.plants_out} "
        f"({plants['station_name'].nunique()} stations, {len(plants)} generator rows, "
        f"{plants['p_nom_mw'].sum():.0f} MW)"
    )
    print(
        f"Wrote {args.eaf_out} ({hourly_eaf.shape[0]} hours x {hourly_eaf.shape[1]} stations, "
        f"mode={args.availability_mode}, mean={hourly_eaf.mean().mean():.4f}, "
        f"Arnot Jan={jan:.4f}, Arnot Jul={jul:.4f})"
    )
    print(f"Wrote {args.bus_out} ({len(bus_assignment)} generator-bus assignments)")
    return 0


def _main_from_snakemake() -> int:
    sm = globals()["snakemake"]
    config = dict(sm.config)
    fleet_cfg = resolved_config(config)
    rsa = Path(sm.params.rsa_scenarios)
    coal = select_coal_fleet(
        load_var_hr_coal(rsa / "fixed_technologies.xlsx"),
        mode=fleet_cfg["effective_mode"],
        include_kelvin=fleet_cfg["include_kelvin"],
    )
    fuel_prices = load_fuel_prices(rsa / "fuel_prices.xlsx")
    ramp_multiplier = float(
        (config.get("za_coal_disaggregation", {}) or {})
        .get("uc", {})
        .get("ramp_multiplier", DEFAULT_RAMP_MULTIPLIER)
    )
    station_specs = build_station_specs(coal, fuel_prices, ramp_multiplier)
    custom_bus_rows = load_custom_coal_bus_rows(Path(sm.input.custom_powerplants))
    plants, bus_assignment = build_generator_rows(station_specs, custom_bus_rows)
    stations = station_specs["station_name"].astype(str).tolist()
    disagg = config.get("za_coal_disaggregation", {}) or {}
    hourly_eaf, eaf_meta = build_hourly_availability(
        rsa / "plant_availability.xlsx",
        stations,
        int(disagg.get("year", DEFAULT_YEAR)),
        str(disagg.get("availability_mode", "raw_base")),
        str(disagg.get("outage_profiles_scenario", "BASE")),
        str(disagg.get("annual_availability_scenario", "EAF_48")),
        disagg.get("annual_availability_target_override", {}),
    )
    plants = plants.merge(eaf_meta, on="station_name", how="left")

    Path(sm.output.plants).parent.mkdir(parents=True, exist_ok=True)
    Path(sm.output.eaf).parent.mkdir(parents=True, exist_ok=True)
    Path(sm.output.buses).parent.mkdir(parents=True, exist_ok=True)
    plants.to_csv(sm.output.plants, index=False)
    hourly_eaf.to_csv(sm.output.eaf)
    bus_assignment.to_csv(sm.output.buses, index=False)
    print(
        f"Wrote {sm.output.plants} "
        f"({plants['station_name'].nunique()} stations, {len(plants)} generator rows, "
        f"{plants['p_nom_mw'].sum():.0f} MW, mode={fleet_cfg['requested_mode']})"
    )
    return 0


if __name__ == "__main__":
    if "snakemake" in globals():
        raise SystemExit(_main_from_snakemake())
    raise SystemExit(main())
