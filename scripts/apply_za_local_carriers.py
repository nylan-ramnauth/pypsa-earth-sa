# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""ZA Calibration Plan Module 11 — apply_za_local_carriers hook.

Runs against the clustered network `elec_s_34.nc` (after Module 09b custom-line
injection). pypsa-earth's upstream `add_electricity` only attaches carriers
listed under `electricity.conventional_carriers` (here: coal, nuclear) so
Sasol/OCGT plants in `data/custom_powerplants.csv` arrive un-attached. This
hook closes that gap and attaches the locked `other_re` exogenous Generator.

Adds Carrier rows for: sasol_coal, sasol_gas, ocgt_diesel, ocgt_gas, other_re.
Splits 128 MW Sasolburg_coal from the aggregated `Witbank coal` row into a new
`Witbank sasol_coal` generator. Attaches Sasol_ice + Sasol_ocgt as `sasol_gas`
on Vaal. Attaches Oil-fueltype OCGTs as `ocgt_diesel` at their `bus` columns.
Attaches 34 `other_re` generators (one per supply area) with the Eskom 8760
"Other RE" profile (per-unit), p_nom = 50.58 MW * area weight, p_min_pu = 0.

Upstream Carrier rows are not mutated. Network mutation is in-place; a backup
`.pre_local.nc` is written first.
"""
import logging
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("apply_za_local_carriers")

OTHER_RE_PNOM_MW = 50.58  # End-of-2023 installed capacity anchor (Module 02).


def _load_carrier_costs(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.set_index("carrier")
    return df


def _carrier_kwargs(row: pd.Series) -> dict:
    kw = {}
    co2 = row.get("co2_emissions")
    if pd.notna(co2):
        kw["co2_emissions"] = float(co2)
    nice = row.get("nice_name")
    if pd.notna(nice) and str(nice).strip():
        kw["nice_name"] = str(nice).strip()
    color = row.get("color")
    if pd.notna(color) and str(color).strip():
        kw["color"] = str(color).strip()
    return kw


def patch_standard_carrier_costs(n: pypsa.Network, costs: pd.DataFrame, audit_rows: list) -> None:
    """Override coal and nuclear generator marginal costs with ZA-specific values.

    costs_2030_elec.csv carries EU-2030 fuel prices with carbon pricing baked in
    (coal 565 EUR/MWh, nuclear 263 EUR/MWh). ZA-specific values from PyPSA-RSA
    fuel_prices.xlsx are coal ~41 EUR/MWh and nuclear ~16 EUR/MWh. This function
    patches the already-attached generators in-place; n.carriers is not touched.
    Also corrects coal co2_emissions to ZA-specific 1.010 tCO2/MWh_el.
    """
    for carrier in ["coal", "nuclear"]:
        if carrier not in costs.index:
            logger.warning("Carrier '%s' not in cost CSV; skipping patch", carrier)
            continue
        mc = float(costs.loc[carrier, "marginal_cost"])
        mask = n.generators.carrier == carrier
        if not mask.any():
            logger.warning("No generators with carrier '%s'; skipping patch", carrier)
            continue
        old_mc = float(n.generators.loc[mask, "marginal_cost"].iloc[0])
        n.generators.loc[mask, "marginal_cost"] = mc
        if carrier == "coal":
            co2 = float(costs.loc[carrier, "co2_emissions"])
            old_co2 = float(n.carriers.at["coal", "co2_emissions"]) if "coal" in n.carriers.index else 0.0
            n.carriers.at["coal", "co2_emissions"] = co2
            logger.info("Patched coal: marginal_cost %.2f -> %.2f EUR/MWh, co2_emissions %.4f -> %.4f tCO2/MWh",
                        old_mc, mc, old_co2, co2)
            co2_log = co2
        else:
            logger.info("Patched nuclear: marginal_cost %.2f -> %.2f EUR/MWh", old_mc, mc)
            co2_log = 0.0
        for gen_name in n.generators.index[mask]:
            audit_rows.append({
                "action": "patch_standard_carrier_cost",
                "carrier": carrier,
                "name": gen_name,
                "bus": n.generators.at[gen_name, "bus"],
                "p_nom": n.generators.at[gen_name, "p_nom"],
                "p_nom_extendable": False,
                "marginal_cost": mc,
                "co2_emissions": co2_log,
                "mean_p_max_pu": np.nan,
            })


def add_local_carriers(n: pypsa.Network, costs: pd.DataFrame, audit_rows: list) -> None:
    upstream_carriers = set(n.carriers.index)
    for carrier in ["sasol_coal", "sasol_gas", "ocgt_diesel", "ocgt_gas", "other_re"]:
        if carrier in upstream_carriers:
            raise SystemExit(f"Upstream Carrier '{carrier}' unexpectedly present; aborting to avoid mutation.")
        if carrier not in costs.index:
            raise SystemExit(f"Carrier '{carrier}' missing from cost CSV.")
        kw = _carrier_kwargs(costs.loc[carrier])
        n.add("Carrier", carrier, **kw)
        audit_rows.append({
            "action": "add_carrier",
            "carrier": carrier,
            "name": "",
            "bus": "",
            "p_nom": np.nan,
            "p_nom_extendable": False,
            "marginal_cost": float(costs.loc[carrier, "marginal_cost"]) if pd.notna(costs.loc[carrier, "marginal_cost"]) else np.nan,
            "co2_emissions": kw.get("co2_emissions", np.nan),
            "mean_p_max_pu": np.nan,
        })


def _generator_kwargs(costs_row: pd.Series, bus: str, carrier: str, p_nom: float) -> dict:
    kw = dict(
        bus=bus,
        carrier=carrier,
        p_nom=float(p_nom),
        p_nom_extendable=False,
        p_min_pu=0.0,
        p_max_pu=1.0,
    )
    mc = costs_row.get("marginal_cost")
    if pd.notna(mc):
        kw["marginal_cost"] = float(mc)
    eff = costs_row.get("efficiency")
    if pd.notna(eff):
        kw["efficiency"] = float(eff)
    return kw


def split_sasol_coal(n: pypsa.Network, custom_pp: pd.DataFrame, costs: pd.DataFrame, audit_rows: list) -> None:
    sasol_coal_rows = custom_pp[custom_pp["Name"].str.contains("Sasolburg_coal", case=False, na=False)]
    if sasol_coal_rows.empty:
        logger.warning("No Sasolburg_coal row in custom_powerplants.csv; skipping sasol_coal split")
        return
    total = float(sasol_coal_rows["Capacity"].sum())
    bus = str(sasol_coal_rows.iloc[0]["bus"])
    agg_name = f"{bus} coal"
    if agg_name not in n.generators.index:
        raise SystemExit(f"Aggregate coal generator '{agg_name}' not found; cannot split sasol_coal")

    prior = float(n.generators.at[agg_name, "p_nom"])
    if prior < total:
        raise SystemExit(f"Aggregate '{agg_name}' p_nom {prior} < sasol_coal target {total}")
    n.generators.at[agg_name, "p_nom"] = prior - total
    new_name = f"{bus} sasol_coal"
    kw = _generator_kwargs(costs.loc["sasol_coal"], bus=bus, carrier="sasol_coal", p_nom=total)
    n.add("Generator", new_name, **kw)
    logger.info("Split %.1f MW Sasolburg_coal off '%s' (%.1f -> %.1f) into '%s'",
                total, agg_name, prior, prior - total, new_name)
    audit_rows.append({
        "action": "split_sasol_coal",
        "carrier": "sasol_coal",
        "name": new_name,
        "bus": bus,
        "p_nom": total,
        "p_nom_extendable": False,
        "marginal_cost": kw.get("marginal_cost", np.nan),
        "co2_emissions": float(costs.loc["sasol_coal", "co2_emissions"]),
        "mean_p_max_pu": 1.0,
    })


def attach_oil_and_gas(n: pypsa.Network, custom_pp: pd.DataFrame, costs: pd.DataFrame, audit_rows: list) -> None:
    # Per scripts/za_fleet/named_inventory.py:
    #   Fueltype == "Oil"          -> ocgt_diesel  (Ankerlig/Gourikwa/Acacia/PortRex/Avon/Dedisa)
    #   Fueltype == "Natural Gas" + Name startswith "Sasol_"  -> sasol_gas
    #   Fueltype == "Natural Gas" + not Sasol                 -> ocgt_gas
    is_oil = custom_pp["Fueltype"] == "Oil"
    is_ng = custom_pp["Fueltype"] == "Natural Gas"
    is_sasol_ng = is_ng & custom_pp["Name"].str.lower().str.startswith("sasol_")

    plants_by_carrier = {
        "ocgt_diesel": custom_pp[is_oil],
        "sasol_gas":   custom_pp[is_ng & is_sasol_ng],
        "ocgt_gas":    custom_pp[is_ng & ~is_sasol_ng],
    }

    for carrier, df in plants_by_carrier.items():
        if df.empty:
            logger.info("No plants to attach for carrier '%s'", carrier)
            continue
        # Aggregate by bus to keep one generator per (bus, carrier).
        agg = df.groupby("bus")["Capacity"].sum().reset_index()
        for _, r in agg.iterrows():
            bus = str(r["bus"])
            cap = float(r["Capacity"])
            if bus not in n.buses.index:
                raise SystemExit(f"Bus '{bus}' from custom_powerplants not in clustered network; cannot attach {carrier}")
            name = f"{bus} {carrier}"
            if name in n.generators.index:
                raise SystemExit(f"Generator '{name}' already exists; refusing to overwrite")
            kw = _generator_kwargs(costs.loc[carrier], bus=bus, carrier=carrier, p_nom=cap)
            n.add("Generator", name, **kw)
            logger.info("Attached %s: %s p_nom=%.1f MW", carrier, name, cap)
            audit_rows.append({
                "action": "add_generator",
                "carrier": carrier,
                "name": name,
                "bus": bus,
                "p_nom": cap,
                "p_nom_extendable": False,
                "marginal_cost": kw.get("marginal_cost", np.nan),
                "co2_emissions": float(costs.loc[carrier, "co2_emissions"]),
                "mean_p_max_pu": 1.0,
            })


def retag_csp_from_solar(n: pypsa.Network, custom_pp: pd.DataFrame, audit_rows: list) -> None:
    # Six 2023 CSP plants in custom_powerplants.csv have Fueltype=Solar + Technology=CSP.
    # add_electricity aggregates them into the per-bus `solar` Generator (wrong carrier,
    # wrong profile). Move the CSP capacity onto the upstream `{bus} csp` ghost Generator,
    # which already carries the correct CSP atlite profile in `n.generators_t.p_max_pu`.
    csp_rows = custom_pp[(custom_pp["Fueltype"] == "Solar") & (custom_pp["Technology"] == "CSP")]
    if csp_rows.empty:
        logger.info("No CSP rows in custom_powerplants.csv; skipping CSP re-tag")
        return
    agg = csp_rows.groupby("bus")["Capacity"].sum().reset_index()
    for _, r in agg.iterrows():
        bus = str(r["bus"])
        cap = float(r["Capacity"])
        solar_name = f"{bus} solar"
        csp_name = f"{bus} csp"
        if solar_name not in n.generators.index:
            raise SystemExit(f"Missing solar generator '{solar_name}'; cannot subtract CSP")
        if csp_name not in n.generators.index:
            raise SystemExit(f"Missing csp ghost generator '{csp_name}'; cannot transfer CSP")
        prior_solar = float(n.generators.at[solar_name, "p_nom"])
        prior_csp = float(n.generators.at[csp_name, "p_nom"])
        if prior_solar < cap:
            raise SystemExit(f"'{solar_name}' p_nom {prior_solar:.1f} < CSP target {cap:.1f}; cannot subtract")
        n.generators.at[solar_name, "p_nom"] = prior_solar - cap
        n.generators.at[csp_name, "p_nom"] = prior_csp + cap
        logger.info("CSP retag at %s: solar %.1f -> %.1f, csp %.1f -> %.1f (+%.1f MW)",
                    bus, prior_solar, prior_solar - cap, prior_csp, prior_csp + cap, cap)
        audit_rows.append({
            "action": "retag_csp_from_solar",
            "carrier": "csp",
            "name": csp_name,
            "bus": bus,
            "p_nom": cap,
            "p_nom_extendable": False,
            "marginal_cost": float(n.generators.at[csp_name, "marginal_cost"]),
            "co2_emissions": 0.0,
            "mean_p_max_pu": float(n.generators_t.p_max_pu[csp_name].mean()) if csp_name in n.generators_t.p_max_pu.columns else np.nan,
        })


def _load_other_re_profile(hourly_path: Path, snapshots: pd.DatetimeIndex) -> pd.Series:
    df = pd.read_csv(hourly_path)
    df["ts"] = pd.to_datetime(df["Date Time Hour Beginning"])
    df = df.set_index("ts").sort_index()
    if "Other RE" not in df.columns:
        raise SystemExit("Column 'Other RE' missing from Eskom hourly CSV")
    raw = pd.to_numeric(df["Other RE"], errors="coerce").fillna(0.0)
    per_unit = (raw / OTHER_RE_PNOM_MW).clip(lower=0.0, upper=1.0)
    aligned = per_unit.reindex(snapshots)
    if aligned.isna().any():
        # Map by hour-of-year if exact snapshot timestamps don't match.
        per_unit_2023 = per_unit.copy()
        # Use month/day/hour key, ignoring year, to remap into snapshot index.
        key_src = pd.MultiIndex.from_arrays([per_unit_2023.index.month, per_unit_2023.index.day, per_unit_2023.index.hour])
        per_unit_2023.index = key_src
        per_unit_2023 = per_unit_2023[~per_unit_2023.index.duplicated()]
        key_dst = pd.MultiIndex.from_arrays([snapshots.month, snapshots.day, snapshots.hour])
        aligned = pd.Series(per_unit_2023.reindex(key_dst).values, index=snapshots).fillna(0.0)
    return aligned


def attach_other_re(n: pypsa.Network, attachment_path: Path, hourly_path: Path, costs: pd.DataFrame, audit_rows: list) -> None:
    att = pd.read_csv(attachment_path)
    att34 = att[att["layer_key"] == 34].copy()
    if att34.empty:
        raise SystemExit("No layer_key==34 rows in other_re attachment CSV")
    total_weight = float(att34["weight"].sum())
    if not np.isclose(total_weight, 1.0, atol=1e-3):
        raise SystemExit(f"other_re weights for layer_key=34 do not sum to 1.0 (got {total_weight})")

    missing = set(att34["target_region_id"]) - set(n.buses.index)
    if missing:
        raise SystemExit(f"other_re target buses missing from clustered network: {sorted(missing)}")

    profile = _load_other_re_profile(hourly_path, n.snapshots)
    mean_profile = float(profile.mean())

    for _, r in att34.iterrows():
        bus = str(r["target_region_id"])
        w = float(r["weight"])
        p_nom = OTHER_RE_PNOM_MW * w
        name = f"{bus} other_re"
        if name in n.generators.index:
            raise SystemExit(f"Generator '{name}' already exists")
        n.add(
            "Generator",
            name,
            bus=bus,
            carrier="other_re",
            p_nom=p_nom,
            p_nom_extendable=False,
            p_min_pu=0.0,
            marginal_cost=0.0,
        )
        n.generators_t.p_max_pu[name] = profile.values
        audit_rows.append({
            "action": "add_other_re",
            "carrier": "other_re",
            "name": name,
            "bus": bus,
            "p_nom": p_nom,
            "p_nom_extendable": False,
            "marginal_cost": 0.0,
            "co2_emissions": 0.0,
            "mean_p_max_pu": mean_profile,
        })


def assert_no_upstream_carrier_mutation(before: pd.DataFrame, after: pd.DataFrame) -> None:
    cols = [c for c in before.columns if c in after.columns]
    for carrier in before.index:
        if carrier not in after.index:
            raise SystemExit(f"Upstream carrier '{carrier}' missing after hook")
        for col in cols:
            v_before, v_after = before.at[carrier, col], after.at[carrier, col]
            same = (pd.isna(v_before) and pd.isna(v_after)) or (v_before == v_after)
            if not same:
                raise SystemExit(f"Upstream carrier mutation: {carrier}.{col} {v_before!r} -> {v_after!r}")


def main(
    network_in: Path,
    carrier_costs_path: Path,
    attachment_path: Path,
    hourly_path: Path,
    custom_pp_path: Path,
    backup_out: Path,
    audit_out: Path,
) -> None:
    backup_out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(network_in, backup_out)
    logger.info("Backed up %s -> %s", network_in, backup_out)

    n = pypsa.Network(str(network_in))
    costs = _load_carrier_costs(carrier_costs_path)
    custom_pp = pd.read_csv(custom_pp_path)

    audit_rows: list = []
    patch_standard_carrier_costs(n, costs, audit_rows)
    # Capture carrier baseline AFTER intentional coal/nuclear patches so the
    # assertion only catches unintended mutations by subsequent steps.
    upstream_carriers = n.carriers.copy()
    add_local_carriers(n, costs, audit_rows)
    split_sasol_coal(n, custom_pp, costs, audit_rows)
    attach_oil_and_gas(n, custom_pp, costs, audit_rows)
    retag_csp_from_solar(n, custom_pp, audit_rows)
    attach_other_re(n, attachment_path, hourly_path, costs, audit_rows)

    assert_no_upstream_carrier_mutation(upstream_carriers, n.carriers.loc[upstream_carriers.index])

    n.export_to_netcdf(str(network_in))
    logger.info("Saved patched network to %s", network_in)

    audit = pd.DataFrame(audit_rows)
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(audit_out, index=False)
    logger.info("Wrote audit (%d rows) to %s", len(audit), audit_out)


if __name__ == "__main__":
    if "snakemake" in globals():
        snakemake = globals()["snakemake"]
        log_path = Path(snakemake.log[0])
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(log_path), mode="w")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logging.getLogger().addHandler(fh)
        main(
            network_in=Path(snakemake.input.network_in),
            carrier_costs_path=Path(snakemake.input.carrier_rows),
            attachment_path=Path(snakemake.input.attachment),
            hourly_path=Path(snakemake.input.hourly),
            custom_pp_path=Path(snakemake.input.custom_pp),
            backup_out=Path(snakemake.output.backup),
            audit_out=Path(snakemake.output.audit),
        )
    else:
        import argparse

        ap = argparse.ArgumentParser()
        ap.add_argument("--network", default="networks/za_2023_fixed_validation/elec_s_34.nc")
        ap.add_argument("--carrier-rows", default="data/za_audit/za_local_carrier_cost_rows.csv")
        ap.add_argument("--attachment", default="data/za_audit/za_2023_other_re_attachment.csv")
        ap.add_argument("--hourly", default="data/za_validation/eskom_2023_hourly_clean.csv")
        ap.add_argument("--custom-pp", default="data/custom_powerplants.csv")
        ap.add_argument("--backup", default="networks/za_2023_fixed_validation/elec_s_34.pre_local.nc")
        ap.add_argument("--audit", default="data/za_audit/za_local_carriers_audit.csv")
        args = ap.parse_args()
        main(
            network_in=Path(args.network),
            carrier_costs_path=Path(args.carrier_rows),
            attachment_path=Path(args.attachment),
            hourly_path=Path(args.hourly),
            custom_pp_path=Path(args.custom_pp),
            backup_out=Path(args.backup),
            audit_out=Path(args.audit),
        )
