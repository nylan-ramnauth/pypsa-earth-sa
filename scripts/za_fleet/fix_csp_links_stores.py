# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""ZA Calibration Plan Module 12 — fix CSP Link/Store fixed capacity.

`add_extra_components.py` (advanced CSP path, lines 177-215) adds extendable
zero-capacity Stores + Links for every CSP bus. With Module 12's empty
`extendable_carriers`, those Stores/Links stay at zero — so the CSP electric
output path is effectively dead and CSP Generators with retagged ~500 MW never
dispatch.

This script post-processes the network produced by `add_extra_components` and:

  * sets each CSP `Link.p_nom` to the bus-level CSP Generator nameplate (sum of
    `Generator.p_nom` for `carrier == "csp"` on that bus);
  * sets each CSP `Store.e_nom` to `link_p_nom * weighted_storage_hours_bus`,
    where the weighted storage hours come from joining `custom_powerplants.csv`
    (plant -> bus) with `za_named_plant_inventory.csv` (plant ->
    `csp_storage_hours=N` parsed from the `notes` column);
  * flips `*_extendable = False` for those Stores and Links so the structural
    baseline solve cannot grow them.

Buses with no inventory match get `Store.e_nom = 0` and a `fallback_used`
warning in the audit (Link still gets fixed `p_nom`, so the CSP carrier behaves
as an instantaneous tower without TES — conservative).
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
logger = logging.getLogger("fix_csp_links_stores")

_STORAGE_HOURS_RE = re.compile(r"csp_storage_hours\s*=\s*([0-9]+(?:\.[0-9]+)?)")


def _parse_storage_hours(notes: object) -> float:
    if not isinstance(notes, str):
        return float("nan")
    m = _STORAGE_HOURS_RE.search(notes)
    if not m:
        return float("nan")
    return float(m.group(1))


def _bus_storage_hours(
    custom_pp_path: Path, inventory_path: Path
) -> tuple[dict[str, float], dict[str, float], pd.DataFrame]:
    """Join custom_powerplants + named inventory on plant name and aggregate to bus.

    Returns:
        bus_capacity_mw: sum of plant capacity per bus (from custom_powerplants).
        bus_storage_hours: capacity-weighted CSP storage hours per bus.
        join_df: per-plant join table for audit.
    """
    cpp = pd.read_csv(custom_pp_path)
    cpp_csp = cpp[(cpp["Fueltype"] == "Solar") & (cpp["Technology"] == "CSP")][
        ["Name", "bus", "Capacity"]
    ].copy()
    cpp_csp.rename(columns={"Capacity": "capacity_mw"}, inplace=True)

    inv = pd.read_csv(inventory_path)
    inv_csp = inv[inv["carrier"] == "csp"][["station_name", "notes"]].copy()
    inv_csp["storage_hours"] = inv_csp["notes"].apply(_parse_storage_hours)

    join = cpp_csp.merge(
        inv_csp[["station_name", "storage_hours"]],
        left_on="Name",
        right_on="station_name",
        how="left",
    ).drop(columns=["station_name"])

    n_unmatched_plant = join["storage_hours"].isna().sum()
    if n_unmatched_plant:
        logger.warning(
            "CSP plants without storage-hours match in inventory: %d (rows: %s)",
            n_unmatched_plant,
            join.loc[join["storage_hours"].isna(), "Name"].tolist(),
        )

    bus_capacity_mw: dict[str, float] = {}
    bus_storage_hours: dict[str, float] = {}
    for bus, grp in join.groupby("bus"):
        cap_total = float(grp["capacity_mw"].sum())
        bus_capacity_mw[str(bus)] = cap_total
        matched = grp.dropna(subset=["storage_hours"])
        if matched.empty or cap_total <= 0:
            bus_storage_hours[str(bus)] = float("nan")
            continue
        weighted = float(
            (matched["capacity_mw"] * matched["storage_hours"]).sum()
            / matched["capacity_mw"].sum()
        )
        bus_storage_hours[str(bus)] = weighted

    return bus_capacity_mw, bus_storage_hours, join


def _csp_bus_to_parent(csp_bus_name: str) -> str:
    # Convention from add_extra_components.py:182-190: `main_buses + " csp"`.
    suffix = " csp"
    if csp_bus_name.endswith(suffix):
        return csp_bus_name[: -len(suffix)]
    return csp_bus_name


def fix_csp(
    n: pypsa.Network,
    bus_capacity_mw: dict[str, float],
    bus_storage_hours: dict[str, float],
) -> pd.DataFrame:
    audit_rows: list[dict] = []

    csp_stores = n.stores[n.stores.carrier == "csp"]
    csp_links = n.links[n.links.carrier == "csp"]
    csp_gens = n.generators[n.generators.carrier == "csp"]

    if csp_links.empty and csp_stores.empty:
        logger.info("No CSP Links/Stores present; nothing to fix")
        return pd.DataFrame(audit_rows)

    # Bus-level CSP nameplate from Generators on the "X csp" buses.
    gen_cap_by_csp_bus = csp_gens.groupby("bus")["p_nom"].sum()

    for csp_bus, link_name in zip(csp_links.bus0, csp_links.index):
        # Link is named after csp bus by `n.madd("Link", csp_buses_i, ...)`.
        parent_bus = _csp_bus_to_parent(str(csp_bus))
        nameplate_mw = float(gen_cap_by_csp_bus.get(csp_bus, 0.0))
        # Cross-check against custom_powerplants total at parent bus.
        cpp_cap = float(bus_capacity_mw.get(parent_bus, 0.0))
        hours = bus_storage_hours.get(parent_bus, float("nan"))
        store_e_nom = nameplate_mw * hours if np.isfinite(hours) else 0.0
        fallback = not np.isfinite(hours)

        n.links.at[link_name, "p_nom"] = nameplate_mw
        n.links.at[link_name, "p_nom_min"] = 0.0
        n.links.at[link_name, "p_nom_max"] = float("inf")
        n.links.at[link_name, "p_nom_extendable"] = False
        n.links.at[link_name, "capital_cost"] = 0.0

        # Store is added with the same index name as the csp bus.
        store_name = str(csp_bus)
        if store_name in n.stores.index:
            n.stores.at[store_name, "e_nom"] = store_e_nom
            n.stores.at[store_name, "e_nom_min"] = 0.0
            n.stores.at[store_name, "e_nom_max"] = float("inf")
            n.stores.at[store_name, "e_nom_extendable"] = False
            n.stores.at[store_name, "capital_cost"] = 0.0

        logger.info(
            "CSP bus=%s parent=%s gen=%.1f MW cpp=%.1f MW hours=%s -> link.p_nom=%.1f, store.e_nom=%.1f (fallback=%s)",
            csp_bus, parent_bus, nameplate_mw, cpp_cap, hours, nameplate_mw, store_e_nom, fallback,
        )
        audit_rows.append({
            "csp_bus": csp_bus,
            "parent_bus": parent_bus,
            "generator_p_nom_mw": nameplate_mw,
            "custom_powerplants_capacity_mw": cpp_cap,
            "storage_hours_weighted": hours,
            "link_p_nom_set_mw": nameplate_mw,
            "store_e_nom_set_mwh": store_e_nom,
            "fallback_used": fallback,
        })

    return pd.DataFrame(audit_rows)


def main(
    network_in: Path,
    custom_pp_path: Path,
    inventory_path: Path,
    backup_out: Path,
    audit_out: Path,
) -> int:
    # Backup BEFORE mutation so failures are recoverable; matches the
    # apply_za_local_carriers in-place mutation pattern.
    backup_out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(network_in, backup_out)
    logger.info("Backed up %s -> %s", network_in, backup_out)

    logger.info("Loading network %s", network_in)
    n = pypsa.Network(str(network_in))

    bus_capacity_mw, bus_storage_hours, _join_df = _bus_storage_hours(
        custom_pp_path, inventory_path
    )
    logger.info("Bus capacity totals: %s", bus_capacity_mw)
    logger.info("Bus weighted storage hours: %s", bus_storage_hours)

    audit = fix_csp(n, bus_capacity_mw, bus_storage_hours)

    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(audit_out, index=False)
    logger.info("Wrote CSP fix audit (%d rows) to %s", len(audit), audit_out)

    # Acceptance: after fix, no CSP Link/Store should remain extendable.
    bad_links = n.links[(n.links.carrier == "csp") & n.links.p_nom_extendable]
    bad_stores = n.stores[(n.stores.carrier == "csp") & n.stores.e_nom_extendable]
    if len(bad_links) or len(bad_stores):
        logger.error(
            "GATE FAIL: extendable CSP components remain (links=%d, stores=%d)",
            len(bad_links), len(bad_stores),
        )
        return 1

    n.export_to_netcdf(str(network_in))
    logger.info("Saved fixed network in place to %s", network_in)
    return 0


if __name__ == "__main__":
    if "snakemake" in globals():
        snakemake = globals()["snakemake"]
        log_path = Path(snakemake.log[0])
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(log_path), mode="w")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logging.getLogger().addHandler(fh)
        rc = main(
            network_in=Path(snakemake.input.network_in),
            custom_pp_path=Path(snakemake.input.custom_pp),
            inventory_path=Path(snakemake.input.inventory),
            backup_out=Path(snakemake.output.backup),
            audit_out=Path(snakemake.output.audit),
        )
        sys.exit(rc)
    else:
        import argparse

        ap = argparse.ArgumentParser()
        ap.add_argument("--network", required=True)
        ap.add_argument("--custom-pp", default="data/custom_powerplants.csv")
        ap.add_argument("--inventory", default="data/za_audit/za_named_plant_inventory.csv")
        ap.add_argument("--backup", required=True)
        ap.add_argument("--audit", required=True)
        args = ap.parse_args()
        sys.exit(
            main(
                network_in=Path(args.network),
                custom_pp_path=Path(args.custom_pp),
                inventory_path=Path(args.inventory),
                backup_out=Path(args.backup),
                audit_out=Path(args.audit),
            )
        )
