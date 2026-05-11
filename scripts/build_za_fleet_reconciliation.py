# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Module 08 — Fleet Reconciliation And Custom Powerplants builder.

Dual-mode CLI / Snakemake entry point. Produces:

- ``data/custom_powerplants.csv`` (replaces header-only file)
- ``data/za_audit/za_powerplant_reconciliation.csv``
- ``data/za_audit/za_named_plant_inventory.csv``
- ``data/za_audit/za_eskom_2023_capacity_anchors.csv``
- ``data/za_audit/za_phs_storage_hours.csv``
- ``data/za_audit/za_powerplants_normalization_diff.csv``  (pending_smoke until ``build_powerplants`` runs)
- ``doc/za_powerplant_reconciliation.md``
- appended rows in ``data/za_audit/source_hashes.csv`` and
  ``data/za_audit/input_file_manifest.csv``

Usage:
    snakemake --configfile configs/za/za_2023_fixed_validation.yaml build_za_fleet_reconciliation

or directly:
    python scripts/build_za_fleet_reconciliation.py --configfile configs/za/za_2023_fixed_validation.yaml
"""

import argparse
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
from za_fleet.reconciliation import (  # noqa: E402
    build_reconciliation_rows,
    make_unique_names,
    write_reconciliation_csv,
)
from za_fleet.custom_powerplants import (  # noqa: E402
    build_custom_rows,
    write_custom_powerplants_csv,
    write_phs_audit_csv,
)
from za_fleet.named_inventory import (  # noqa: E402
    build_named_inventory_rows,
    cross_check,
    write_named_inventory_csv,
)
from za_fleet.eskom_anchors import build_anchor_rows, write_anchors_csv  # noqa: E402
from za_fleet.normalization_smoke import build_smoke_diff, write_diff_csv  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("build_za_fleet_reconciliation")

DATA = Path("data")
DATA_AUDIT = DATA / "za_audit"
CONFIG_DEFAULT = Path("configs/za/za_2023_fixed_validation.yaml")

# Inputs (audited Module 04 artifacts)
FIXED_TECH_CSV = DATA_AUDIT / "pypsa_rsa_fixed_technologies_2023_candidates.csv"
REIPPPP_WIND_CSV = DATA_AUDIT / "reipppp_wind_2023_candidates.csv"
REIPPPP_SOLAR_CSV = DATA_AUDIT / "reipppp_solar_2023_candidates.csv"
ESKOM_RAW_CSV = DATA_AUDIT / "raw" / "eskom_data_2023_full.csv"
CARRIER_TAXONOMY_CSV = DATA_AUDIT / "za_carrier_taxonomy.csv"

# Outputs
CUSTOM_OUT = DATA / "custom_powerplants.csv"
RECON_OUT = DATA_AUDIT / "za_powerplant_reconciliation.csv"
NAMED_OUT = DATA_AUDIT / "za_named_plant_inventory.csv"
ANCHORS_OUT = DATA_AUDIT / "za_eskom_2023_capacity_anchors.csv"
PHS_OUT = DATA_AUDIT / "za_phs_storage_hours.csv"
DIFF_OUT = DATA_AUDIT / "za_powerplants_normalization_diff.csv"
DOC_OUT = Path("doc/za_powerplant_reconciliation.md")
SOURCE_HASHES = DATA_AUDIT / "source_hashes.csv"
INPUT_MANIFEST = DATA_AUDIT / "input_file_manifest.csv"

# Smoke build expects this path after `snakemake build_powerplants` runs.
def _resources_powerplants_csv(run_name: str) -> Path:
    return Path("resources") / run_name / "powerplants.csv"


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


def _record_provenance(eskom_hash: str, fixed_tech_hash: str, wind_hash: str, solar_hash: str) -> None:
    now = _now()
    artifacts = [
        ("za-fleet-builder-script",     "script",   Path("scripts/build_za_fleet_reconciliation.py"),       "Module 08 builder"),
        ("za-fleet-package-recon",      "script",   Path("scripts/za_fleet/reconciliation.py"),             "Module 08 reconciliation builder"),
        ("za-fleet-package-custom",     "script",   Path("scripts/za_fleet/custom_powerplants.py"),         "Module 08 custom_powerplants emitter"),
        ("za-fleet-package-named",      "script",   Path("scripts/za_fleet/named_inventory.py"),            "Module 08 named-plant inventory + cross-check"),
        ("za-fleet-package-eskom",      "script",   Path("scripts/za_fleet/eskom_anchors.py"),              "Module 08 Eskom 2023 anchor builder"),
        ("za-fleet-package-smoke",      "script",   Path("scripts/za_fleet/normalization_smoke.py"),        "Module 08 normalization smoke diff"),
        ("za-custom-powerplants",       "csv",      CUSTOM_OUT,                                              "Module 08 frozen 2023 ZA fleet (replaces header-only)"),
        ("za-powerplant-reconciliation","csv",      RECON_OUT,                                               "Module 08 reconciliation audit"),
        ("za-named-plant-inventory",    "csv",      NAMED_OUT,                                               "Module 08 canonical Eskom-named station inventory"),
        ("za-eskom-2023-anchors",       "csv",      ANCHORS_OUT,                                             "Module 08 per-carrier installed-capacity anchors from raw hourly"),
        ("za-phs-storage-hours",        "csv",      PHS_OUT,                                                 "Module 08 PHS StorageCapacity_MWh audit"),
        ("za-powerplants-norm-diff",    "csv",      DIFF_OUT,                                                "Module 08 normalization smoke vs resources/powerplants.csv"),
        ("za-fleet-reconciliation-doc", "markdown", DOC_OUT,                                                 "Module 08 canonical doc"),
    ]
    hash_rows = []
    manifest_rows = []
    # Note source inputs explicitly with their computed hashes.
    inputs_meta = [
        ("eskom-2023-raw-hourly",       "csv-input", ESKOM_RAW_CSV,    eskom_hash,      "Eskom 2023 raw hourly (Module 02 staging)"),
        ("pypsa-rsa-fixed-tech-2023",   "csv-input", FIXED_TECH_CSV,   fixed_tech_hash, "PyPSA-RSA fixed_technologies 2023 candidates (Module 04)"),
        ("reipppp-wind-2023",           "csv-input", REIPPPP_WIND_CSV, wind_hash,       "REIPPPP wind 2023 candidates (Module 04)"),
        ("reipppp-solar-2023",          "csv-input", REIPPPP_SOLAR_CSV, solar_hash,     "REIPPPP solar 2023 candidates (Module 04)"),
    ]
    for sid, typ, path, h, notes in inputs_meta:
        hash_rows.append({
            "source_id": sid, "source_type": typ, "path_or_url": str(path),
            "hash_algorithm": "sha256", "hash": h, "commit_or_version": "",
            "recorded_at": now, "notes": notes,
        })
        manifest_rows.append({
            "artifact_id": sid, "artifact_type": typ, "path": str(path),
            "status": "present" if path.exists() else "missing",
            "sha256": h, "source_commit_or_version": "",
            "recorded_at": now, "notes": notes,
        })
    for sid, typ, path, notes in artifacts:
        h = sha256_of_file(path) if isinstance(path, Path) and path.exists() else ""
        status = "present" if isinstance(path, Path) and path.exists() else "missing"
        hash_rows.append({
            "source_id": sid, "source_type": typ, "path_or_url": str(path),
            "hash_algorithm": "sha256", "hash": h, "commit_or_version": "",
            "recorded_at": now, "notes": notes,
        })
        manifest_rows.append({
            "artifact_id": sid, "artifact_type": typ, "path": str(path),
            "status": status, "sha256": h, "source_commit_or_version": "",
            "recorded_at": now, "notes": notes,
        })
    _upsert_csv(
        SOURCE_HASHES, "source_id", hash_rows,
        ["source_id", "source_type", "path_or_url", "hash_algorithm", "hash", "commit_or_version", "recorded_at", "notes"],
    )
    _upsert_csv(
        INPUT_MANIFEST, "artifact_id", manifest_rows,
        ["artifact_id", "artifact_type", "path", "status", "sha256", "source_commit_or_version", "recorded_at", "notes"],
    )


def _write_doc(
    recon_count: int,
    custom_count: int,
    named_count: int,
    failures: list[dict],
    anchors_rows: list[dict],
    custom_rows: list[dict],
    diff_rows: list[dict],
) -> None:
    custom_by_carrier = (
        pd.DataFrame(custom_rows)
        .assign(_cap=lambda d: pd.to_numeric(d["Capacity"], errors="coerce"))
        .groupby("Fueltype")["_cap"].sum().sort_values(ascending=False)
    )
    failure_section = "\n".join(
        f"- **{f['station_name']}**: {f.get('reason','')}  (expected {f.get('expected_mw','?')} MW, "
        f"got {f.get('actual_mw','?')} MW, distance {f.get('distance_km','?')} km)"
        for f in failures
    ) or "_All operating + commissioning named plants reconciled within tolerance._"
    diff_status_counts = (
        pd.DataFrame(diff_rows).get("status", pd.Series(dtype=str)).value_counts().to_dict()
        if diff_rows else {}
    )
    anchor_lines = "\n".join(
        f"- `{r['carrier']}`: max={r['p_nom_mw_2023_max']} MW (source col `{r['source_column']}`)"
        for r in anchors_rows if r.get("available")
    )

    text = f"""# ZA Powerplant Reconciliation — Module 08

Module 08 reconciles the audited 2023-active candidates from Module 04
(PyPSA-RSA `fixed_technologies` BASE scenario, REIPPPP wind, REIPPPP
solar) into a single frozen `data/custom_powerplants.csv` that Module 10
loads under `electricity.custom_powerplants: replace`.

## Sources

- `{FIXED_TECH_CSV}` — PyPSA-RSA fixed_technologies (scenario_set='ME IRP 2024', Scenario='BASE')
- `{REIPPPP_WIND_CSV}` — REIPPPP wind 2023 candidates (`included_2023 == True`)
- `{REIPPPP_SOLAR_CSV}` — REIPPPP solar 2023 candidates (`included_2023 == True`, Type ∈ PV)
- `{ESKOM_RAW_CSV}` — raw hourly Eskom 2023 feed; used to derive per-carrier installed-capacity anchors

## Per-carrier totals (custom_powerplants.csv)

{custom_by_carrier.to_string()}

## Eskom 2023 capacity anchors (informational)

{anchor_lines}

The Eskom hourly feed exposes installed capacity only for renewable carriers
(Wind, PV, CSP, Other RE) plus the aggregate `Installed Eskom Capacity`.
Per-carrier conventional anchors (coal/nuclear/OCGT/Sasol) are NOT available
from the hourly feed and are recorded as `available: False` in
`{ANCHORS_OUT}`. Module 12 must use the Eskom Annual Report 2023 / IRP 2023
for the conventional anchors.

## Required source decisions

### Hex 20 MW battery (PyPSA-RSA `battery_4h` row, COD 2023)
**Decision: include.** Audit flagged `included_2023 == True`. Decommissioning
year = 2038. Documented as the only V1 battery row in the 2023 fleet.

### Redstone Solar Thermal
**Decision: exclude.** DateIn 2024 — outside the 2023 fixed-validation
baseline. Module 13 forward-looking scenarios will reintroduce it.

### PHS — Drakensberg, Ingula, Palmiet, Steenbras
**Decision: include with per-station `StorageCapacity_MWh`.** Module 08
writes `StorageCapacity_MWh` directly into `custom_powerplants.csv`; the
audit `data/za_audit/za_phs_storage_hours.csv` records the source for each
station. The upstream contract at `add_electricity.py:1027` only replaces
`max_hours == 0` with `config.renewable.hydro.PHS_max_hours: 6`, so any
non-zero value survives.

Reference values (used when the Module 04 audit `Max Storage (GWh)` column
is absent for a station):

| Station | p_nom (MW) | max_hours | StorageCapacity_MWh |
|---|---|---|---|
| Drakensberg | 1000 | 24 | 24,000 |
| Ingula      | 1332 | 14 | 18,648 |
| Palmiet     | 400  | 12 | 4,800  |
| Steenbras   | 180  | 20 | 3,600  |

### CSP — six 2023 plants
**Decision: include with `Type=Solar/Technology=CSP`.** KaXu Solar One,
Khi Solar One, Bokpoort, Kathu, Xina Solar One, Ilanga CSP (≈500 MW total).
`StorageCapacity_MWh` left blank — Module 10 owns CSP storage representation
through the `renewable.csp.csp_model` config key. Per-plant
`CSP Storage Hours` are recorded in `za_named_plant_inventory.csv` notes.

### Conventional capacity checks
Coal / Nuclear / OCGT / Sasol totals are recorded in this report and in
`za_powerplant_reconciliation.csv` for cross-check against the Eskom Annual
Report 2023. The hard ≤2% tolerance gate is deferred to Module 12.

## Named-plant gate

Named-plant inventory: {named_count} stations.
Failures (operating + commissioning stations outside ±50 MW / ±10 km
tolerance):

{failure_section}

## Smoke diff status counts

{diff_status_counts}

If any row has `status` other than `ok` or `pending_smoke`, see
`{DIFF_OUT}` for details.

## V1 Limitations (recorded for Module 12)

- Per-carrier conventional anchors are not in the Eskom hourly feed —
  Module 12 must use the Eskom Annual Report 2023 / IRP 2023 instead.
- `bus` column blank in Module 08 — upstream KDTree assigns; Module 09
  finalises explicit substation assignments.
- CSP storage is **not** in `custom_powerplants.csv`; Module 10 owns it
  via `renewable.csp.csp_model`.
- The PyPSA-RSA `Coal_Flexibilisation` scenario set is **not** used; only
  `ME IRP 2024 / BASE` rows are included in the canonical 2023 fleet.

## Artifacts

- `{CUSTOM_OUT}` — {custom_count} rows
- `{RECON_OUT}` — {recon_count} reconciliation rows
- `{NAMED_OUT}` — {named_count} named-plant rows
- `{ANCHORS_OUT}` — {len(anchors_rows)} anchor rows
- `{PHS_OUT}` — PHS storage audit
- `{DIFF_OUT}` — normalization smoke diff
"""
    DOC_OUT.parent.mkdir(parents=True, exist_ok=True)
    DOC_OUT.write_text(text, encoding="utf-8")


def _run(config: dict) -> int:
    DATA_AUDIT.mkdir(parents=True, exist_ok=True)

    eskom_hash = sha256_of_file(ESKOM_RAW_CSV) if ESKOM_RAW_CSV.exists() else ""
    fixed_tech_hash = sha256_of_file(FIXED_TECH_CSV) if FIXED_TECH_CSV.exists() else ""
    wind_hash = sha256_of_file(REIPPPP_WIND_CSV) if REIPPPP_WIND_CSV.exists() else ""
    solar_hash = sha256_of_file(REIPPPP_SOLAR_CSV) if REIPPPP_SOLAR_CSV.exists() else ""

    # 1) Reconciliation rows from RSA + REIPPPP audits.
    logger.info("Building reconciliation rows from Module 04 audits.")
    recon_rows = build_reconciliation_rows(FIXED_TECH_CSV, REIPPPP_WIND_CSV, REIPPPP_SOLAR_CSV)
    recon_rows = make_unique_names(recon_rows)
    recon_count = write_reconciliation_csv(recon_rows, RECON_OUT)
    logger.info("Reconciliation CSV: %d rows", recon_count)

    # 2) Custom powerplants + PHS storage audit.
    custom_rows, phs_audit_rows = build_custom_rows(recon_rows)
    custom_count = write_custom_powerplants_csv(custom_rows, CUSTOM_OUT)
    write_phs_audit_csv(phs_audit_rows, PHS_OUT)
    logger.info("Custom powerplants CSV: %d rows", custom_count)

    # 3) Named-plant inventory.
    named_rows = build_named_inventory_rows()
    named_count = write_named_inventory_csv(named_rows, NAMED_OUT)
    matches, failures = cross_check(named_rows, CUSTOM_OUT)
    logger.info("Named-plant gate: %d matches, %d failures", len(matches), len(failures))

    # 4) Eskom 2023 capacity anchors.
    anchors_rows = build_anchor_rows(ESKOM_RAW_CSV, eskom_hash)
    write_anchors_csv(anchors_rows, ANCHORS_OUT)
    logger.info("Eskom anchors CSV: %d rows", len(anchors_rows))

    # 5) Smoke diff (pending_smoke until build_powerplants runs).
    run_name = (config.get("run") or {}).get("name") or "za_2023_fixed_validation"
    diff_rows = build_smoke_diff(CUSTOM_OUT, _resources_powerplants_csv(run_name))
    write_diff_csv(diff_rows, DIFF_OUT)
    logger.info("Normalization smoke diff: %d rows", len(diff_rows))

    # 6) Canonical doc.
    _write_doc(recon_count, custom_count, named_count, failures, anchors_rows, custom_rows, diff_rows)

    # 7) Provenance.
    _record_provenance(eskom_hash, fixed_tech_hash, wind_hash, solar_hash)

    print({
        "reconciliation": recon_count,
        "custom":         custom_count,
        "named":          named_count,
        "anchors":        len(anchors_rows),
        "phs":            len(phs_audit_rows),
        "diff_rows":      len(diff_rows),
        "named_failures": len(failures),
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
