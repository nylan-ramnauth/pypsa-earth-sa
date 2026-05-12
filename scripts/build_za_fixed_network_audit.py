# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""ZA Calibration Plan Module 11 — fixed-capacity network audit (pre-solve gate).

Reads the prepared but unsolved network `elec_s_34_ec_l<ll>_<opts>.nc` and the
2023 Eskom capacity anchors. Emits `data/za_audit/za_fixed_network_audit.csv`
with the spec columns and gates the solve on no-unintended-extendable-capacity
and (when anchor data is available) capacity-vs-anchor deltas.

Load-shedding generators added by `solve_network.py:add_load_shedding` are not
yet present (we run pre-solve), so `is_load_shedding_safety_valve` is False
for all rows. The column is reserved for the post-solve re-run.
"""
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("build_za_fixed_network_audit")

ANCHOR_DELTA_THRESHOLD_PCT = 5.0

# Module 12 — fixed-grid expansion gate across all 5 PyPSA component classes.
_EXT_COMPONENTS: list[tuple[str, str, str]] = [
    # (component_class, nom_attr, extendable_attr)
    ("generators", "p_nom", "p_nom_extendable"),
    ("storage_units", "p_nom", "p_nom_extendable"),
    ("stores", "e_nom", "e_nom_extendable"),
    ("links", "p_nom", "p_nom_extendable"),
    ("lines", "s_nom", "s_nom_extendable"),
]


def _extendable_counts(n: pypsa.Network) -> pd.DataFrame:
    """One row per component class: total count, extendable count, nameplate sum.

    For fixed-grid Module 12 acceptance: every n_extendable must be 0.
    """
    rows = []
    for comp, nom_attr, ext_attr in _EXT_COMPONENTS:
        df = getattr(n, comp)
        n_total = int(len(df))
        if n_total == 0:
            rows.append({
                "component": comp,
                "n_total": 0,
                "n_extendable": 0,
                "nom_sum_mw": 0.0,
            })
            continue
        n_ext = int(df[ext_attr].sum()) if ext_attr in df.columns else 0
        nom_sum = float(df[nom_attr].sum()) if nom_attr in df.columns else float("nan")
        rows.append({
            "component": comp,
            "n_total": n_total,
            "n_extendable": n_ext,
            "nom_sum_mw": nom_sum,
        })
    return pd.DataFrame(rows)


def _load_anchor(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.set_index("carrier")
    if "p_nom_mw_2023_max" in df.columns:
        df["capacity_mw_anchor"] = pd.to_numeric(df["p_nom_mw_2023_max"], errors="coerce")
    else:
        df["capacity_mw_anchor"] = np.nan
    return df


def _carrier_metrics(n: pypsa.Network, carrier: str) -> dict:
    gens = n.generators[n.generators.carrier == carrier]
    storage = n.storage_units[n.storage_units.carrier == carrier] if len(n.storage_units) else n.storage_units
    p_nom_gen = float(gens.p_nom.sum()) if len(gens) else 0.0
    p_nom_storage = float(storage.p_nom.sum()) if len(storage) else 0.0
    capacity_built = p_nom_gen + p_nom_storage

    bus_set: set = set()
    if len(gens):
        bus_set |= set(gens.bus.unique())
    if len(storage):
        bus_set |= set(storage.bus.unique())

    extendable = False
    if len(gens) and gens["p_nom_extendable"].any():
        extendable = True
    if len(storage) and storage["p_nom_extendable"].any():
        extendable = True

    pmax_t = n.generators_t.p_max_pu if hasattr(n.generators_t, "p_max_pu") else pd.DataFrame()
    pmin_t = n.generators_t.p_min_pu if hasattr(n.generators_t, "p_min_pu") else pd.DataFrame()
    t_cols = [g for g in gens.index if g in pmax_t.columns] if len(pmax_t) else []
    s_cols = [g for g in gens.index if g not in t_cols]
    p_max_mean_vals = []
    if t_cols:
        p_max_mean_vals.append(float(pmax_t[t_cols].mean().mean()))
    if s_cols:
        p_max_mean_vals.append(float(gens.loc[s_cols, "p_max_pu"].mean()))
    p_max_pu_mean = float(np.mean(p_max_mean_vals)) if p_max_mean_vals else np.nan

    t_min = [g for g in gens.index if g in pmin_t.columns] if len(pmin_t) else []
    s_min = [g for g in gens.index if g not in t_min]
    p_min_mean_vals = []
    if t_min:
        p_min_mean_vals.append(float(pmin_t[t_min].mean().mean()))
    if s_min:
        p_min_mean_vals.append(float(gens.loc[s_min, "p_min_pu"].mean()))
    p_min_pu_mean = float(np.mean(p_min_mean_vals)) if p_min_mean_vals else np.nan

    return {
        "capacity_mw_built": capacity_built,
        "bus_count": len(bus_set),
        "generator_count": int(len(gens)),
        "extendable_flag": bool(extendable),
        "p_max_pu_mean": p_max_pu_mean,
        "p_min_pu_mean": p_min_pu_mean,
    }


def main(network_path: Path, anchor_path: Path, audit_out: Path) -> int:
    n = pypsa.Network(str(network_path))
    anchor = _load_anchor(anchor_path)
    logger.info("Loaded network %s (carriers=%d, gens=%d)", network_path, len(n.carriers), len(n.generators))

    carriers = sorted(set(n.carriers.index) | set(anchor.index))
    rows = []
    bus_load_total_mwh = float(
        (n.loads_t.p_set.sum(axis=1) * n.snapshot_weightings.objective).sum()
    ) if len(n.loads_t.p_set) else float((n.loads.p_set.sum() * n.snapshot_weightings.objective.sum()))

    for carrier in carriers:
        metrics = _carrier_metrics(n, carrier)
        anchor_mw = float(anchor.at[carrier, "capacity_mw_anchor"]) if carrier in anchor.index else np.nan
        delta_pct = np.nan
        if not np.isnan(anchor_mw) and anchor_mw > 0:
            delta_pct = (metrics["capacity_mw_built"] - anchor_mw) / anchor_mw * 100.0
        rows.append(
            {
                "carrier": carrier,
                "capacity_mw_built": metrics["capacity_mw_built"],
                "capacity_mw_anchor": anchor_mw,
                "anchor_delta_pct": delta_pct,
                "bus_count": metrics["bus_count"],
                "generator_count": metrics["generator_count"],
                "bus_load_total_mwh": bus_load_total_mwh,
                "p_min_pu_mean": metrics["p_min_pu_mean"],
                "p_max_pu_mean": metrics["p_max_pu_mean"],
                "extendable_flag": metrics["extendable_flag"],
                "is_load_shedding_safety_valve": False,
            }
        )

    audit = pd.DataFrame(
        rows,
        columns=[
            "carrier",
            "capacity_mw_built",
            "capacity_mw_anchor",
            "anchor_delta_pct",
            "bus_count",
            "generator_count",
            "bus_load_total_mwh",
            "p_min_pu_mean",
            "p_max_pu_mean",
            "extendable_flag",
            "is_load_shedding_safety_valve",
        ],
    )
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(audit_out, index=False)
    logger.info("Wrote audit (%d rows) to %s", len(audit), audit_out)

    ext_audit = _extendable_counts(n)
    ext_audit_out = audit_out.parent / "za_fixed_network_extendable_audit.csv"
    ext_audit.to_csv(ext_audit_out, index=False)
    logger.info("Wrote per-component extendable audit to %s", ext_audit_out)

    failures = []
    bad_extendable = audit[(audit["extendable_flag"]) & (~audit["is_load_shedding_safety_valve"])]
    if len(bad_extendable):
        failures.append(f"unintended extendable capacity in carriers: {bad_extendable['carrier'].tolist()}")

    bad_components = ext_audit[ext_audit["n_extendable"] > 0]
    if len(bad_components):
        failures.append(
            "unintended extendable components: "
            + ", ".join(f"{r.component}={int(r.n_extendable)}" for r in bad_components.itertuples())
        )

    overshoot = audit[
        audit["capacity_mw_anchor"].notna() & (audit["anchor_delta_pct"].abs() > ANCHOR_DELTA_THRESHOLD_PCT)
    ]
    if len(overshoot):
        logger.warning("Anchor delta > %.1f%% for: %s", ANCHOR_DELTA_THRESHOLD_PCT, overshoot[["carrier", "anchor_delta_pct"]].to_dict("records"))

    if failures:
        for f in failures:
            logger.error("GATE FAIL: %s", f)
        return 1
    logger.info("Audit gate PASS")
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
            network_path=Path(snakemake.input.network),
            anchor_path=Path(snakemake.input.anchor),
            audit_out=Path(snakemake.output.audit),
        )
        sys.exit(rc)
    else:
        import argparse

        ap = argparse.ArgumentParser()
        ap.add_argument("--network", default="networks/za_2023_fixed_validation/elec_s_34_ec_lc1_NoCO2-1H.nc")
        ap.add_argument("--anchor", default="data/za_audit/za_eskom_2023_capacity_anchors.csv")
        ap.add_argument("--audit", default="data/za_audit/za_fixed_network_audit.csv")
        args = ap.parse_args()
        sys.exit(main(Path(args.network), Path(args.anchor), Path(args.audit)))
