# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""ZA Calibration Plan Module 12 — apply station-weekly coal EAF overlay.

Reads PyPSA-RSA ``plant_availability.xlsx:outage_profiles`` (BASE scenario),
maps station-level planned + unplanned outage profiles through
``data/custom_powerplants.csv`` to bus-level coal availability, and writes a
prepared EAF network. The mutation surface is intentionally narrow:
``generators_t.p_max_pu`` for coal generators only.
"""

import logging
import re
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("apply_coal_eaf")

OUTAGE_TYPES = ("planned", "unplanned")
WORKBOOK_STATION_EXCLUDES = {
    # The workbook has a Kelvin column, but the Module 12 station table treats
    # Kelvin as unmatched and requires the fleet fallback.
    "Kelvin",
}
NON_STATION_COLUMNS = {
    "scenario",
    "type",
    "week",
    "RSA-coal_eskom_low",
    "RSA-coal_eskom_med",
    "RSA-coal_eskom_high",
    "coal",
    "nuclear",
    "ocgt_diesel",
    "ocgt_diesel_emg",
    "ocgt_gas",
    "ocgt_gas_h2_40",
    "ocgt_gas_h2_45",
    "ocgt_gas_h2_50",
    "ocgt_gas_h2_55",
    "ocgt_gas_h2_60",
    "ccgt_steam",
    "hydro",
}


def load_base_outage_profiles(
    workbook: Path,
    sheet: str = "outage_profiles",
    scenario: str = "BASE",
) -> pd.DataFrame:
    """Read BASE weekly planned/unplanned outage rows from the workbook."""
    df = pd.read_excel(workbook, sheet_name=sheet, header=1)
    required = {"scenario", "type", "week"}
    missing = required.difference(df.columns)
    if missing:
        raise SystemExit(f"{workbook}:{sheet} missing required columns: {sorted(missing)}")

    out = df[(df["scenario"] == scenario) & (df["type"].isin(OUTAGE_TYPES))].copy()
    out["week"] = pd.to_numeric(out["week"], errors="coerce")
    out = out[out["week"].notna()].copy()
    out["week"] = out["week"].astype(int)
    out = out[out["week"].between(1, 53)]
    if out.empty:
        raise SystemExit(f"No numeric weekly rows found for scenario={scenario!r} in {workbook}:{sheet}")

    station_cols = [
        c
        for c in out.columns
        if c not in NON_STATION_COLUMNS and c not in WORKBOOK_STATION_EXCLUDES
    ]
    if not station_cols:
        raise SystemExit(f"No station columns found in {workbook}:{sheet}")

    out = out[["week", "type"] + station_cols].copy()
    for c in station_cols:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def compute_station_weekly_availability(outage: pd.DataFrame) -> pd.DataFrame:
    """Return weekly station availability = clip(1 - planned - unplanned, 0, 1)."""
    station_cols = [c for c in outage.columns if c not in {"week", "type"}]
    long = outage.melt(
        id_vars=["week", "type"],
        value_vars=station_cols,
        var_name="station",
        value_name="outage",
    )
    wide = long.pivot_table(
        index=["week", "station"],
        columns="type",
        values="outage",
        aggfunc="first",
    )
    for outage_type in OUTAGE_TYPES:
        if outage_type not in wide.columns:
            raise SystemExit(f"Missing outage type {outage_type!r} in workbook rows")
    avail = 1.0 - wide["planned"].fillna(0.0) - wide["unplanned"].fillna(0.0)
    station_weekly = avail.clip(lower=0.0, upper=1.0).unstack("station").sort_index()
    station_weekly.index = station_weekly.index.astype(int)
    return station_weekly


def reconcile_station_key(name: str) -> str:
    """Strip a terminal '_<digits>' suffix from custom_powerplants station names."""
    return re.sub(r"_\d+$", "", str(name))


def load_coal_station_bus_map(custom_pp: Path) -> pd.DataFrame:
    """Read custom_powerplants.csv and return Hard Coal station-to-bus rows."""
    df = pd.read_csv(custom_pp)
    required = {"Name", "Fueltype", "bus", "Capacity"}
    missing = required.difference(df.columns)
    if missing:
        raise SystemExit(f"{custom_pp} missing required columns: {sorted(missing)}")

    coal = df[df["Fueltype"] == "Hard Coal"][["Name", "bus", "Capacity"]].copy()
    coal["station_key"] = coal["Name"].map(reconcile_station_key)
    coal["Capacity"] = pd.to_numeric(coal["Capacity"], errors="coerce")
    coal = coal.dropna(subset=["Capacity"])
    return coal[["Name", "station_key", "bus", "Capacity"]]


def build_bus_weekly_availability(
    station_weekly: pd.DataFrame,
    coal_map: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Capacity-weight station weekly profiles to PyPSA bus-level availability."""
    rows = coal_map.copy()
    rows["matched"] = rows["station_key"].isin(station_weekly.columns)
    rows["fallback_used"] = ~rows["matched"]

    audit_cols = ["Name", "station_key", "bus", "Capacity", "matched", "fallback_used"]
    matched = rows[rows["matched"]].copy()
    if matched.empty:
        raise SystemExit("No Hard Coal custom_powerplants rows matched workbook station columns")

    bus_profiles: dict[str, pd.Series] = {}
    for bus, grp in matched.groupby("bus"):
        denom = float(grp["Capacity"].sum())
        if denom <= 0:
            continue
        weighted = pd.Series(0.0, index=station_weekly.index, dtype=float)
        for _, r in grp.iterrows():
            weighted = weighted.add(
                station_weekly[str(r["station_key"])] * float(r["Capacity"]),
                fill_value=0.0,
            )
        bus_profiles[str(bus)] = weighted / denom

    if not bus_profiles:
        raise SystemExit("No bus-level weekly availability profiles could be built")
    bus_weekly = pd.DataFrame(bus_profiles).sort_index(axis=1)
    return bus_weekly, rows[audit_cols].copy()


def expand_weekly_to_snapshots(
    bus_weekly: pd.DataFrame,
    snapshots: pd.DatetimeIndex,
) -> pd.DataFrame:
    """Broadcast weekly bus values to snapshots; ISO week 53 reuses week 52."""
    weeks = pd.Series(snapshots.isocalendar().week.to_numpy(dtype=int), index=snapshots)
    weeks = weeks.mask(weeks == 53, 52)
    if 52 not in bus_weekly.index and (weeks == 52).any():
        raise SystemExit("Snapshot ISO week 52 required but absent from weekly availability table")
    missing = sorted(set(weeks.unique()).difference(set(bus_weekly.index)))
    if missing:
        raise SystemExit(f"Snapshot ISO weeks missing from weekly availability table: {missing}")
    hourly = bus_weekly.reindex(weeks.to_numpy()).copy()
    hourly.index = snapshots
    return hourly


def apply_coal_p_max_pu(
    n: pypsa.Network,
    hourly_bus_availability: pd.DataFrame,
    fallback: pd.Series,
) -> pd.DataFrame:
    """Apply bus availability to coal generator p_max_pu columns only."""
    coal = n.generators[n.generators["carrier"] == "coal"]
    if coal.empty:
        raise SystemExit("No coal generators found in network")

    if n.generators_t.p_max_pu.empty:
        n.generators_t.p_max_pu = pd.DataFrame(index=n.snapshots)
    else:
        n.generators_t.p_max_pu = n.generators_t.p_max_pu.reindex(index=n.snapshots)

    fallback = fallback.reindex(n.snapshots)
    if fallback.isna().any():
        raise SystemExit("Fleet fallback has missing snapshot values")

    rows: list[dict] = []
    for gen_name, gen in coal.iterrows():
        bus = str(gen["bus"])
        if bus in hourly_bus_availability.columns:
            series = hourly_bus_availability[bus].reindex(n.snapshots)
            fallback_used = False
        else:
            series = fallback
            fallback_used = True
        if series.isna().any():
            raise SystemExit(f"Availability profile for generator {gen_name!r} contains NaN values")
        n.generators_t.p_max_pu.loc[:, gen_name] = series.astype(float).clip(lower=0.0, upper=1.0)
        rows.append(
            {
                "record_type": "generator",
                "gen_name": gen_name,
                "bus": bus,
                "station_key": "",
                "fallback_used": fallback_used,
                "mean_p_max_pu": float(n.generators_t.p_max_pu[gen_name].mean()),
            }
        )
    return pd.DataFrame(rows)


def write_audit(audit_out: Path, audit_rows: pd.DataFrame, metadata: dict) -> None:
    """Write metadata plus per-station/per-generator overlay audit rows."""
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit = audit_rows.copy()
    for key, value in metadata.items():
        audit[key] = value
    ordered = list(metadata.keys()) + [c for c in audit.columns if c not in metadata]
    audit = audit[ordered]
    audit.to_csv(audit_out, index=False)
    logger.info("Wrote coal EAF audit (%d rows) to %s", len(audit), audit_out)


def _fleet_fallback_to_snapshots(
    station_weekly: pd.DataFrame,
    coal_map: pd.DataFrame,
    snapshots: pd.DatetimeIndex,
) -> pd.Series:
    matched = coal_map[coal_map["station_key"].isin(station_weekly.columns)].copy()
    denom = float(matched["Capacity"].sum())
    if denom <= 0:
        raise SystemExit("Cannot compute fleet fallback: matched coal capacity is zero")
    weekly = pd.Series(0.0, index=station_weekly.index, dtype=float)
    for _, r in matched.iterrows():
        weekly = weekly.add(station_weekly[str(r["station_key"])] * float(r["Capacity"]), fill_value=0.0)
    weekly = weekly / denom
    hourly = expand_weekly_to_snapshots(pd.DataFrame({"fallback": weekly}), snapshots)
    return hourly["fallback"]


def _non_coal_p_max_pu(n: pypsa.Network) -> pd.DataFrame:
    non_coal = n.generators.index[n.generators["carrier"] != "coal"]
    return n.generators_t.p_max_pu.reindex(columns=n.generators_t.p_max_pu.columns.intersection(non_coal)).copy()


def _station_audit_rows(per_row_audit: pd.DataFrame) -> pd.DataFrame:
    out = per_row_audit.copy()
    out.insert(0, "record_type", "station_row")
    out["gen_name"] = ""
    out["mean_p_max_pu"] = np.nan
    return out


def _enrich_generator_station_keys(generator_audit: pd.DataFrame, per_row_audit: pd.DataFrame) -> pd.DataFrame:
    """Add station-key lists by bus where custom_powerplants bus names match."""
    by_bus = (
        per_row_audit.groupby("bus")["station_key"]
        .apply(lambda s: "|".join(sorted(set(map(str, s)))))
        .to_dict()
    )
    out = generator_audit.copy()
    out["station_key"] = out["bus"].map(by_bus).fillna("")
    return out


def main(
    network_in: Path,
    network_out: Path,
    workbook: Path,
    custom_pp: Path,
    audit_out: Path,
    backup: Path | None = None,
) -> int:
    if backup is not None:
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(network_in, backup)
        logger.info("Backed up %s -> %s", network_in, backup)

    logger.info("Loading network %s", network_in)
    n = pypsa.Network(str(network_in))
    non_coal_before = _non_coal_p_max_pu(n)

    outage = load_base_outage_profiles(workbook)
    station_weekly = compute_station_weekly_availability(outage)
    coal_map = load_coal_station_bus_map(custom_pp)
    bus_weekly, per_row_audit = build_bus_weekly_availability(station_weekly, coal_map)
    fallback = _fleet_fallback_to_snapshots(station_weekly, coal_map, n.snapshots)
    hourly_bus = expand_weekly_to_snapshots(bus_weekly, n.snapshots)
    generator_audit = apply_coal_p_max_pu(n, hourly_bus, fallback)

    non_coal_after = _non_coal_p_max_pu(n).reindex(columns=non_coal_before.columns)
    non_coal_changed = not non_coal_before.equals(non_coal_after)
    if non_coal_changed:
        raise SystemExit("GATE FAIL: non-coal generators_t.p_max_pu changed during coal EAF overlay")

    network_out.parent.mkdir(parents=True, exist_ok=True)
    n.export_to_netcdf(str(network_out))
    logger.info("Saved EAF network to %s", network_out)

    station_rows = _station_audit_rows(per_row_audit)
    gen_rows = _enrich_generator_station_keys(generator_audit, per_row_audit)
    audit_rows = pd.concat([station_rows, gen_rows], ignore_index=True, sort=False)
    unmatched_mw = float(per_row_audit.loc[~per_row_audit["matched"], "Capacity"].sum())
    metadata = {
        "source_workbook": str(workbook),
        "sheet": "outage_profiles",
        "scenario": "BASE",
        "outage_types": "planned+unplanned",
        "station_to_bus_mapping_rule": "strip_terminal_numeric_suffix_then_capacity_weight_by_bus",
        "any_fallback_used": bool(per_row_audit["fallback_used"].any() or generator_audit["fallback_used"].any()),
        "unmatched_mw": unmatched_mw,
        "coal_generators_overlaid": int((n.generators["carrier"] == "coal").sum()),
        "n_snapshots": int(len(n.snapshots)),
        "mean_fleet_availability": float(fallback.mean()),
        "non_coal_p_max_pu_changed": False,
    }
    write_audit(audit_out, audit_rows, metadata)
    return 0


if __name__ == "__main__":
    if "snakemake" in globals():
        snakemake = globals()["snakemake"]
        log_path = Path(snakemake.log[0])
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(log_path), mode="w")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logging.getLogger().addHandler(fh)
        sys.exit(
            main(
                network_in=Path(snakemake.input.network_in),
                network_out=Path(snakemake.output.network_out),
                workbook=Path(snakemake.input.workbook),
                custom_pp=Path(snakemake.input.custom_pp),
                audit_out=Path(snakemake.output.audit),
                backup=Path(snakemake.output.backup),
            )
        )
    else:
        import argparse

        ap = argparse.ArgumentParser()
        ap.add_argument("--network-in", required=True)
        ap.add_argument("--network-out", required=True)
        ap.add_argument("--workbook", required=True)
        ap.add_argument("--custom-pp", default="data/custom_powerplants.csv")
        ap.add_argument("--audit", default="data/za_audit/za_coal_eaf_audit.csv")
        ap.add_argument("--backup")
        args = ap.parse_args()
        sys.exit(
            main(
                network_in=Path(args.network_in),
                network_out=Path(args.network_out),
                workbook=Path(args.workbook),
                custom_pp=Path(args.custom_pp),
                audit_out=Path(args.audit),
                backup=Path(args.backup) if args.backup else None,
            )
        )
