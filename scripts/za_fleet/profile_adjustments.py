# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Config-driven ZA generator availability/profile adjustments."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def _carrier_generators(n, carrier: str) -> pd.Index:
    gens = n.generators.index[n.generators.carrier == carrier]
    if gens.empty:
        raise ValueError(
            f"ZA profile/availability adjustment requested for carrier {carrier!r}, "
            "but no matching generators exist in the active network"
        )
    return gens


def apply_profile_scaling(n, config: dict[str, Any]) -> list[dict[str, Any]]:
    cfg = config.get("za_profile_scaling", {}) or {}
    if not cfg.get("enable", False):
        return []

    carriers = cfg.get("carriers", {}) or {}
    if not isinstance(carriers, dict):
        raise ValueError("za_profile_scaling.carriers must be a mapping")

    rows: list[dict[str, Any]] = []
    dynamic_cols = set(getattr(n.generators_t, "p_max_pu", pd.DataFrame()).columns)
    for carrier, raw_multiplier in carriers.items():
        carrier = str(carrier)
        multiplier = float(raw_multiplier)
        if multiplier < 0:
            raise ValueError(f"za_profile_scaling multiplier for {carrier!r} is negative")

        gens = _carrier_generators(n, carrier)
        dynamic = pd.Index([g for g in gens if g in dynamic_cols])
        static = pd.Index([g for g in gens if g not in dynamic_cols])

        before = 0.0
        after = 0.0
        if len(dynamic) > 0:
            before += float(n.generators_t.p_max_pu.loc[:, dynamic].sum().sum())
            n.generators_t.p_max_pu.loc[:, dynamic] = (
                n.generators_t.p_max_pu.loc[:, dynamic] * multiplier
            ).clip(lower=0.0, upper=1.0)
            after += float(n.generators_t.p_max_pu.loc[:, dynamic].sum().sum())

        if len(static) > 0:
            before += float(
                n.generators.loc[static, "p_max_pu"].astype(float).sum()
                * len(n.snapshots)
            )
            n.generators.loc[static, "p_max_pu"] = (
                n.generators.loc[static, "p_max_pu"].astype(float) * multiplier
            ).clip(lower=0.0, upper=1.0)
            after += float(
                n.generators.loc[static, "p_max_pu"].astype(float).sum()
                * len(n.snapshots)
            )

        row = {
            "adjustment": "profile_scaling",
            "carrier": carrier,
            "multiplier": multiplier,
            "dynamic_generators": len(dynamic),
            "static_generators": len(static),
            "profile_sum_before": before,
            "profile_sum_after": after,
        }
        rows.append(row)
        logger.info("Applied ZA profile scaling: %s", row)
    return rows


def apply_static_availability_overrides(n, config: dict[str, Any]) -> list[dict[str, Any]]:
    cfg = (
        config.get("za_availability_overrides", {})
        .get("static_p_max_pu", {})
        or {}
    )
    if not cfg.get("enable", False):
        return []

    carriers = cfg.get("carriers", {}) or {}
    if not isinstance(carriers, dict):
        raise ValueError("za_availability_overrides.static_p_max_pu.carriers must be a mapping")

    rows: list[dict[str, Any]] = []
    dynamic_cols = set(getattr(n.generators_t, "p_max_pu", pd.DataFrame()).columns)
    for carrier, raw_value in carriers.items():
        carrier = str(carrier)
        value = float(raw_value)
        if not 0 < value <= 1:
            raise ValueError(
                f"za_availability_overrides.static_p_max_pu for {carrier!r} "
                f"must be in (0, 1], got {value}"
            )

        gens = _carrier_generators(n, carrier)
        dynamic = pd.Index([g for g in gens if g in dynamic_cols])
        if len(dynamic) > 0:
            raise ValueError(
                "ZA static p_max_pu override only supports carriers without "
                f"dynamic p_max_pu profiles; {carrier!r} has {len(dynamic)}"
            )

        before = float(n.generators.loc[gens, "p_max_pu"].astype(float).mean())
        n.generators.loc[gens, "p_max_pu"] = value
        row = {
            "adjustment": "static_p_max_pu",
            "carrier": carrier,
            "value": value,
            "generators": len(gens),
            "p_max_pu_before_mean": before,
            "p_max_pu_after_mean": value,
        }
        rows.append(row)
        logger.info("Applied ZA static availability override: %s", row)
    return rows


def apply_pre_solve_adjustments(n, config: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.extend(apply_profile_scaling(n, config))
    rows.extend(apply_static_availability_overrides(n, config))
    return rows
