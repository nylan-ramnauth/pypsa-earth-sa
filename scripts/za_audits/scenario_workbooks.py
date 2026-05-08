# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""ZA Module 04 — PyPSA-RSA scenario workbook inventory."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .io import list_xlsx_sheets, sha256_of_file


SCENARIO_WORKBOOKS = [
    # (rel_path, scenario_set, role)
    ("scenarios/ME IRP 2024/scenarios_to_run.xlsx",                                "ME IRP 2024",        "master"),
    ("scenarios/ME IRP 2024/sub_scenarios/annual_load.xlsx",                       "ME IRP 2024",        "annual_load"),
    ("scenarios/ME IRP 2024/sub_scenarios/carbon_constraints.xlsx",                "ME IRP 2024",        "carbon_constraints"),
    ("scenarios/ME IRP 2024/sub_scenarios/fixed_technologies.xlsx",                "ME IRP 2024",        "fixed_technologies"),
    ("scenarios/ME IRP 2024/sub_scenarios/extendable_technologies.xlsx",           "ME IRP 2024",        "extendable_technologies"),
    ("scenarios/ME IRP 2024/sub_scenarios/operational_constraints.xlsx",           "ME IRP 2024",        "operational_constraints"),
    ("scenarios/ME IRP 2024/sub_scenarios/plant_availability.xlsx",                "ME IRP 2024",        "plant_availability"),
    ("scenarios/ME IRP 2024/sub_scenarios/reserve_margin.xlsx",                    "ME IRP 2024",        "reserve_margin"),
    ("scenarios/ME IRP 2024/sub_scenarios/transmission_expansion.xlsx",            "ME IRP 2024",        "transmission_expansion"),
    ("scenarios/Coal_Flexibilisation/scenarios_to_run.xlsx",                       "Coal_Flexibilisation","master"),
    ("scenarios/Coal_Flexibilisation/sub_scenarios/annual_load.xlsx",              "Coal_Flexibilisation","annual_load"),
    ("scenarios/Coal_Flexibilisation/sub_scenarios/aux_stg_feed.xlsx",             "Coal_Flexibilisation","aux_stg_feed"),
    ("scenarios/Coal_Flexibilisation/sub_scenarios/emissions.xlsx",                "Coal_Flexibilisation","emissions"),
    ("scenarios/Coal_Flexibilisation/sub_scenarios/extendable_technologies.xlsx",  "Coal_Flexibilisation","extendable_technologies"),
    ("scenarios/Coal_Flexibilisation/sub_scenarios/fixed_technologies.xlsx",       "Coal_Flexibilisation","fixed_technologies"),
    ("scenarios/Coal_Flexibilisation/sub_scenarios/fuel_prices.xlsx",              "Coal_Flexibilisation","fuel_prices"),
    ("scenarios/Coal_Flexibilisation/sub_scenarios/operational_constraints.xlsx",  "Coal_Flexibilisation","operational_constraints"),
    ("scenarios/Coal_Flexibilisation/sub_scenarios/phased_decommissioning.xlsx",   "Coal_Flexibilisation","phased_decommissioning"),
    ("scenarios/Coal_Flexibilisation/sub_scenarios/plant_availability.xlsx",       "Coal_Flexibilisation","plant_availability"),
    ("scenarios/Coal_Flexibilisation/sub_scenarios/reserve_margin.xlsx",           "Coal_Flexibilisation","reserve_margin"),
    ("scenarios/Coal_Flexibilisation/sub_scenarios/transmission_expansion.xlsx",   "Coal_Flexibilisation","transmission_expansion"),
    ("scenarios/Coal_Flexibilisation/sub_scenarios/weather.xlsx",                  "Coal_Flexibilisation","weather"),
]


def build_scenario_workbook_inventory(pypsa_rsa_root: Path, out_path: Path) -> int:
    base = Path(pypsa_rsa_root)
    rows: list[dict] = []
    for rel, scenario_set, role in SCENARIO_WORKBOOKS:
        abs_path = base / rel
        if not abs_path.exists():
            rows.append(
                {
                    "scenario_set": scenario_set,
                    "role": role,
                    "rel_path": rel,
                    "sheet": "",
                    "n_rows": -1,
                    "n_cols": -1,
                    "columns": "",
                    "active_scenario_flag": "",
                    "evidence_class": "missing",
                    "hash": "",
                }
            )
            continue
        file_hash = sha256_of_file(abs_path)
        for sheet_info in list_xlsx_sheets(abs_path):
            cols = sheet_info["columns"]
            scen_flag = ""
            for c in cols:
                cl = (c or "").lower()
                if cl in {"run", "active", "include", "enabled", "selected"}:
                    scen_flag = c
                    break
            evidence = "validation" if role in {"plant_availability", "operational_constraints", "reserve_margin"} else (
                "expansion" if role in {"extendable_technologies", "transmission_expansion", "carbon_constraints"} else "baseline"
            )
            rows.append(
                {
                    "scenario_set": scenario_set,
                    "role": role,
                    "rel_path": rel,
                    "sheet": sheet_info["sheet"],
                    "n_rows": sheet_info["n_rows"],
                    "n_cols": sheet_info["n_cols"],
                    "columns": "|".join(cols),
                    "active_scenario_flag": scen_flag,
                    "evidence_class": evidence,
                    "hash": file_hash,
                }
            )
    df = pd.DataFrame(rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return len(df)
