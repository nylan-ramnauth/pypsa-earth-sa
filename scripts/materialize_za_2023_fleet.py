# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Materialise Module 13m 2023 fleet mode artifacts."""

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from za_fleet.fleet_calibration import run_materialisation  # noqa: E402


def _load_config(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def main(
    *,
    config: dict,
    selected_out: Path,
    audit_out: Path,
    backup_manifest: Path,
) -> int:
    result = run_materialisation(
        config=config,
        selected_out=selected_out,
        audit_out=audit_out,
        backup_manifest=backup_manifest,
    )
    print(result)
    return 0


def _main_from_snakemake() -> int:
    sm = globals()["snakemake"]
    return main(
        config=dict(sm.config),
        selected_out=Path(sm.output.selected_custom_powerplants),
        audit_out=Path(sm.output.audit),
        backup_manifest=Path(sm.output.backup_manifest),
    )


def _main_from_cli() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--configfile",
        default=Path("configs/za/za_2023_fixed_validation.yaml"),
        type=Path,
    )
    parser.add_argument(
        "--selected-out",
        default=Path("data/za_validation/custom_powerplants_selected_2023.csv"),
        type=Path,
    )
    parser.add_argument(
        "--audit",
        default=Path("data/za_audit/za_2023_fleet_mode_audit.csv"),
        type=Path,
    )
    parser.add_argument(
        "--backup-manifest",
        default=Path("data/za_audit/custom_powerplants_backup_manifest.csv"),
        type=Path,
    )
    args = parser.parse_args()
    return main(
        config=_load_config(args.configfile),
        selected_out=args.selected_out,
        audit_out=args.audit,
        backup_manifest=args.backup_manifest,
    )


if __name__ == "__main__":
    if "snakemake" in globals():
        raise SystemExit(_main_from_snakemake())
    raise SystemExit(_main_from_cli())
