# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build the canonical Module 07 cost/fuel/emissions audit CSV.

Aggregates Module 04 PyPSA-RSA evidence (`pypsa_rsa_cost_fuel_emissions_audit.csv`)
and the upstream PyPSA-Earth `costs_2030.csv` defaults into a single per-
(carrier, parameter) row table that satisfies the V1 carrier coverage gate.

For every row the table records ZAR value, EUR value, units, base year,
conversion rate + rate base year, source path, and source hash. Rows whose
PyPSA-Earth default is retained instead of a PyPSA-RSA value carry
``source = 'pypsa_earth_default'`` and an explanatory note.

The mapping from V1 carrier → PyPSA-RSA Carrier label is hand-coded here.
Module 05's taxonomy CSV is the lock for which carriers are in scope; this
file is the lock for which fields are audited per carrier.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

# PyPSA-RSA fuel prices are quoted in 2018 ZAR for the ME_IRP23 / BASE scenario
# set (matches the source workbook base year used in Module 04). Cost rows
# pulled from fixed_tech are also referenced to the same base year.
PYPSA_RSA_BASE_YEAR = 2018

# V1 carrier -> RSA Carrier labels in pypsa_rsa_cost_fuel_emissions_audit.csv
V1_TO_RSA: dict[str, list[str]] = {
    "coal":         ["coal"],
    "nuclear":      ["nuclear"],
    "sasol_coal":   ["sasol_coal"],
    "sasol_gas":    ["sasol_gas"],
    "ocgt_diesel":  ["ocgt_diesel"],
    "ocgt_gas":     ["ocgt_gas", "ocgt_avf"],
    "onwind":       ["wind"],
    "solar":        ["solar_pv"],
    "csp":          ["solar_csp"],
    "hydro":        ["hydro"],
    "ror":          [],
    "PHS":          ["phs"],
    "battery":      ["battery_4h"],
    "biomass":      ["bioenergy"],
    "other_re":     [],
    "load_shedding": [],
    "imports":      [],
    "exports":      [],
}

# PyPSA-Earth `costs_2030.csv` technology label per V1 carrier (None if no
# direct upstream row). Used to fall back to upstream defaults.
V1_TO_PYPSA_EARTH: dict[str, str | None] = {
    "coal":          "coal",
    "nuclear":       "nuclear",
    "sasol_coal":    None,
    "sasol_gas":     None,
    "ocgt_diesel":   "OCGT",
    "ocgt_gas":      "OCGT",
    "onwind":        "onwind",
    "solar":         "solar",
    "csp":           "csp-tower",
    "hydro":         "hydro",
    "ror":           "ror",
    "PHS":           "PHS",
    "battery":       "battery storage",
    "biomass":       "biomass",
    "other_re":      None,
    "load_shedding": None,
    "imports":       None,
    "exports":       None,
}

AUDIT_COLUMNS = [
    "carrier",
    "parameter",
    "value_zar",
    "value_eur",
    "units",
    "base_year",
    "source_carrier_in_audit",
    "source_path",
    "source_hash",
    "conversion_eur_zar_rate",
    "conversion_rate_base_year",
    "source",
    "notes",
]


def _rsa_fuel_price_2023(df: pd.DataFrame, station_keys: Iterable[str]) -> tuple[float | None, str]:
    """Return the 2023 R/GJ fuel price for the most representative station entry."""
    fp = df[df["role"] == "fuel_prices"].copy()
    fp["station_name"] = fp["station_name"].astype(str)
    rows = fp[fp["station_name"].isin(list(station_keys))]
    rows = rows[rows["parameter"].astype(str).str.contains("R/GJ|fuel_price", regex=True, na=False)]
    rows = rows.dropna(subset=["2023"])
    if rows.empty:
        return None, ""
    val = float(pd.to_numeric(rows["2023"], errors="coerce").dropna().median())
    sp = str(rows.iloc[0]["source_path"])
    return val, sp


def _fixed_tech_carrier_median(df: pd.DataFrame, rsa_carriers: list[str]) -> pd.Series:
    ft = df[df["role"] == "fixed_tech"].copy()
    ft["Carrier_l"] = ft["Carrier"].astype(str).str.lower()
    keys = {c.lower() for c in rsa_carriers}
    sub = ft[ft["Carrier_l"].isin(keys)]
    if sub.empty:
        return pd.Series(dtype=float)
    numeric_cols = [
        "Heat Rate (GJ/MWh)",
        "CO2 Emissions (kgCO2/MWh)",
        "Fuel Price (R/GJ)",
        "Variable O&M Cost (R/MWh)",
        "Fixed O&M Cost (R/kW/yr)",
        "Round Trip Efficiency (%)",
        "Max Storage (hours)",
    ]
    out: dict[str, float] = {}
    for col in numeric_cols:
        if col in sub.columns:
            vals = pd.to_numeric(sub[col], errors="coerce").dropna()
            if not vals.empty:
                out[col] = float(vals.median())
    out["_source_path"] = str(sub.iloc[0]["source_path"])
    return pd.Series(out)


def _pypsa_earth_param(costs_df: pd.DataFrame, tech: str, parameter: str) -> tuple[float | None, str, int | None]:
    """Return (value, unit, currency_year) from upstream costs CSV. None if missing."""
    sub = costs_df[(costs_df["technology"] == tech) & (costs_df["parameter"] == parameter)]
    if sub.empty:
        return None, "", None
    row = sub.iloc[0]
    val = pd.to_numeric(row.get("value"), errors="coerce")
    if pd.isna(val):
        return None, "", None
    cy = row.get("currency_year")
    cy_int = int(cy) if pd.notna(cy) else None
    return float(val), str(row.get("unit") or ""), cy_int


def _row(
    carrier: str,
    parameter: str,
    *,
    value_zar: float | None,
    value_eur: float | None,
    units: str,
    base_year: int | None,
    source_carrier_in_audit: str,
    source_path: str,
    source_hash: str,
    conversion_eur_zar_rate: float | None,
    conversion_rate_base_year: int | None,
    source: str,
    notes: str = "",
) -> dict:
    return {
        "carrier": carrier,
        "parameter": parameter,
        "value_zar": value_zar,
        "value_eur": value_eur,
        "units": units,
        "base_year": base_year,
        "source_carrier_in_audit": source_carrier_in_audit,
        "source_path": source_path,
        "source_hash": source_hash,
        "conversion_eur_zar_rate": conversion_eur_zar_rate,
        "conversion_rate_base_year": conversion_rate_base_year,
        "source": source,
        "notes": notes,
    }


def build_audit_rows(
    audit_csv: Path,
    costs_csv: Path,
    rate_2023_eur_zar: float,
    base_year_rate_lookup,
    cost_audit_hash: str,
    costs_csv_hash: str,
) -> list[dict]:
    """Compose the full per-(carrier, parameter) audit row set.

    ``base_year_rate_lookup`` is a callable ``year -> float`` returning the
    ECB EUR/ZAR average for that year (used to convert ZAR values whose base
    year differs from 2023).
    """
    df = pd.read_csv(audit_csv, low_memory=False)
    costs = pd.read_csv(costs_csv)

    rate_rsa = base_year_rate_lookup(PYPSA_RSA_BASE_YEAR)
    rows: list[dict] = []

    def add_pe_default(carrier: str, parameter: str, tech: str | None, *, note: str = "") -> None:
        if tech is None:
            return
        value, unit, cy = _pypsa_earth_param(costs, tech, parameter)
        if value is None:
            return
        rows.append(
            _row(
                carrier=carrier,
                parameter=parameter,
                value_zar=None,
                value_eur=value,
                units=unit,
                base_year=cy,
                source_carrier_in_audit=tech,
                source_path=str(costs_csv),
                source_hash=costs_csv_hash,
                conversion_eur_zar_rate=None,
                conversion_rate_base_year=None,
                source="pypsa_earth_default",
                notes=note,
            )
        )

    def add_rsa_zar(
        carrier: str,
        parameter: str,
        value_zar: float | None,
        unit: str,
        source_carrier: str,
        source_path: str,
        note: str = "",
        rate: float | None = None,
        rate_year: int | None = None,
    ) -> None:
        if value_zar is None:
            return
        rate_used = rate if rate is not None else rate_rsa
        ry = rate_year if rate_year is not None else PYPSA_RSA_BASE_YEAR
        value_eur = float(value_zar) / float(rate_used) if rate_used else None
        rows.append(
            _row(
                carrier=carrier,
                parameter=parameter,
                value_zar=float(value_zar),
                value_eur=value_eur,
                units=unit,
                base_year=PYPSA_RSA_BASE_YEAR,
                source_carrier_in_audit=source_carrier,
                source_path=source_path,
                source_hash=cost_audit_hash,
                conversion_eur_zar_rate=float(rate_used) if rate_used else None,
                conversion_rate_base_year=ry,
                source="pypsa_rsa",
                notes=note,
            )
        )

    for v1_carrier in list(V1_TO_RSA.keys()):
        rsa_carriers = V1_TO_RSA[v1_carrier]
        pe_tech = V1_TO_PYPSA_EARTH[v1_carrier]

        # 1) PyPSA-Earth upstream defaults (where applicable).
        for pe_param in ("investment", "FOM", "VOM", "fuel", "efficiency", "lifetime", "CO2 intensity"):
            add_pe_default(v1_carrier, pe_param, pe_tech)

        # 2) PyPSA-RSA fuel price (2023 R/GJ) for fueled carriers.
        fp_val, fp_src = _rsa_fuel_price_2023(df, rsa_carriers)
        if fp_val is not None:
            add_rsa_zar(
                v1_carrier,
                "fuel_price",
                fp_val,
                "R/GJ",
                rsa_carriers[0] if rsa_carriers else "",
                fp_src,
                note="PyPSA-RSA fuel_prices role, 2023 column",
            )

        # 3) PyPSA-RSA fixed_tech median values per carrier (heat rate, CO2,
        #    VOM, FOM, round-trip efficiency, max storage).
        med = _fixed_tech_carrier_median(df, rsa_carriers)
        if not med.empty:
            src_path = str(med.get("_source_path", ""))
            field_map = [
                ("Heat Rate (GJ/MWh)",            "heat_rate",       "GJ/MWh"),
                ("CO2 Emissions (kgCO2/MWh)",     "co2_emissions",   "kgCO2/MWh"),
                ("Variable O&M Cost (R/MWh)",     "VOM_zar",         "R/MWh"),
                ("Fixed O&M Cost (R/kW/yr)",      "FOM_zar",         "R/kW/yr"),
                ("Round Trip Efficiency (%)",     "round_trip_efficiency", "%"),
                ("Max Storage (hours)",           "max_storage_hours", "hours"),
            ]
            for col, param, unit in field_map:
                if col not in med.index:
                    continue
                value = float(med[col])
                if param in {"heat_rate", "co2_emissions", "round_trip_efficiency", "max_storage_hours"}:
                    # Non-currency values: record as `value_zar` placeholder is None;
                    # populate `value_eur` directly with the dimensionless quantity.
                    rows.append(
                        _row(
                            carrier=v1_carrier,
                            parameter=param,
                            value_zar=None,
                            value_eur=value,
                            units=unit,
                            base_year=PYPSA_RSA_BASE_YEAR,
                            source_carrier_in_audit=rsa_carriers[0] if rsa_carriers else "",
                            source_path=src_path,
                            source_hash=cost_audit_hash,
                            conversion_eur_zar_rate=None,
                            conversion_rate_base_year=None,
                            source="pypsa_rsa",
                            notes="median across 2023-active stations in fixed_tech",
                        )
                    )
                else:
                    add_rsa_zar(
                        v1_carrier,
                        param,
                        value,
                        unit,
                        rsa_carriers[0] if rsa_carriers else "",
                        src_path,
                        note="median across 2023-active stations in fixed_tech",
                    )

        # 4) Carriers with no PyPSA-RSA evidence but special V1 policy.
        if v1_carrier == "other_re":
            rows.append(
                _row(
                    carrier="other_re",
                    parameter="marginal_cost",
                    value_zar=0.0,
                    value_eur=0.0,
                    units="EUR/MWh",
                    base_year=2023,
                    source_carrier_in_audit="",
                    source_path="doc/active/calibration-plan/07_costs_fuels_efficiencies_and_coUE.md",
                    source_hash="",
                    conversion_eur_zar_rate=rate_2023_eur_zar,
                    conversion_rate_base_year=2023,
                    source="za_v1_policy",
                    notes="zero-cost fixed exogenous accounting generation per V1 baseline",
                )
            )
            rows.append(
                _row(
                    carrier="other_re",
                    parameter="co2_emissions",
                    value_zar=None,
                    value_eur=0.0,
                    units="tCO2/MWh",
                    base_year=2023,
                    source_carrier_in_audit="",
                    source_path="doc/active/calibration-plan/07_costs_fuels_efficiencies_and_coUE.md",
                    source_hash="",
                    conversion_eur_zar_rate=None,
                    conversion_rate_base_year=None,
                    source="za_v1_policy",
                    notes="biogenic-neutral accounting; aggregate Eskom Other RE category — reporting must flag aggregate-category limitation",
                )
            )

        if v1_carrier == "load_shedding":
            rows.append(
                _row(
                    carrier="load_shedding",
                    parameter="solver_safety_valve_marginal_cost",
                    value_zar=None,
                    value_eur=100000.0,
                    units="EUR/MWh",
                    base_year=2023,
                    source_carrier_in_audit="",
                    source_path="scripts/solve_network.py",
                    source_hash="",
                    conversion_eur_zar_rate=rate_2023_eur_zar,
                    conversion_rate_base_year=2023,
                    source="pypsa_earth_default",
                    notes="solving.options.load_shedding=100 EUR/kWh * 1000 (solve_network.py:161); numerical sentinel, not policy CoLS",
                )
            )

        if v1_carrier in ("imports", "exports"):
            rows.append(
                _row(
                    carrier=v1_carrier,
                    parameter="marginal_cost",
                    value_zar=0.0,
                    value_eur=0.0,
                    units="EUR/MWh",
                    base_year=2023,
                    source_carrier_in_audit="",
                    source_path="doc/active/calibration-plan/06_demand_import_export_model_inputs.md",
                    source_hash="",
                    conversion_eur_zar_rate=rate_2023_eur_zar,
                    conversion_rate_base_year=2023,
                    source="za_v1_policy",
                    notes="exogenous accounting flow per Module 06; zero marginal cost for V1",
                )
            )

    return rows


def write_audit_csv(rows: list[dict], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=AUDIT_COLUMNS)
    df.to_csv(out_path, index=False, float_format="%.9f")
    return len(df)
