# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Emit `za_local_carrier_cost_rows.csv` consumed by Module 10's
`apply_za_local_carriers` hook.

One row per ZA local carrier (`sasol_coal`, `sasol_gas`, `ocgt_diesel`,
`ocgt_gas`, `other_re`). Marginal cost is computed in EUR/MWh as

    marginal_cost = fuel_price_eur_per_gj * heat_rate_gj_per_mwh + VOM_eur_per_mwh

using PyPSA-RSA medians from the Module 04 audit. CO2 emissions are recorded
in tCO2/MWh (converted from kgCO2/MWh). Capital cost is left blank for the
2023 fixed-validation baseline — Module 08 owns plant-by-plant capex
reconciliation through `custom_powerplants.csv`. The
``pypsa_earth_default_retained_reason`` column is filled when a PyPSA-Earth
default has been kept instead of an audited PyPSA-RSA value.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .audit_builder import V1_TO_RSA, PYPSA_RSA_BASE_YEAR, _fixed_tech_carrier_median, _rsa_fuel_price_2023

LOCAL_CARRIERS = ["sasol_coal", "sasol_gas", "ocgt_diesel", "ocgt_gas", "other_re"]

LOCAL_ROW_COLUMNS = [
    "carrier",
    "capital_cost",
    "marginal_cost",
    "fuel_price",
    "efficiency",
    "heat_rate",
    "co2_emissions",
    "lifetime",
    "color",
    "nice_name",
    "validation_target",
    "units_currency",
    "units_quantity",
    "source",
    "source_path",
    "source_hash",
    "base_year",
    "pypsa_earth_default_retained_reason",
    "notes",
]


def build_local_rows(
    audit_csv: Path,
    cost_audit_hash: str,
    za_local_carriers_cfg: dict,
    rate_rsa_eur_zar: float,
) -> list[dict]:
    df = pd.read_csv(audit_csv, low_memory=False)
    rows: list[dict] = []

    for carrier in LOCAL_CARRIERS:
        meta = za_local_carriers_cfg.get(carrier, {}) or {}
        color = meta.get("color", "")
        nice_name = meta.get("nice_name", "")
        validation_target = meta.get("validation_target", "")

        if carrier == "other_re":
            rows.append({
                "carrier": "other_re",
                "capital_cost": "",
                "marginal_cost": 0.0,
                "fuel_price": 0.0,
                "efficiency": "",
                "heat_rate": "",
                "co2_emissions": 0.0,
                "lifetime": "",
                "color": color,
                "nice_name": nice_name,
                "validation_target": validation_target,
                "units_currency": "EUR/MWh",
                "units_quantity": "tCO2/MWh",
                "source": "za_v1_policy",
                "source_path": "doc/active/calibration-plan/07_costs_fuels_efficiencies_and_coUE.md",
                "source_hash": "",
                "base_year": 2023,
                "pypsa_earth_default_retained_reason": "",
                "notes": (
                    "zero-cost fixed exogenous accounting; biogenic-neutral CO2; "
                    "aggregate-category (Eskom Other RE) — reporting metadata must flag this"
                ),
            })
            continue

        rsa_carriers = V1_TO_RSA[carrier]
        med = _fixed_tech_carrier_median(df, rsa_carriers)
        fp_zar, fp_src = _rsa_fuel_price_2023(df, rsa_carriers)

        heat_rate = float(med.get("Heat Rate (GJ/MWh)")) if "Heat Rate (GJ/MWh)" in med.index else None
        co2_kg_mwh = float(med.get("CO2 Emissions (kgCO2/MWh)")) if "CO2 Emissions (kgCO2/MWh)" in med.index else None
        vom_zar = float(med.get("Variable O&M Cost (R/MWh)")) if "Variable O&M Cost (R/MWh)" in med.index else None
        src_path = str(med.get("_source_path", "")) if not med.empty else ""

        # Fallback: PyPSA-RSA `fuel_prices` role uses station-key labels that
        # do not include Sasol stations. Fixed_tech rows carry per-plant
        # `Fuel Price (R/GJ)` — fall back to that when fuel_prices misses.
        if fp_zar is None and "Fuel Price (R/GJ)" in med.index:
            fp_zar = float(med["Fuel Price (R/GJ)"])
            fp_src = src_path

        # Marginal cost computation in EUR/MWh.
        fp_eur_per_gj = (fp_zar / rate_rsa_eur_zar) if (fp_zar is not None and rate_rsa_eur_zar) else None
        vom_eur = (vom_zar / rate_rsa_eur_zar) if (vom_zar is not None and rate_rsa_eur_zar) else None
        marginal_cost = None
        if fp_eur_per_gj is not None and heat_rate is not None:
            marginal_cost = fp_eur_per_gj * heat_rate + (vom_eur or 0.0)

        # Efficiency = 3.6 / heat_rate (GJ/MWh → 1/per_unit electrical efficiency on LHV).
        efficiency = (3.6 / heat_rate) if (heat_rate and heat_rate > 0) else None

        co2_t_per_mwh = (co2_kg_mwh / 1000.0) if co2_kg_mwh is not None else None

        retained_reason = ""
        if fp_zar is None:
            retained_reason = (
                f"PyPSA-RSA fuel_price missing for {carrier} in 2023 column; "
                "marginal_cost left blank — module 11 must address before dispatch validation"
            )

        rows.append({
            "carrier": carrier,
            "capital_cost": "",  # Module 08 owns per-plant capex; no fleet capital row here
            "marginal_cost": marginal_cost if marginal_cost is not None else "",
            "fuel_price": fp_zar if fp_zar is not None else "",
            "efficiency": efficiency if efficiency is not None else "",
            "heat_rate": heat_rate if heat_rate is not None else "",
            "co2_emissions": co2_t_per_mwh if co2_t_per_mwh is not None else "",
            "lifetime": "",  # not used by V1 fixed-validation
            "color": color,
            "nice_name": nice_name,
            "validation_target": validation_target,
            "units_currency": "EUR/MWh",
            "units_quantity": "tCO2/MWh; heat_rate GJ/MWh; fuel_price R/GJ",
            "source": "pypsa_rsa",
            "source_path": src_path or fp_src,
            "source_hash": cost_audit_hash,
            "base_year": PYPSA_RSA_BASE_YEAR,
            "pypsa_earth_default_retained_reason": retained_reason,
            "notes": (
                "marginal_cost = (fuel_price R/GJ ÷ base-year EUR/ZAR rate) × heat_rate + VOM_eur; "
                "capital_cost left blank — Module 08 owns custom_powerplants capex"
            ),
        })

    return rows


def write_local_rows_csv(rows: list[dict], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=LOCAL_ROW_COLUMNS)
    df.to_csv(out_path, index=False, float_format="%.9f")
    return len(df)


COLS_REFERENCE_ROWS = [
    {
        "source_label": "CSIR",
        "base_year": 2024,
        "value_zar_per_mwh": 116570.0,
        "source_doc": "3-wiki/reference/web-clips/2026-05-07-fti-consulting-out-of-darkness-economic-costs.md",
        "frame": "policy_primary",
        "note": "CSIR Utility-scale power generation statistics in South Africa 2024; cited by FTI Consulting and National Treasury",
    },
    {
        "source_label": "Nova_Economics",
        "base_year": 2019,
        "value_zar_per_mwh": 9530.0,
        "source_doc": "3-wiki/reference/web-clips/2026-05-07-nova-economics-cost-of-load-shedding-sa.md",
        "frame": "policy_lower_sensitivity",
        "note": "Nova Economics, commissioned by Eskom, c. 2020; GDP-loss only",
    },
    {
        "source_label": "Deloitte_Eskom_2009",
        "base_year": 2009,
        "value_zar_per_mwh": 8950.0,
        "source_doc": "",
        "frame": "historical_reference",
        "note": "Deloitte 2009 study for Eskom; historical reference only",
    },
]


def build_cols_reference_rows(rate_lookup) -> list[dict]:
    """Convert the three policy CoLS reference values to EUR using each row's base-year rate."""
    out: list[dict] = []
    for row in COLS_REFERENCE_ROWS:
        rate = rate_lookup(row["base_year"])
        out.append({
            **row,
            "value_eur_per_mwh": float(row["value_zar_per_mwh"]) / rate,
            "conversion_rate": rate,
        })
    return out


COLS_REFERENCE_COLUMNS = [
    "source_label",
    "base_year",
    "value_zar_per_mwh",
    "value_eur_per_mwh",
    "conversion_rate",
    "source_doc",
    "frame",
    "note",
]


def write_cols_reference_csv(rows: list[dict], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=COLS_REFERENCE_COLUMNS)
    df.to_csv(out_path, index=False, float_format="%.6f")
    return len(df)
