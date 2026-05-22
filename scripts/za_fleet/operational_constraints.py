# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Apply ZA operational-constraints workbook rows during optimisation.

This is the South Africa-specific port of the single-year operational-limits
logic in ``pypsa-rsa/scripts/custom_constraints.py``. Module 13i makes the
selected workbook scenario explicit through ``za_operational_constraints`` and
audits every selected row against the active PyPSA-Earth fixed-validation
network.
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

logger = logging.getLogger(__name__)

ENERGY_UNIT_CONVERSION = {
    "GW": 1e3,
    "GJ": 1 / 3.6,
    "TJ": 1000 / 3.6,
    "PJ": 1e6 / 3.6,
    "GWh": 1e3,
    "TWh": 1e6,
}

AUDIT_COLUMNS = [
    "operational_limits_scenario",
    "model_year",
    "snapshot_year",
    "workbook_row_id",
    "component",
    "name",
    "carrier",
    "bus",
    "p_nom",
    "constraint_type",
    "period",
    "limit",
    "apply_to",
    "units",
    "rhs_value",
    "old_marginal_cost",
    "new_marginal_cost",
    "affected_by_opc",
    "reason",
    "constraint_name",
    "source_bus",
    "source_tech_fuel",
    "source",
]


def _snakemake_param(snakemake, name: str, default: Any = None) -> Any:
    params = getattr(snakemake, "params", {})
    if isinstance(params, dict):
        return params.get(name, default)
    return getattr(params, name, default)


def _snapshot_year(snapshots: pd.Index) -> int:
    years = pd.Index(snapshots.year).unique()
    if len(years) != 1:
        raise ValueError(
            "ZA operational constraints only support a single calendar-year "
            f"network; got {list(years)}"
        )
    return int(years[0])


def _normalise_year_columns(frame: pd.DataFrame) -> pd.DataFrame:
    renamed = {}
    for column in frame.columns:
        try:
            as_float = float(column)
        except (TypeError, ValueError):
            continue
        if as_float.is_integer():
            renamed[column] = int(as_float)
    return frame.rename(columns=renamed)


def _carrier_list(carrier: str) -> list[str]:
    return [c.strip() for c in str(carrier).split("+") if c.strip()]


def _filter_generators(
    n,
    carrier: str,
    bus: str,
    apply_to: str,
) -> tuple[pd.Index, pd.Index, pd.DataFrame]:
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


def _static_marginal_cost(n, name: str) -> float | str:
    if "marginal_cost" not in n.generators.columns:
        return ""
    value = n.generators.at[name, "marginal_cost"]
    if pd.isna(value):
        return ""
    return float(value)


def _audit_rows(
    n,
    *,
    scenario: str,
    model_year: int,
    snapshot_year: int,
    workbook_row_id: str,
    source_bus: str,
    source_tech_fuel: str,
    constraint_type: str,
    period: str,
    limit: str,
    apply_to: str,
    units: str,
    rhs_value: Any,
    filtered_gens: pd.DataFrame,
    constraint_name: str,
    reason: str,
    source: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    affected = reason == "applied"
    if filtered_gens.empty:
        rows.append(
            {
                "operational_limits_scenario": scenario,
                "model_year": model_year,
                "snapshot_year": snapshot_year,
                "workbook_row_id": workbook_row_id,
                "component": "Generator",
                "name": "",
                "carrier": source_tech_fuel,
                "bus": source_bus,
                "p_nom": "",
                "constraint_type": constraint_type,
                "period": period,
                "limit": limit,
                "apply_to": apply_to,
                "units": units,
                "rhs_value": rhs_value,
                "old_marginal_cost": "",
                "new_marginal_cost": "",
                "affected_by_opc": False,
                "reason": reason,
                "constraint_name": constraint_name,
                "source_bus": source_bus,
                "source_tech_fuel": source_tech_fuel,
                "source": source,
            }
        )
        return rows

    for name, gen in filtered_gens.iterrows():
        marginal_cost = _static_marginal_cost(n, name)
        rows.append(
            {
                "operational_limits_scenario": scenario,
                "model_year": model_year,
                "snapshot_year": snapshot_year,
                "workbook_row_id": workbook_row_id,
                "component": "Generator",
                "name": name,
                "carrier": gen.carrier,
                "bus": gen.bus,
                "p_nom": float(gen.p_nom) if pd.notna(gen.p_nom) else "",
                "constraint_type": constraint_type,
                "period": period,
                "limit": limit,
                "apply_to": apply_to,
                "units": units,
                "rhs_value": rhs_value,
                "old_marginal_cost": marginal_cost,
                "new_marginal_cost": marginal_cost,
                "affected_by_opc": affected,
                "reason": reason,
                "constraint_name": constraint_name,
                "source_bus": source_bus,
                "source_tech_fuel": source_tech_fuel,
                "source": source,
            }
        )
    return rows


def calc_max_gen_potential(
    n,
    sns: pd.DatetimeIndex,
    gens: pd.Index,
    incl_pu: bool,
    weightings: pd.DataFrame,
    active: pd.DataFrame,
    cf_limit: pd.Series,
    model_year: int,
    extendable: bool = False,
):
    """Return generation potential for one source-year CF limit."""
    if len(gens) == 0:
        return 0

    suffix = "" if not extendable else "-ext"
    if incl_pu:
        p_max_pu = get_as_dense(n, "Generator", "p_max_pu", sns)[gens]
    else:
        p_max_pu = pd.DataFrame(1, index=sns, columns=gens)
    p_max_pu.columns.name = f"Generator{suffix}"

    cf_limit_h = pd.DataFrame(float(cf_limit[model_year]), index=sns, columns=gens)
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
    potential = xr.DataArray(
        cf_limit_h[gens] * active[gens] * p_max_pu * weightings[gens]
    )
    if "Generator" in potential.dims:
        potential = potential.rename({"Generator": "Generator-ext"})
    return (potential * p_nom).sum(f"Generator{suffix}")


def _validate_row(
    *,
    row_id: str,
    constraint_type: str,
    period: str,
    limit: str,
    apply_to: str,
    units: str,
) -> None:
    if constraint_type not in {
        "capacity_factor",
        "primary_energy",
        "output_energy",
        "output_power",
    }:
        raise ValueError(f"Unsupported OPC constraint type in {row_id}: {constraint_type!r}")
    if period not in {"year", "month", "week", "hour"}:
        raise ValueError(f"Unsupported OPC period in {row_id}: {period!r}")
    if limit not in {"min", "max"}:
        raise ValueError(f"Unsupported OPC limit direction in {row_id}: {limit!r}")
    if apply_to not in {"fixed", "extendable", "all"}:
        raise ValueError(f"Unsupported OPC apply_to in {row_id}: {apply_to!r}")
    if constraint_type in {"primary_energy", "output_energy"} and units != "MWh":
        if units not in ENERGY_UNIT_CONVERSION:
            raise ValueError(f"Unsupported OPC energy unit in {row_id}: {units!r}")
    if constraint_type == "output_power" and units != "MW":
        if units not in ENERGY_UNIT_CONVERSION:
            raise ValueError(f"Unsupported OPC power unit in {row_id}: {units!r}")


def _delegated_to_module_13j(
    constraint_type: str,
    period: str,
    limit: str,
) -> bool:
    """Annual max generation caps belong to Module 13j, not OPC-only 13i."""
    return constraint_type == "output_energy" and period == "year" and limit == "max"


def apply_operational_constraints(
    n,
    sns: pd.DatetimeIndex,
    **kwargs,
) -> tuple[list[dict[str, Any]], bool]:
    """Apply one pypsa-rsa operational-limit row to ``n.model``."""
    if getattr(n, "multi_invest", False):
        raise ValueError("ZA operational constraints port only supports non-multi-invest networks")

    scenario = kwargs["scenario"]
    model_year = int(kwargs["model_year"])
    snapshot_year = _snapshot_year(sns)
    workbook_row_id = kwargs["workbook_row_id"]
    source = kwargs["source"]
    values = kwargs["values"]
    value = values.get(model_year, pd.NA)
    constraint_type = kwargs["type"]
    type_ = (
        "energy_power"
        if constraint_type in {"primary_energy", "output_energy", "output_power"}
        else "capacity_factor"
    )
    carrier = kwargs["carrier"]
    period = kwargs["period"]
    apply_to = kwargs["apply_to"]
    limit = kwargs["limit"]
    bus = kwargs["bus"]
    units = kwargs["units"]
    incl_pu = bool(kwargs["incl_pu"])

    _validate_row(
        row_id=workbook_row_id,
        constraint_type=constraint_type,
        period=period,
        limit=limit,
        apply_to=apply_to,
        units=units,
    )

    fix_i, ext_i, filtered_gens = _filter_generators(n, carrier, bus, apply_to)
    common_audit = dict(
        scenario=scenario,
        model_year=model_year,
        snapshot_year=snapshot_year,
        workbook_row_id=workbook_row_id,
        source_bus=bus,
        source_tech_fuel=carrier,
        constraint_type=constraint_type,
        period=period,
        limit=limit,
        apply_to=apply_to,
        units=units,
        rhs_value=value,
        filtered_gens=filtered_gens,
        source=source,
    )

    if pd.isna(value):
        return _audit_rows(
            n,
            constraint_name="",
            reason="skipped_no_value_for_model_year",
            **common_audit,
        ), False
    if _delegated_to_module_13j(constraint_type, period, limit):
        return _audit_rows(
            n,
            constraint_name="",
            reason="skipped_delegated_to_module_13j",
            **common_audit,
        ), False
    if type_ == "energy_power" and float(value) <= 0:
        return _audit_rows(
            n,
            constraint_name="",
            reason="skipped_non_positive_rhs",
            **common_audit,
        ), False
    if filtered_gens.empty:
        return _audit_rows(
            n,
            constraint_name="",
            reason="skipped_no_matching_generators",
            **common_audit,
        ), False

    if period == "week" and max(n.snapshot_weightings["generators"]) > 1:
        logger.warning(
            "Applying weekly operational limits with segmented snapshot "
            "weightings; weekly grouping may not align with source limits."
        )

    sense = "<=" if limit == "max" else ">="
    cf_limit = 0 * values if type_ == "energy_power" else values.copy()
    en_pow_limit = 0 * values if type_ == "capacity_factor" else values.copy()

    if (
        (constraint_type in {"primary_energy", "output_energy"} and units != "MWh")
        or (constraint_type == "output_power" and units != "MW")
    ):
        en_pow_limit = en_pow_limit * ENERGY_UNIT_CONVERSION[units]

    efficiency = (
        get_as_dense(n, "Generator", "efficiency", inds=filtered_gens.index)
        if constraint_type == "primary_energy"
        else pd.DataFrame(1, index=n.snapshots, columns=filtered_gens.index)
    )
    weightings = (1 / efficiency).multiply(n.snapshot_weightings.generators, axis=0)

    min_year = int(n.generators.loc[filtered_gens.index, "build_year"].min())
    sns_active = sns[sns.year >= min_year]
    gen_p = n.model.variables["Generator-p"].loc[sns_active, filtered_gens.index]
    act_gen = (
        (gen_p * weightings.loc[sns_active])
        .sel(Generator=filtered_gens.index)
        .sum("Generator")
    )
    act_gen_pow = gen_p.sel(Generator=filtered_gens.index).sum("Generator")

    active = get_activity_mask(n, "Generator", sns).astype(int)
    if type_ != "energy_power":
        max_gen_fix = (
            calc_max_gen_potential(
                n,
                sns,
                fix_i,
                incl_pu,
                weightings,
                active,
                cf_limit,
                model_year,
                extendable=False,
            )
            if len(fix_i) > 0
            else 0
        )
        max_gen_ext = (
            calc_max_gen_potential(
                n,
                sns,
                ext_i,
                incl_pu,
                weightings,
                active,
                cf_limit,
                model_year,
                extendable=True,
            )
            if len(ext_i) > 0
            else 0
        )
    else:
        max_gen_fix = 0
        max_gen_ext = 0

    groupby_dict = {
        "year": "snapshot.year",
        "month": "snapshot.month",
        "week": "snapshot.week",
        "hour": None,
    }
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
            rhs = float(en_pow_limit[model_year])
            skip_constraint = rhs <= 0

        if skip_constraint:
            return _audit_rows(
                n,
                constraint_name="",
                reason="skipped_non_positive_rhs",
                **common_audit,
            ), False

        lhs = lhs.sel(snapshot=sns_active)
        lhs_p = lhs.sum() if period == "year" else lhs.groupby(groupby).sum()
        rhs_p = (
            rhs
            if isinstance(rhs, (int, float))
            else xr.DataArray(rhs).groupby(groupby).sum()
        )
        constraint_name = f"{limit}-{carrier}-{period}-{apply_to[:3]}-{model_year}"
        n.model.add_constraints(lhs_p, sense, rhs_p, name=constraint_name)
    else:
        lhs = (
            (act_gen - max_gen_ext).sel(snapshot=sns_active)
            if type_ == "capacity_factor"
            else act_gen_pow.sel(snapshot=sns_active)
        )
        if constraint_type == "output_energy":
            raise ValueError(
                f"Hourly output_energy limits are not implemented for {workbook_row_id}"
            )

        if type_ == "capacity_factor":
            rhs = (
                max_gen_fix
                if isinstance(max_gen_fix, int)
                else xr.DataArray(max_gen_fix.loc[sns_active])
            )
            if not isinstance(rhs, int) and rhs.dims[0] == "dim_0":
                rhs = rhs.rename({"dim_0": "snapshot"})
        else:
            rhs = xr.DataArray(
                pd.Series(float(en_pow_limit[model_year]), index=sns_active)
            )
            if rhs.dims[0] == "dim_0":
                rhs = rhs.rename({"dim_0": "snapshot"})

        constraint_name = f"{limit}-{carrier}-hour-{apply_to[:3]}-{model_year}"
        n.model.add_constraints(lhs, sense, rhs, name=constraint_name)

    return _audit_rows(
        n,
        constraint_name=constraint_name,
        reason="applied",
        **common_audit,
    ), True


def _load_operational_limits(workbook: Path, scenario: str, model_year: int) -> pd.DataFrame:
    if not workbook.exists():
        raise FileNotFoundError(f"Operational constraints workbook not found: {workbook}")

    op_limits = pd.read_excel(
        workbook,
        sheet_name="operational_constraints",
        index_col=list(range(9)),
    )
    op_limits = _normalise_year_columns(op_limits)

    if scenario not in op_limits.index.get_level_values(0).unique():
        raise ValueError(
            f"Operational constraints scenario {scenario!r} not found in {workbook}"
        )
    if model_year not in op_limits.columns:
        raise ValueError(
            f"Operational constraints model_year {model_year} not found in {workbook}"
        )

    op_limits = op_limits.loc[scenario]
    op_limits = op_limits.loc[~op_limits.isna().all(axis=1)]
    op_limits = op_limits.loc[op_limits[model_year].notna()]
    if op_limits.empty:
        raise ValueError(
            f"No operational constraints rows found for scenario {scenario!r} "
            f"and model_year {model_year} in {workbook}"
        )
    return op_limits


def _resolved_config(n, snakemake) -> tuple[str, int]:
    cfg = snakemake.config.get("za_operational_constraints", {})
    legacy_cfg = snakemake.config.get("za", {}).get("operational_constraints", {})

    scenario = _snakemake_param(
        snakemake,
        "za_operational_constraints_scenario",
        cfg.get("scenario", legacy_cfg.get("scenario", "NO_MIN_GAS")),
    )
    model_year = _snakemake_param(
        snakemake,
        "za_operational_constraints_model_year",
        cfg.get("model_year", legacy_cfg.get("model_year", _snapshot_year(n.snapshots))),
    )
    return str(scenario), int(model_year)


def apply(n, snapshots: pd.DatetimeIndex, snakemake) -> list[dict[str, Any]]:
    """Read configured workbook rows and register ZA operational constraints."""
    scenario, model_year = _resolved_config(n, snakemake)
    workbook = Path(snakemake.input.operational_constraints)
    op_limits = _load_operational_limits(workbook, scenario, model_year)

    audit_rows: list[dict[str, Any]] = []
    applied_constraint_count = 0
    applied_before = len(getattr(n.model, "constraints", []))

    for pos, (row_idx, row) in enumerate(op_limits.iterrows(), start=1):
        bus, carrier, type_, period, incl_pu, limit, apply_to, units = row_idx
        row_id = f"{scenario}:{model_year}:{pos}"
        rows, applied = apply_operational_constraints(
            n,
            snapshots,
            scenario=scenario,
            model_year=model_year,
            workbook_row_id=row_id,
            source=str(workbook),
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
        audit_rows.extend(rows)
        applied_constraint_count += int(applied)

    applied_after = len(getattr(n.model, "constraints", []))
    if applied_after - applied_before != applied_constraint_count:
        raise RuntimeError(
            "Operational-constraints audit mismatch: "
            f"{applied_constraint_count} applied rows but model constraint count "
            f"changed by {applied_after - applied_before}"
        )

    matched = [
        row
        for row in audit_rows
        if row["name"] and row["reason"] in {"applied", "skipped_non_positive_rhs"}
    ]
    if not matched:
        raise RuntimeError(
            f"No operational-constraints rows for scenario {scenario!r} and "
            f"model_year {model_year} matched any generators"
        )

    return [{col: row.get(col, "") for col in AUDIT_COLUMNS} for row in audit_rows]
