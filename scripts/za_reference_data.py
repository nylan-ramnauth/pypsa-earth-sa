# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Resolve packaged South Africa reference-data paths.

Normal ZA baseline runs should read packaged reference inputs from this
repository. A sibling pypsa-rsa checkout is retained only as a legacy fallback
or for explicit source-audit workflows.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

BENCHMARK_DEFAULT = Path("data/za_reference/pypsa_rsa_benchmark_2023")
COAL_FLEX_DEFAULT = Path("data/za_reference/pypsa_rsa_coal_flexibilisation")
SUPPLY_REGIONS_DEFAULT = Path("data/za_reference/supply_regions/rsa_supply_regions.gpkg")

BENCHMARK_LEGACY_REL = Path("scenarios/Benchmark_2023")
COAL_FLEX_LEGACY_REL = Path("scenarios/Coal_Flexibilisation")
SUPPLY_REGIONS_LEGACY_REL = Path("data/bundle/supply_regions/rsa_supply_regions.gpkg")


def repo_path(path_like: str | Path) -> Path:
    path = Path(path_like).expanduser()
    return path if path.is_absolute() else REPO_ROOT / path


def _reference_cfg(config: dict[str, Any]) -> dict[str, Any]:
    return config.get("za_reference_data", {}) or {}


def _legacy_pypsa_rsa_root(config: dict[str, Any]) -> Path | None:
    raw = config.get("pypsa_rsa_root")
    if not raw:
        raw = (config.get("za_source_audits", {}) or {}).get("pypsa_rsa_root")
    if not raw:
        return None
    return repo_path(raw)


def _configured_or_default(
    config: dict[str, Any],
    key: str,
    default: Path,
    *,
    legacy_rel: Path | None = None,
) -> Path:
    cfg = _reference_cfg(config)
    if key in cfg and cfg[key]:
        return repo_path(cfg[key])

    packaged = repo_path(default)
    if packaged.exists() or legacy_rel is None:
        return packaged

    legacy_root = _legacy_pypsa_rsa_root(config)
    if legacy_root is not None:
        legacy = legacy_root / legacy_rel
        if legacy.exists():
            return legacy

    return packaged


def benchmark_root(config: dict[str, Any]) -> Path:
    return _configured_or_default(
        config,
        "pypsa_rsa_benchmark_2023",
        BENCHMARK_DEFAULT,
        legacy_rel=BENCHMARK_LEGACY_REL,
    )


def coal_flexibilisation_root(config: dict[str, Any]) -> Path:
    return _configured_or_default(
        config,
        "pypsa_rsa_coal_flexibilisation",
        COAL_FLEX_DEFAULT,
        legacy_rel=COAL_FLEX_LEGACY_REL,
    )


def benchmark_sub_scenario(config: dict[str, Any], filename: str) -> Path:
    return benchmark_root(config) / "sub_scenarios" / filename


def coal_flexibilisation_sub_scenario(config: dict[str, Any], filename: str) -> Path:
    return coal_flexibilisation_root(config) / "sub_scenarios" / filename


def supply_regions_gpkg(config: dict[str, Any]) -> Path:
    cfg = _reference_cfg(config)
    if cfg.get("supply_regions"):
        return repo_path(cfg["supply_regions"])

    packaged = repo_path(SUPPLY_REGIONS_DEFAULT)
    if packaged.exists():
        return packaged

    legacy_root = _legacy_pypsa_rsa_root(config)
    if legacy_root is not None:
        legacy = legacy_root / SUPPLY_REGIONS_LEGACY_REL
        if legacy.exists():
            return legacy

    return packaged


def source_audit_pypsa_rsa_root(config: dict[str, Any]) -> Path:
    cfg = config.get("za_source_audits", {}) or {}
    raw = cfg.get("pypsa_rsa_root") or config.get("pypsa_rsa_root")
    if not raw:
        raise FileNotFoundError(
            "source audits require za_source_audits.pypsa_rsa_root "
            "(or legacy pypsa_rsa_root)"
        )
    return repo_path(raw)
