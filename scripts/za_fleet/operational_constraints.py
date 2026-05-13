# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""ZA Calibration Plan Module 12 — apply operational constraints.

Ports the single-year branch of
``pypsa-rsa/scripts/custom_constraints.py::apply_operational_constraints`` for
the South Africa 2023 fixed-fleet validation run. The source workbook remains
owned by pypsa-rsa; this module only reads the configured scenario rows and
registers matching Generator constraints on the active linopy model.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
import xarray as xr
from pypsa.descriptors import (
    get_activity_mask,
    get_switchable_as_dense as get_as_dense,
)

idx = pd.IndexSlice
logger = logging.getLogger(__name__)

ENERGY_UNIT_CONVERSION = {
    "GW": 1e3,
    "GJ": 1 / 3.6,
    "TJ": 1000 / 3.6,
    "PJ": 1e6 / 3.6,
    "GWh": 1e3,
    "TWh": 1e6,
}

_PYPSA_RSA_TO_EARTH = {
    # None means the carrier is intentionally absent from the Module 12
    # pypsa-earth ZA fixed fleet. Future modules may map these explicitly.
    "ocgt_avf": None,
    "ccgt_steam": None,
    "rmippp": None,
    "sasol_coal": None,
    "sasol_gas": None,
}

AUDIT_COLUMNS = [
    "scenario",
    "bus",
    "tech_fuel",
    "type",
    "period",
    "limit",
    "apply_to",
    "units",
    "value_2023",
    "matched_carriers",
    "n_generators",
    "constraint_name",
    "status",
]


def _year(snapshots: pd.Index) -> int:
    years = pd.Index(snapshots.year).unique()
    if len(years) != 1:
        raise ValueError(
            "ZA operational constraints only support a single calendar year; "
            f"got {list(years)}"
        )
    return int(years[0])


def _carrier_list(carrier: str) -> list[str]:
    return [c.strip() for c in str(carrier).split("+") if c.strip()]


def _filter_generators(n, carrier: str, bus: str, apply_to: str) -> tuple[pd.Index, pd.Index, pd.DataFrame]:
    carriers = _carrier_list(carrier)
    filtered = n.generators[n.generators.carrier.isin(carriers)]
    if bus != "global":
        filtered = filtered[filtered.bus == bus]

    fix_i = (
        filtered.index[~filtered.p_nom_extendable.astype(bool)]
        if apply_to in {"fixed", "all"}
        else pd.Index([])
    )
    ext_i = (
        filtered.index[filtered.p_nom_extendable.astype(bool)]
        if apply_to in {"extendable", "all"}
        else pd.Index([])
    )
    filtered = filtered.loc[list(fix_i) + list(ext_i)]
    return fix_i, ext_i, filtered


def calc_max_gen_potential(
    n,
    sns: pd.DatetimeIndex,
    gens: pd.Index,
    incl_pu: bool,
    weightings: pd.DataFrame,
    active: pd.DataFrame,
    cf_limit: pd.Series,
    extendable: bool = False,
):
    """Return generation potential for the single-year operational CF limit."""
    if len(gens) == 0:
        return 0

    year = _year(sns)
    suffix = "" if not extendable else "-ext"
    if incl_pu:
        p_max_pu = get_as_dense(n, "Generator", "p_max_pu", sns)[gens]
    else:
        p_max_pu = pd.DataFrame(1, index=sns, columns=gens)
    p_max_pu.columns.name = f"Generator{suffix}"

    cf_limit_h = pd.DataFrame(float(cf_limit[year]), index=sns, columns=gens)
    cf_limit_h = cf_limit_h * weightings[gens]

    if not extendable:
        return (
            cf_limit_h[gens]
            * active[gens]
            * p_max_pu
            * weightings[gens]
            * n.generators.loc[gens, "p_nom"]
        ).sum(axis=1)

    p_nom = n.model.variables["Generator-p_nom"].sel({f"Generator{suffix}": gens})
    potential = xr.DataArray(cf_limit_h[gens] * active[gens] * p_max_pu * weightings[gens])
    if "Generator" in potential.dims:
        potential = potential.rename({"Generator": "Generator-ext"})
    return (potential * p_nom).sum(f"Generator{suffix}")


def _constraint_status_for_value(type_: str, value: Any) -> str | None:
    if pd.isna(value):
        return "skipped_nan"
    if type_ == "energy_power" and float(value) <= 0:
        return "skipped_zero_rhs"
    return None


def apply_operational_constraints(n, sns: pd.DatetimeIndex, **kwargs) -> dict[str, Any]:
    """Apply one pypsa-rsa operational-limit row to ``n.model``.

    Returns one audit row. Missing carriers are normal no-ops for Module 12.
    """
    if getattr(n, "multi_invest", False):
        raise ValueError("ZA operational constraints port only supports non-multi-invest networks")

    year = _year(sns)
    values = kwargs["values"]
    value = values.get(year, pd.NA)
    type_ = (
        "energy_power"
        if kwargs["type"] in {"primary_energy", "output_energy", "output_power"}
        else "capacity_factor"
    )
    carrier = kwargs["carrier"]
    period = kwargs["period"]
    apply_to = kwargs["apply_to"]
    limit = kwargs["limit"]
    bus = kwargs["bus"]
    units = kwargs["units"]

    fix_i, ext_i, filtered_gens = _filter_generators(n, carrier, bus, apply_to)
    matched_carriers = sorted(set(filtered_gens.carrier.astype(str)))
    constraint_name = ""

    audit = {
        "scenario": kwargs["scenario"],
        "bus": bus,
        "tech_fuel": carrier,
        "type": kwargs["type"],
        "period": period,
        "limit": limit,
        "apply_to": apply_to,
        "units": units,
        "value_2023": value,
        "matched_carriers": " + ".join(matched_carriers),
        "n_generators": int(len(filtered_gens)),
        "constraint_name": constraint_name,
        "status": "applied",
    }

    skipped = _constraint_status_for_value(type_, value)
    if skipped is not None:
        audit["status"] = skipped
        return audit
    if filtered_gens.empty:
        audit["status"] = "skipped_no_match"
        return audit
    if len(ext_i) > 0:
        raise ValueError(
            "ZA Module 12 operational constraints expected fixed fleet only; "
            f"matched extendable generators for {carrier!r}: {list(ext_i)}"
        )

    if period == "week" and max(n.snapshot_weightings["generators"]) > 1:
        logger.warning(
            "Applying weekly operational limits with segmented snapshot weightings; "
            "weekly grouping may not align with source limits."
        )

    sense = "<=" if limit == "max" else ">="
    cf_limit = 0 * values if type_ == "energy_power" else values.copy()
    en_pow_limit = 0 * values if type_ == "capacity_factor" else values.copy()

    if (
        (kwargs["type"] in {"primary_energy", "output_energy"} and units != "MWh")
        or (kwargs["type"] == "output_power" and units != "MW")
    ):
        en_pow_limit = en_pow_limit * ENERGY_UNIT_CONVERSION[units]

    efficiency = (
        get_as_dense(n, "Generator", "efficiency", inds=filtered_gens.index)
        if kwargs["type"] == "primary_energy"
        else pd.DataFrame(1, index=n.snapshots, columns=filtered_gens.index)
    )
    weightings = (1 / efficiency).multiply(n.snapshot_weightings.generators, axis=0)

    min_year = int(n.generators.loc[filtered_gens.index, "build_year"].min())
    sns_active = sns[sns.year >= min_year]
    gen_p = n.model.variables["Generator-p"].loc[sns_active, filtered_gens.index]
    act_gen = (gen_p * weightings.loc[sns_active]).sel(Generator=filtered_gens.index).sum("Generator")
    act_gen_pow = gen_p.sel(Generator=filtered_gens.index).sum("Generator")

    groupby_dict = {
        "year": "snapshot.year",
        "month": "snapshot.month",
        "week": "snapshot.week",
        "hour": None,
    }

    active = get_activity_mask(n, "Generator", sns).astype(int)
    max_gen_fix = (
        calc_max_gen_potential(n, sns, fix_i, kwargs["incl_pu"], weightings, active, cf_limit, extendable=False)
        if type_ != "energy_power" and len(fix_i) > 0
        else 0
    )
    max_gen_ext = 0

    groupby = groupby_dict[period]
    if groupby:
        if type_ == "capacity_factor":
            lhs = act_gen - max_gen_ext
            rhs = max_gen_fix
            if isinstance(rhs, (int, float)):
                skip_constraint = rhs < 0
            else:
                rhs = rhs.loc[sns_active]
                skip_constraint = not (rhs >= 0).any().any()
        else:
            lhs = act_gen
            rhs = float(en_pow_limit[year])
            skip_constraint = rhs <= 0

        if skip_constraint:
            audit["status"] = "skipped_zero_rhs"
            return audit

        lhs = lhs.sel(snapshot=sns_active)
        lhs_p = lhs.sum() if period == "year" else lhs.groupby(groupby).sum()
        rhs_p = (
            rhs
            if isinstance(rhs, (int, float))
            else xr.DataArray(rhs).groupby(groupby).sum()
        )
        constraint_name = f"{limit}-{carrier}-{period}-{apply_to[:3]}-{year}"
        n.model.add_constraints(lhs_p, sense, rhs_p, name=constraint_name)
    else:
        lhs = (
            (act_gen - max_gen_ext).sel(snapshot=sns_active)
            if type_ == "capacity_factor"
            else act_gen_pow.sel(snapshot=sns_active)
        )
        if kwargs["type"] == "output_energy":
            logger.warning("Energy limits are not implemented for hourly operational limits.")
            audit["status"] = "skipped_zero_rhs"
            return audit

        if type_ == "capacity_factor":
            rhs = (
                max_gen_fix
                if isinstance(max_gen_fix, int)
                else xr.DataArray(max_gen_fix.loc[sns_active])
            )
            if not isinstance(rhs, int) and rhs.dims[0] == "dim_0":
                rhs = rhs.rename({"dim_0": "snapshot"})
        else:
            rhs = pd.Series(index=sns, dtype=float)
            rhs.loc[str(year)] = float(en_pow_limit[year])

        constraint_name = f"{limit}-{carrier}-hour-{apply_to[:3]}"
        n.model.add_constraints(lhs, sense, rhs, name=constraint_name)

    audit["constraint_name"] = constraint_name
    return audit


def _load_operational_limits(workbook: Path, scenario: str) -> pd.DataFrame:
    op_limits = pd.read_excel(
        workbook,
        sheet_name="operational_constraints",
        index_col=list(range(9)),
    )
    if scenario not in op_limits.index.get_level_values(0).unique():
        raise ValueError(f"Operational constraints scenario {scenario!r} not found in {workbook}")

    op_limits = op_limits.loc[scenario]
    op_limits = op_limits.loc[~op_limits.isna().all(axis=1)]
    return op_limits


def apply(n, snapshots: pd.DatetimeIndex, snakemake) -> list[dict[str, Any]]:
    """Read configured pypsa-rsa workbook rows and register ZA constraints."""
    cfg = snakemake.config.get("za", {}).get("operational_constraints", {})
    scenario = cfg.get("scenario", "HIGH_GAS")
    workbook = Path(snakemake.input.operational_constraints)

    op_limits = _load_operational_limits(workbook, scenario)
    audit_rows: list[dict[str, Any]] = []
    applied_before = len(getattr(n.model, "constraints", []))

    for row_idx, row in op_limits.iterrows():
        bus, carrier, type_, period, incl_pu, limit, apply_to, units = row_idx
        audit_rows.append(
            apply_operational_constraints(
                n,
                snapshots,
                scenario=scenario,
                bus=bus,
                carrier=carrier,
                type=type_,
                values=row,
                period=period,
                incl_pu=bool(incl_pu),
                limit=limit,
                apply_to=apply_to,
                units=units,
            )
        )

    applied_rows = [r for r in audit_rows if r["status"] == "applied"]
    applied_after = len(getattr(n.model, "constraints", []))
    if applied_after - applied_before != len(applied_rows):
        raise RuntimeError(
            "Operational-constraints audit mismatch: "
            f"{len(applied_rows)} applied rows but model constraint count changed "
            f"by {applied_after - applied_before}"
        )

    matched_rows = [r for r in audit_rows if int(r["n_generators"]) > 0]
    if not matched_rows:
        raise RuntimeError(
            f"No operational-constraints rows for scenario {scenario!r} matched any generators"
        )

    return [{col: row.get(col, "") for col in AUDIT_COLUMNS} for row in audit_rows]
