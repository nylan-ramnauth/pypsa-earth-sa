# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""ZA Calibration Plan Module 09b — inject custom missing lines into clustered network.

Reads `data/za_audit/za_custom_missing_lines.csv` and adds each row as a Line
to the clustered network `elec_s_34.nc`. Writes a backup `.pre_custom.nc`
before mutating the network in place. Emits an audit CSV listing each added
line with the parameters PyPSA stored (so 400 kV `type`-derived x/r/b are
captured post-hoc).
"""
import logging
import shutil
import sys
from pathlib import Path

import pandas as pd
import pypsa

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("apply_za_custom_lines")

AUDIT_COLUMNS = [
    "name",
    "bus0",
    "bus1",
    "v_nom_kv",
    "length_km",
    "num_parallel",
    "s_nom_built",
    "s_nom_target",
    "x",
    "r",
    "b",
    "type_used",
    "source_note",
    "added_ok",
]


def add_line(n: pypsa.Network, row: pd.Series) -> dict:
    kwargs = dict(
        bus0=row["bus0"],
        bus1=row["bus1"],
        length=float(row["length"]),
        num_parallel=float(row["num_parallel"]),
        s_nom=float(row["s_nom"]),
        s_nom_extendable=False,
        carrier="AC",
    )
    type_raw = row.get("type")
    has_type = pd.notna(type_raw) and str(type_raw).strip() != ""
    if has_type:
        kwargs["type"] = str(type_raw).strip()
    else:
        kwargs["type"] = ""
        kwargs["x"] = float(row["x"])
        kwargs["r"] = float(row["r"])
        kwargs["b"] = float(row["b"])
    n.add("Line", row["name"], **kwargs)
    line = n.lines.loc[row["name"]]
    return {
        "name": row["name"],
        "bus0": row["bus0"],
        "bus1": row["bus1"],
        "v_nom_kv": float(line["v_nom"]),
        "length_km": float(line["length"]),
        "num_parallel": float(line["num_parallel"]),
        "s_nom_built": float(line["s_nom"]),
        "s_nom_target": float(row["s_nom"]),
        "x": float(line["x"]),
        "r": float(line["r"]),
        "b": float(line["b"]),
        "type_used": str(line["type"]),
        "source_note": row.get("source_note", ""),
        "added_ok": abs(float(line["s_nom"]) - float(row["s_nom"])) < 1e-6,
    }


def main(custom_lines_path: Path, network_in: Path, backup_out: Path, audit_out: Path) -> None:
    custom = pd.read_csv(custom_lines_path)
    logger.info("Loaded %d custom lines from %s", len(custom), custom_lines_path)

    # Backup current network before mutation.
    backup_out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(network_in, backup_out)
    logger.info("Backed up %s -> %s", network_in, backup_out)

    if custom.empty:
        audit_out.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=AUDIT_COLUMNS).to_csv(audit_out, index=False)
        logger.info("No custom lines requested; wrote empty audit to %s", audit_out)
        return

    n = pypsa.Network(str(network_in))
    prior = len(n.lines)

    audit_rows = []
    for _, row in custom.iterrows():
        if row["bus0"] not in n.buses.index or row["bus1"] not in n.buses.index:
            raise SystemExit(f"Bus missing in network for line {row['name']}: {row['bus0']} / {row['bus1']}")
        if row["name"] in n.lines.index:
            logger.warning("Line %s already present; skipping", row["name"])
            continue
        audit_rows.append(add_line(n, row))

    assert len(n.lines) == prior + len(audit_rows), f"Line count drift: {prior} -> {len(n.lines)}"
    logger.info("Added %d lines; total now %d", len(audit_rows), len(n.lines))

    n.export_to_netcdf(str(network_in))
    logger.info("Saved patched network to %s", network_in)

    audit = pd.DataFrame(audit_rows, columns=AUDIT_COLUMNS)
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(audit_out, index=False)
    logger.info("Wrote audit (%d rows) to %s", len(audit), audit_out)
    bad = audit.loc[~audit["added_ok"]]
    if len(bad) > 0:
        raise SystemExit(f"Audit failures: {bad}")


if __name__ == "__main__":
    if "snakemake" in globals():
        snakemake = globals()["snakemake"]
        log_path = Path(snakemake.log[0])
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(log_path), mode="w")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logging.getLogger().addHandler(fh)
        main(
            custom_lines_path=Path(snakemake.input.custom_lines),
            network_in=Path(snakemake.input.network_in),
            backup_out=Path(snakemake.output.backup),
            audit_out=Path(snakemake.output.audit),
        )
    else:
        import argparse

        ap = argparse.ArgumentParser()
        ap.add_argument("--custom", default="data/za_audit/za_custom_missing_lines.csv")
        ap.add_argument("--network", default="networks/za_2023_fixed_validation/elec_s_34.nc")
        ap.add_argument("--backup", default="networks/za_2023_fixed_validation/elec_s_34.pre_custom.nc")
        ap.add_argument("--audit", default="data/za_audit/za_custom_lines_audit.csv")
        args = ap.parse_args()
        main(Path(args.custom), Path(args.network), Path(args.backup), Path(args.audit))
