# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""ZA Module 04 — cost / fuel / emissions audit."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .io import sha256_of_file


def _melt_cost_workbook(path: Path, scenario_set: str, role: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        xl = pd.ExcelFile(path)
    except Exception as exc:  # noqa: BLE001
        return pd.DataFrame([{"scenario_set": scenario_set, "role": role, "rel_path": str(path), "error": str(exc)}])
    out = []
    file_hash = sha256_of_file(path)
    for sheet in xl.sheet_names:
        df = xl.parse(sheet)
        df.insert(0, "scenario_set", scenario_set)
        df.insert(1, "role", role)
        df.insert(2, "sheet", sheet)
        df.insert(3, "source_path", path.name)
        df.insert(4, "source_hash", file_hash)
        out.append(df)
    if not out:
        return pd.DataFrame()
    return pd.concat(out, ignore_index=True, sort=False)


def build_cost_fuel_emissions_audit(pypsa_rsa_root: Path, out_path: Path) -> int:
    base = Path(pypsa_rsa_root)
    workbooks = [
        ("Coal_Flexibilisation", "fuel_prices",   base / "scenarios" / "Coal_Flexibilisation" / "sub_scenarios" / "fuel_prices.xlsx"),
        ("Coal_Flexibilisation", "emissions",     base / "scenarios" / "Coal_Flexibilisation" / "sub_scenarios" / "emissions.xlsx"),
        ("ME IRP 2024",          "fixed_tech",    base / "scenarios" / "ME IRP 2024" / "sub_scenarios" / "fixed_technologies.xlsx"),
        ("ME IRP 2024",          "extendable_tech", base / "scenarios" / "ME IRP 2024" / "sub_scenarios" / "extendable_technologies.xlsx"),
    ]
    frames = [_melt_cost_workbook(p, s, r) for s, r, p in workbooks]
    df = pd.concat([f for f in frames if not f.empty], ignore_index=True, sort=False) if frames else pd.DataFrame()

    # Capture the PyPSA-RSA config + add_electricity reference paths so downstream
    # Module 07 knows where the cost-transformation logic lives.
    extras = [
        {"scenario_set": "_meta", "role": "config_yaml", "rel_path": "config.yaml", "hash": sha256_of_file(base / "config.yaml")},
        {"scenario_set": "_meta", "role": "add_electricity_py", "rel_path": "scripts/add_electricity.py", "hash": sha256_of_file(base / "scripts" / "add_electricity.py")},
    ]
    extra_df = pd.DataFrame(extras)
    if not extra_df.empty:
        df = pd.concat([df, extra_df], ignore_index=True, sort=False)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return len(df)
