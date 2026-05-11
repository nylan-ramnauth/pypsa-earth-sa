# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Module 07 — Costs, Fuels, Efficiencies, and CoUE builder.

Dual-mode CLI / Snakemake entry point. Produces:

- ``data/za_audit/za_costs_fuels_efficiencies_audit.csv``
- ``data/za_audit/za_local_carrier_cost_rows.csv``
- ``data/za_audit/za_eur_zar_fxrate_2023.csv``
- ``data/za_audit/za_cols_reference_values.csv``
- ``doc/za_costs_fuels_efficiencies_and_coUE.md``
- appended rows in ``data/za_audit/source_hashes.csv`` and
  ``data/za_audit/input_file_manifest.csv``

Usage:
    snakemake --configfile configs/za/za_2023_fixed_validation.yaml build_za_costs_fuels_efficiencies

or directly:
    python scripts/build_za_costs_fuels_efficiencies.py --configfile configs/za/za_2023_fixed_validation.yaml
"""

import argparse
import csv
import datetime as dt
import logging
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from za_audits.io import sha256_of_file  # noqa: E402
from za_costs.audit_builder import build_audit_rows, write_audit_csv  # noqa: E402
from za_costs.fxrate import (  # noqa: E402
    EUROFXREF_HIST_URL,
    base_year_eur_zar,
    fetch_2023_eur_zar,
    write_fxrate_csv,
    _fetch_archive,
)
from za_costs.local_rows import (  # noqa: E402
    build_cols_reference_rows,
    build_local_rows,
    write_cols_reference_csv,
    write_local_rows_csv,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("build_za_costs_fuels_efficiencies")

DATA_AUDIT = Path("data/za_audit")
COST_AUDIT_CSV = DATA_AUDIT / "pypsa_rsa_cost_fuel_emissions_audit.csv"
COSTS_2030_CSV = Path("data/costs_2030.csv")
AUDIT_OUT = DATA_AUDIT / "za_costs_fuels_efficiencies_audit.csv"
LOCAL_ROWS_OUT = DATA_AUDIT / "za_local_carrier_cost_rows.csv"
FXRATE_OUT = DATA_AUDIT / "za_eur_zar_fxrate_2023.csv"
COLS_REFS_OUT = DATA_AUDIT / "za_cols_reference_values.csv"
DOC_OUT = Path("doc/za_costs_fuels_efficiencies_and_coUE.md")
SOURCE_HASHES = DATA_AUDIT / "source_hashes.csv"
INPUT_MANIFEST = DATA_AUDIT / "input_file_manifest.csv"


def _load_config(configfile: Path) -> dict:
    with open(configfile, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M local")


def _upsert_csv(path: Path, key_column: str, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = pd.read_csv(path, dtype=str)
        if key_column in existing.columns:
            remove_keys = {str(row[key_column]) for row in rows}
            existing = existing.loc[~existing[key_column].isin(remove_keys)]
        else:
            existing = pd.DataFrame(columns=columns)
    else:
        existing = pd.DataFrame(columns=columns)
    out = pd.concat([existing, pd.DataFrame(rows)], ignore_index=True)
    out = out.reindex(columns=columns)
    out.to_csv(path, index=False)


def _record_provenance(fx_archive_sha256: str) -> None:
    now = _now()
    artifacts = [
        ("za-costs-builder-script",                "script",   Path("scripts/build_za_costs_fuels_efficiencies.py"), "Module 07 builder"),
        ("za-costs-package-fxrate",                "script",   Path("scripts/za_costs/fxrate.py"),                   "Module 07 FX helper"),
        ("za-costs-package-currency",              "script",   Path("scripts/za_costs/currency.py"),                 "Module 07 currency helper"),
        ("za-costs-package-audit-builder",         "script",   Path("scripts/za_costs/audit_builder.py"),            "Module 07 audit builder"),
        ("za-costs-package-local-rows",            "script",   Path("scripts/za_costs/local_rows.py"),               "Module 07 local rows + CoLS refs"),
        ("za-costs-fuels-efficiencies-audit",      "csv",      AUDIT_OUT,                                            "Module 07 cost/fuel/emissions audit"),
        ("za-local-carrier-cost-rows",             "csv",      LOCAL_ROWS_OUT,                                       "Module 07 sidecar consumed by Module 10 apply_za_local_carriers"),
        ("za-eur-zar-fxrate-2023",                 "csv",      FXRATE_OUT,                                           "Module 07 frozen 2023 EUR/ZAR rate"),
        ("za-cols-reference-values",               "csv",      COLS_REFS_OUT,                                        "Module 07 policy CoLS reference values"),
        ("za-costs-fuels-efficiencies-doc",        "markdown", DOC_OUT,                                              "Module 07 canonical doc"),
        ("eurofxref-hist-zip",                     "url",      EUROFXREF_HIST_URL,                                   "Module 07 FX source archive"),
    ]
    hash_rows = []
    manifest_rows = []
    for sid, typ, path, notes in artifacts:
        if isinstance(path, str) and path.startswith("http"):
            h = fx_archive_sha256
            status = "fetched"
        elif isinstance(path, Path):
            h = sha256_of_file(path) if path.exists() else ""
            status = "present" if path.exists() else "missing"
        else:
            h = ""
            status = "unknown"
        hash_rows.append({
            "source_id": sid,
            "source_type": typ,
            "path_or_url": str(path),
            "hash_algorithm": "sha256",
            "hash": h,
            "commit_or_version": "",
            "recorded_at": now,
            "notes": notes,
        })
        manifest_rows.append({
            "artifact_id": sid,
            "artifact_type": typ,
            "path": str(path),
            "status": status,
            "sha256": h,
            "source_commit_or_version": "",
            "recorded_at": now,
            "notes": notes,
        })
    _upsert_csv(
        SOURCE_HASHES,
        "source_id",
        hash_rows,
        ["source_id", "source_type", "path_or_url", "hash_algorithm", "hash", "commit_or_version", "recorded_at", "notes"],
    )
    _upsert_csv(
        INPUT_MANIFEST,
        "artifact_id",
        manifest_rows,
        ["artifact_id", "artifact_type", "path", "status", "sha256", "source_commit_or_version", "recorded_at", "notes"],
    )


def _write_doc(
    audit_count: int,
    local_count: int,
    fx_row,
    cols_refs: list[dict],
    rate_rsa_base_year_value: float,
) -> None:
    text = f"""# ZA Costs, Fuels, Efficiencies, and CoUE

Module 07 locks dispatch-cost inputs — fuel prices, heat rates, VOM/FOM,
emissions factors, lifetimes, and load-shedding cost — for the 2023 fixed-
capacity validation baseline before Module 10 (network build) and Module 11
(dispatch calibration).

## Cost Source Policy

- Upstream PyPSA-Earth `costs.year` locked to **2030** because the repo
  ships `data/costs.csv`, `data/costs_2025.csv`, and `data/costs_2030.csv`
  but no `costs_2023.csv`. This is a known V1 limitation reported by
  Module 12.
- PyPSA-Earth/technology-data defaults are used where the carrier maps
  cleanly. PyPSA-RSA values from the Module 04 audit override defaults for
  ZA local carriers (`sasol_coal`, `sasol_gas`, `ocgt_diesel`, `ocgt_gas`,
  `other_re`) and are recorded for the other V1 carriers as evidence.
- PyPSA-RSA workbooks themselves are NOT re-parsed in this module — the
  Module 04 audit CSV (`pypsa_rsa_cost_fuel_emissions_audit.csv`) is the
  only allowed source.

## Currency Mechanics

- **Solver internal unit: EUR/MWh** (upstream contract; not changed).
- **Frozen 2023 EUR/ZAR rate:** `{fx_row.eur_zar_rate:.4f}` ZAR per 1 EUR
  on `{fx_row.date}`.
- **Source:** {fx_row.source_url} (member `{fx_row.archive_member}`,
  SHA256 `{fx_row.archive_sha256}`).
- **PyPSA-RSA base-year rate ({2018}):** `{rate_rsa_base_year_value:.4f}`
  ZAR per 1 EUR. Used to convert all PyPSA-RSA-sourced ZAR values to EUR
  for solver-internal use.
- **Reporting output:** Module 10's `apply_za_local_carriers` hook will
  re-convert EUR solver outputs to ZAR using the 2023 frozen rate before
  writing validation CSVs. The helper `scripts/za_costs/currency.py`
  exports `eur_to_zar` and `zar_to_eur` for that consumer.

## Cost of Load Shedding (CoLS)

Two distinct frames exist; they must not be confused.

### 1. Solver safety-valve marginal cost

Value: `solving.options.load_shedding: 100` (EUR/kWh). The solver code
`scripts/solve_network.py:161` multiplies by 1000, so the safety-valve
marginal cost is **100,000 EUR/MWh**. This is a numerical sentinel that
keeps the solver from shedding load except where physically unavoidable;
it is intentionally extreme (about 200x the Nova CoLS and 17x the CSIR
CoLS). Module 07 does not change this value.

### 2. Policy CoLS for reporting + reliability handoff

Recorded in `data/za_audit/za_cols_reference_values.csv` with three rows
(CSIR primary, Nova lower-sensitivity, Deloitte historical). Module 12
validation reports must present load-shedding costs in both frames.

## electricity_grid_connection Decision

Upstream PyPSA-Earth PR `f8eab87a` added a per-generator grid-connection
cost. **Decision for ZA overlay: disable** — set
`costs.electricity_grid_connection: 0` in
`configs/za/za_2023_fixed_validation.yaml`. Rationale: Module 08 reconciles
full per-plant capex through `custom_powerplants.csv`, including grid-
connection components. Applying the upstream formula again would
double-count.

## Local Carrier Hook Boundary

Module 07 produces the data sidecar `za_local_carrier_cost_rows.csv` and
the importable EUR/ZAR helper. The `apply_za_local_carriers` hook itself —
which inserts these rows into the PyPSA network after `add_electricity` —
is implemented by Module 10. See `scripts/za_costs/currency.py` for the
EUR-to-ZAR helper that Module 10 imports.

## Artifacts

- `{AUDIT_OUT}` — {audit_count} rows
- `{LOCAL_ROWS_OUT}` — {local_count} rows ({{sasol_coal, sasol_gas, ocgt_diesel, ocgt_gas, other_re}})
- `{FXRATE_OUT}` — 1 row
- `{COLS_REFS_OUT}` — {len(cols_refs)} rows ({{CSIR, Nova, Deloitte}})

## V1 Limitations (recorded for Module 12)

- `costs.year: 2030` (no `costs_2023.csv` upstream).
- `other_re` is an aggregate Eskom category; CO2 emissions factor = 0
  under biogenic-neutral V1 accounting; the aggregate-category limitation
  must be flagged in reporting metadata.
- PyPSA-RSA fuel-price base year is treated as **2018 ZAR** for the
  ME_IRP23 scenario set; Module 12 should sensitivity-check.
- Capital cost is left blank in the local-carrier sidecar; Module 08 owns
  per-plant capex reconciliation through `custom_powerplants.csv`.
"""
    DOC_OUT.parent.mkdir(parents=True, exist_ok=True)
    DOC_OUT.write_text(text, encoding="utf-8")


def _run(config: dict) -> int:
    DATA_AUDIT.mkdir(parents=True, exist_ok=True)

    # 1) Fetch + freeze 2023 EUR/ZAR + open the archive once for base-year lookups.
    logger.info("Fetching EUR/ZAR archive %s", EUROFXREF_HIST_URL)
    raw_zip, archive_sha = _fetch_archive(EUROFXREF_HIST_URL)
    fx_row = fetch_2023_eur_zar(EUROFXREF_HIST_URL)
    logger.info("Frozen 2023 EUR/ZAR = %.4f (%s)", fx_row.eur_zar_rate, fx_row.date)
    write_fxrate_csv(fx_row, FXRATE_OUT)

    def rate_lookup(year: int) -> float:
        return base_year_eur_zar(year, archive_zip=raw_zip)

    rate_rsa = rate_lookup(2018)

    # 2) Audit hashes for provenance.
    cost_audit_hash = sha256_of_file(COST_AUDIT_CSV) if COST_AUDIT_CSV.exists() else ""
    costs_csv_hash = sha256_of_file(COSTS_2030_CSV) if COSTS_2030_CSV.exists() else ""

    # 3) Audit rows.
    audit_rows = build_audit_rows(
        audit_csv=COST_AUDIT_CSV,
        costs_csv=COSTS_2030_CSV,
        rate_2023_eur_zar=fx_row.eur_zar_rate,
        base_year_rate_lookup=rate_lookup,
        cost_audit_hash=cost_audit_hash,
        costs_csv_hash=costs_csv_hash,
    )
    audit_count = write_audit_csv(audit_rows, AUDIT_OUT)
    logger.info("Audit CSV: %d rows", audit_count)

    # 4) Local-carrier sidecar rows.
    local_rows = build_local_rows(
        audit_csv=COST_AUDIT_CSV,
        cost_audit_hash=cost_audit_hash,
        za_local_carriers_cfg=config.get("za_local_carriers", {}) or {},
        rate_rsa_eur_zar=rate_rsa,
    )
    local_count = write_local_rows_csv(local_rows, LOCAL_ROWS_OUT)
    logger.info("Local rows CSV: %d rows", local_count)

    # 5) CoLS reference values (CSIR + Nova + Deloitte).
    cols_rows = build_cols_reference_rows(rate_lookup)
    write_cols_reference_csv(cols_rows, COLS_REFS_OUT)
    logger.info("CoLS reference values: %d rows", len(cols_rows))

    # 6) Canonical doc.
    _write_doc(audit_count, local_count, fx_row, cols_rows, rate_rsa)

    # 7) Provenance append.
    _record_provenance(fx_archive_sha256=archive_sha)

    print({
        "audit": audit_count,
        "local_rows": local_count,
        "cols_refs": len(cols_rows),
        "fxrate": 1,
        "rate_2023": fx_row.eur_zar_rate,
        "rate_2018": rate_rsa,
    })
    return 0


def _main_from_snakemake() -> int:
    snakemake = globals().get("snakemake", None)
    if snakemake is None:
        return 2
    return _run(dict(snakemake.config))


if "snakemake" in globals():
    raise SystemExit(_main_from_snakemake())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--configfile", required=True, type=Path)
    args = parser.parse_args()
    raise SystemExit(_run(_load_config(args.configfile)))
