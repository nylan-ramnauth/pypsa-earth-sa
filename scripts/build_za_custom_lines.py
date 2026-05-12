# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""ZA Calibration Plan Module 09b — build custom missing transmission lines.

Reads the OSM-vs-StClair comparison and produces a CSV of corridors that have
St Clair N-1 ratings but no OSM line representation. Output feeds
`apply_za_custom_lines` which injects them into the clustered network
`elec_s_34.nc` so module 11 sees the full RSA transmission topology.

All corridors compute x/r/b directly from per-km values and persist them on
the Line component (no `type` lookup). PyPSA's `calculate_dependent_values`
only derives impedance from `type` at runtime using bus `v_nom` — post-cluster
buses do not carry a voltage tag reliably, so the persisted `x, r, b` columns
would remain zero on disk and the lines would behave as zero-impedance shunts
in any solver that does not re-call `calculate_dependent_values` before solve.

400 kV corridors use PyPSA standard `Al/St 240/40 4-bundle 380.0` per-km values
(matches the existing clustered-network 380 kV lines):
    r = 0.030 ohm/km, x = 0.246 ohm/km, c = 13.8 nF/km
    -> b = 2*pi*50*c = 4.335e-6 S/km

275 kV corridors have no exact standard in PyPSA's line_types catalog. Hand-
override using representative single-circuit 275 kV values:
    x = 0.32 ohm/km, r = 0.034 ohm/km, b = 3.6e-6 S/km
Impedance scales with length / num_parallel; capacitance with length * num_parallel.
"""
import logging
import math
import sys
from pathlib import Path

import pandas as pd
import pypsa

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("build_za_custom_lines")

# Per-km parameters. 400 kV values match PyPSA standard `Al/St 240/40 4-bundle 380.0`
# (n.line_types.loc['Al/St 240/40 4-bundle 380.0']); b derived from c_per_length × 2pi*f.
P_400KV = {"x_per_km": 0.246, "r_per_km": 0.030, "b_per_km": 4.335e-6, "v_nom": 380.0}
P_275KV = {"x_per_km": 0.32,  "r_per_km": 0.034, "b_per_km": 3.6e-6,   "v_nom": 275.0}
CUSTOM_LINE_COLUMNS = [
    "name",
    "bus0",
    "bus1",
    "v_nom",
    "type",
    "x",
    "r",
    "b",
    "length",
    "num_parallel",
    "s_nom",
    "s_nom_extendable",
    "carrier",
    "source_note",
]


def haversine_km(lon0: float, lat0: float, lon1: float, lat1: float) -> float:
    r_earth = 6371.0
    p0, p1 = math.radians(lat0), math.radians(lat1)
    dphi = math.radians(lat1 - lat0)
    dlam = math.radians(lon1 - lon0)
    a = math.sin(dphi / 2) ** 2 + math.cos(p0) * math.cos(p1) * math.sin(dlam / 2) ** 2
    return 2 * r_earth * math.asin(math.sqrt(a))


def load_unmatched(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    mask = df["notes"].fillna("") == "no_osm_lines_found"
    unmatched = df.loc[mask].copy()
    if unmatched.empty:
        logger.info("No 'no_osm_lines_found' rows in %s; emitting empty custom-line artifact", path)
        return pd.DataFrame(columns=["bus0", "bus1", "voltage_kv", "st_clair_n1_mw", "n_circuits"])
    unmatched = unmatched.rename(columns={"n_lines": "n_circuits", "voltage_max_kv": "voltage_kv"})
    logger.info("Loaded %d unmatched corridors from %s", len(unmatched), path)
    return unmatched[["bus0", "bus1", "voltage_kv", "st_clair_n1_mw", "n_circuits"]].reset_index(drop=True)


def load_bus_coords(network_path: Path) -> pd.DataFrame:
    n = pypsa.Network(str(network_path))
    return n.buses[["x", "y"]].copy()


def derive_line_params(voltage_kv: int, length_km: float, num_parallel: int) -> dict:
    if voltage_kv == 400:
        p = P_400KV
        source = "pypsa_standard_400kV_4bundle_380_per_km"
    elif voltage_kv == 275:
        p = P_275KV
        source = "hand_override_275kV_singlecircuit"
    else:
        raise SystemExit(f"Unsupported voltage_kv={voltage_kv}; only 275 and 400 supported")
    return {
        "v_nom": p["v_nom"],
        "type": "",
        "x": p["x_per_km"] * length_km / num_parallel,
        "r": p["r_per_km"] * length_km / num_parallel,
        "b": p["b_per_km"] * length_km * num_parallel,
        "params_source": source,
    }


def build_custom_lines_df(unmatched: pd.DataFrame, buses: pd.DataFrame) -> pd.DataFrame:
    if unmatched.empty:
        return pd.DataFrame(columns=CUSTOM_LINE_COLUMNS)

    missing_buses = set()
    for col in ("bus0", "bus1"):
        missing_buses |= set(unmatched[col]) - set(buses.index)
    if missing_buses:
        raise SystemExit(f"Bus names not present in clustered network: {sorted(missing_buses)}")

    rows = []
    for _, r in unmatched.iterrows():
        b0, b1 = r["bus0"], r["bus1"]
        v = int(r["voltage_kv"])
        s_nom = float(r["st_clair_n1_mw"])
        n_circ = int(r["n_circuits"])
        length = haversine_km(buses.at[b0, "x"], buses.at[b0, "y"], buses.at[b1, "x"], buses.at[b1, "y"])
        params = derive_line_params(v, length, n_circ)
        rows.append(
            {
                "name": f"ZA_custom_{b0}_{b1}_{v}kV",
                "bus0": b0,
                "bus1": b1,
                "v_nom": params["v_nom"],
                "type": params["type"],
                "x": params["x"],
                "r": params["r"],
                "b": params["b"],
                "length": length,
                "num_parallel": float(n_circ),
                "s_nom": s_nom,
                "s_nom_extendable": False,
                "carrier": "AC",
                "source_note": params["params_source"],
            }
        )
    return pd.DataFrame(rows, columns=CUSTOM_LINE_COLUMNS)


def main(unmatched_path: Path, network_path: Path, out_path: Path) -> None:
    unmatched = load_unmatched(unmatched_path)
    buses = pd.DataFrame(columns=["x", "y"]) if unmatched.empty else load_bus_coords(network_path)
    df = build_custom_lines_df(unmatched, buses)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    total_s_nom = float(df["s_nom"].sum()) if "s_nom" in df.columns else 0.0
    logger.info("Wrote %d custom lines to %s (total s_nom = %.1f MW)", len(df), out_path, total_s_nom)


if __name__ == "__main__":
    if "snakemake" in globals():
        snakemake = globals()["snakemake"]
        log_path = Path(snakemake.log[0])
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(log_path), mode="w")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logging.getLogger().addHandler(fh)
        main(
            unmatched_path=Path(snakemake.input.unmatched),
            network_path=Path(snakemake.input.network),
            out_path=Path(snakemake.output.custom_lines),
        )
    else:
        import argparse

        ap = argparse.ArgumentParser()
        ap.add_argument("--unmatched", default="data/za_audit/za_osm_vs_stclair_ratings_comparison.csv")
        ap.add_argument("--network", default="networks/za_2023_fixed_validation/elec_s_34.nc")
        ap.add_argument("--out", default="data/za_audit/za_custom_missing_lines.csv")
        args = ap.parse_args()
        main(Path(args.unmatched), Path(args.network), Path(args.out))
