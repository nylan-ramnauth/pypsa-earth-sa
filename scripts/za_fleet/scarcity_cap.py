# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Apply ZA scarcity-cap diagnostics during optimisation.

Module 13j keeps annual generation caps separate from the pypsa-rsa
operational-constraints workbook parser. The caps are direct PyPSA-Earth
diagnostic constraints configured by carrier and annual TWh target. Module 13m
labelled solves may pass a source map so Sasol caps delegated from selected
OPC workbook rows audit distinctly from explicit config fallbacks.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

import pandas as pd
import xarray as xr

logger = logging.getLogger(__name__)

MWH_PER_TWH = 1_000_000.0

AUDIT_COLUMNS = [
    "model_year",
    "snapshot_year",
    "component",
    "name",
    "carrier",
    "bus",
    "p_nom",
    "annual_dispatch_twh",
    "included_in_cap",
    "annual_generation_cap_twh",
    "reason",
    "constraint_name",
    "source",
    "parity_status",
]


@dataclass(frozen=True)
class ScarcityCapConfig:
    enabled: bool
    model_year: int
    annual_generation_caps_twh: dict[str, float]
    annual_generation_cap_sources: dict[str, str]


def _snakemake_param(snakemake, name: str, default: Any = None) -> Any:
    params = getattr(snakemake, "params", {})
    if isinstance(params, dict):
        return params.get(name, default)
    return getattr(params, name, default)


def _snapshot_year(snapshots: pd.Index) -> int:
    years = pd.Index(snapshots.year).unique()
    if len(years) != 1:
        raise ValueError(
            "ZA scarcity caps only support a single calendar-year network; "
            f"got {list(years)}"
        )
    return int(years[0])


def _constraint_name(carrier: str, model_year: int) -> str:
    safe_carrier = re.sub(r"[^A-Za-z0-9_]+", "_", carrier).strip("_")
    return f"ZA-scarcity-cap-{safe_carrier}-{model_year}"


def _cap_source(carrier: str, cap_twh: float, model_year: int) -> str:
    if model_year == 2023 and carrier == "ocgt_diesel":
        if abs(cap_twh - 5.243) <= 1e-6:
            return "Eskom observed 2023 OCGT generation target"
        if abs(cap_twh - 5.5) <= 1e-6:
            return "pypsa-rsa HIGH_GAS 2023 ocgt_diesel annual cap row"
    if model_year == 2023 and carrier == "sasol_coal" and abs(cap_twh - 5.5) <= 1e-6:
        return "explicit_cap_config"
    if model_year == 2023 and carrier == "sasol_gas" and abs(cap_twh - 2.8) <= 1e-6:
        return "explicit_cap_config"
    return "explicit_cap_config"


def _parity_status(carrier: str, model_year: int) -> str:
    if model_year == 2023 and carrier == "ocgt_diesel":
        return "diagnostic_counterfactual_for_S_2023BM_NO_MIN_GAS"
    return "diagnostic_counterfactual_not_RSA_BM_parity"


def _normalise_caps(caps: Any) -> dict[str, float]:
    if not isinstance(caps, dict) or not caps:
        raise ValueError(
            "ZA annual generation caps are enabled but carrier caps are empty "
            "or not a mapping"
        )

    normalised: dict[str, float] = {}
    for carrier, value in caps.items():
        carrier_name = str(carrier).strip()
        if not carrier_name:
            raise ValueError("ZA annual generation caps contain an empty carrier key")
        cap_twh = float(value)
        if cap_twh <= 0:
            raise ValueError(
                f"ZA annual generation cap for {carrier_name!r} must be positive; "
                f"got {cap_twh}"
            )
        normalised[carrier_name] = cap_twh
    return normalised


def _normalise_cap_sources(sources: Any, caps: dict[str, float]) -> dict[str, str]:
    if sources in (None, ""):
        return {}
    if not isinstance(sources, dict):
        raise ValueError(
            "ZA annual generation cap sources must be a mapping"
        )

    normalised: dict[str, str] = {}
    for carrier, source in sources.items():
        carrier_name = str(carrier).strip()
        if carrier_name in caps and str(source).strip():
            normalised[carrier_name] = str(source).strip()
    return normalised


def resolved_config(n, snakemake) -> ScarcityCapConfig:
    cfg = (
        snakemake.config.get("za_generation_constraints", {})
        .get("annual_generation_caps", {})
        or {}
    )
    legacy_cfg = snakemake.config.get("za_scarcity_cap", {})
    enabled = bool(
        _snakemake_param(
            snakemake,
            "za_scarcity_cap_enable",
            cfg.get("enable", legacy_cfg.get("enable", False)),
        )
    )
    model_year = int(
        _snakemake_param(
            snakemake,
            "za_scarcity_cap_model_year",
            cfg.get("model_year", legacy_cfg.get("model_year", _snapshot_year(n.snapshots))),
        )
    )
    unit = str(cfg.get("unit", "TWh"))
    if unit != "TWh":
        raise ValueError(f"ZA annual generation caps currently require unit: TWh, got {unit!r}")
    caps = _snakemake_param(
        snakemake,
        "za_scarcity_cap_annual_generation_caps_twh",
        cfg.get("carriers", legacy_cfg.get("annual_generation_caps_twh", {})),
    )
    normalised_caps = _normalise_caps(caps) if enabled else {}
    cap_sources = _snakemake_param(
        snakemake,
        "za_scarcity_cap_annual_generation_cap_sources",
        cfg.get("sources", legacy_cfg.get("annual_generation_cap_sources", {})),
    )
    return ScarcityCapConfig(
        enabled=enabled,
        model_year=model_year,
        annual_generation_caps_twh=normalised_caps,
        annual_generation_cap_sources=(
            _normalise_cap_sources(cap_sources, normalised_caps) if enabled else {}
        ),
    )


def _matching_generators(n, carrier: str) -> pd.Index:
    return n.generators.index[n.generators.carrier == carrier]


def apply(n, snapshots: pd.DatetimeIndex, snakemake) -> None:
    """Register configured annual generation-cap constraints on ``n.model``."""
    if getattr(n, "multi_invest", False):
        raise ValueError("ZA scarcity caps only support non-multi-invest networks")

    cfg = resolved_config(n, snakemake)
    if not cfg.enabled:
        return

    snapshot_year = _snapshot_year(snapshots)
    sns = pd.DatetimeIndex(snapshots)
    weights = n.snapshot_weightings["generators"].loc[sns]
    gen_p = n.model.variables["Generator-p"]

    for carrier, cap_twh in cfg.annual_generation_caps_twh.items():
        gens = _matching_generators(n, carrier)
        if gens.empty:
            raise ValueError(
                f"ZA scarcity cap requested for carrier {carrier!r}, but no "
                "matching generators exist in the active network"
            )

        gen_p_subset = gen_p.loc[sns, gens]
        weights_da = xr.DataArray(
            pd.DataFrame(
                {gen: weights for gen in gens},
                index=sns,
                columns=gens,
            ),
            dims=("snapshot", "Generator"),
            coords={"snapshot": sns, "Generator": gens},
        )
        lhs = (gen_p_subset * weights_da).sum(("snapshot", "Generator"))
        rhs = cap_twh * MWH_PER_TWH
        constraint_name = _constraint_name(carrier, cfg.model_year)
        n.model.add_constraints(lhs <= rhs, name=constraint_name)
        logger.info(
            "Added ZA scarcity cap %s: carrier=%s cap=%.6f TWh snapshot_year=%s",
            constraint_name,
            carrier,
            cap_twh,
            snapshot_year,
        )


def _annual_dispatch_twh(n) -> pd.Series:
    if n.generators_t.p.empty:
        return pd.Series(dtype=float)
    weights = n.snapshot_weightings["generators"].reindex(n.generators_t.p.index)
    return n.generators_t.p.multiply(weights, axis=0).sum(axis=0) / MWH_PER_TWH


def build_audit(n, snakemake) -> list[dict[str, Any]]:
    """Build a post-solve audit table for configured scarcity caps."""
    cfg = resolved_config(n, snakemake)
    if not cfg.enabled:
        return []

    snapshot_year = _snapshot_year(n.snapshots)
    dispatch_twh = _annual_dispatch_twh(n)
    rows: list[dict[str, Any]] = []

    configured_carriers = set(cfg.annual_generation_caps_twh)
    for name, gen in n.generators.iterrows():
        included = gen.carrier in configured_carriers
        cap_twh = (
            cfg.annual_generation_caps_twh[gen.carrier]
            if included
            else ""
        )
        rows.append(
            {
                "model_year": cfg.model_year,
                "snapshot_year": snapshot_year,
                "component": "Generator",
                "name": name,
                "carrier": gen.carrier,
                "bus": gen.bus,
                "p_nom": float(gen.p_nom) if pd.notna(gen.p_nom) else "",
                "annual_dispatch_twh": (
                    float(dispatch_twh.get(name, 0.0))
                    if name in dispatch_twh.index
                    else ""
                ),
                "included_in_cap": bool(included),
                "annual_generation_cap_twh": cap_twh,
                "reason": (
                    "included_configured_carrier"
                    if included
                    else "skipped_carrier_not_configured"
                ),
                "constraint_name": (
                    _constraint_name(gen.carrier, cfg.model_year) if included else ""
                ),
                "source": (
                    cfg.annual_generation_cap_sources.get(
                        gen.carrier,
                        _cap_source(gen.carrier, float(cap_twh), cfg.model_year),
                    )
                    if included
                    else ""
                ),
                "parity_status": (
                    _parity_status(gen.carrier, cfg.model_year) if included else ""
                ),
            }
        )

    for carrier, cap_twh in cfg.annual_generation_caps_twh.items():
        included_dispatch = sum(
            float(row["annual_dispatch_twh"] or 0.0)
            for row in rows
            if row["carrier"] == carrier and row["included_in_cap"]
        )
        if included_dispatch > cap_twh + 1e-5:
            raise RuntimeError(
                f"ZA scarcity cap audit failed for {carrier}: dispatch "
                f"{included_dispatch:.6f} TWh exceeds cap {cap_twh:.6f} TWh"
            )

    return [{col: row.get(col, "") for col in AUDIT_COLUMNS} for row in rows]
