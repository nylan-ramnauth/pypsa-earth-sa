"""Module 14 joint VRE scaling + annual cap solve.

This script starts from the accepted Module 13n solved network, applies VRE
availability scaling and annual generation caps in memory, then re-solves once.
Coal availability is owned by the regenerated coal EAF input CSVs upstream of
this solve. It intentionally avoids rebuilding the Snakemake DAG.
"""

from __future__ import annotations

import argparse
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/matplotlib")

import pandas as pd
import pypsa
import yaml

from za_fleet.operational_constraints import apply as apply_operational_constraints
from za_fleet.scarcity_cap import apply as apply_scarcity_cap


REPO_ROOT = Path(__file__).resolve().parents[1]
VAULT_ROOT = REPO_ROOT.parents[2]

NETWORK_DIR = REPO_ROOT / "results/za_2023_fixed_validation/networks"
SOURCE_NETWORK = (
    NETWORK_DIR
    / "elec_s_34_ec_lc1_NoCO2-1H-EAF-UC-OPC-LOW-GAS-OFFICIAL-FLEET.nc"
)
BACKUP_NETWORK = (
    NETWORK_DIR
    / "elec_s_34_ec_lc1_NoCO2-1H-EAF-UC-OPC-LOW-GAS-OFFICIAL-FLEET-PRE-14.nc"
)
OUTPUT_NETWORK = (
    NETWORK_DIR
    / "elec_s_34_ec_lc1_NoCO2-1H-EAF-UC-OPC-LOW-GAS-OFFICIAL-FLEET-MODULE14-VRE-OCGT-CAP.nc"
)

VRE_SCALE = {
    "onwind": 1.58,
    "solar": 1.40,
    "ror": 1.425,
}
OCGT_CAP_TWH = 5.243
OCGT_CARRIERS = ("ocgt_diesel", "OCGT")
MWH_PER_TWH = 1_000_000.0
GWH_PER_TWH = 1_000.0

ESKOM_TARGETS_TWH = {
    "Coal dispatch": 165.627,
    "OCGT diesel dispatch": 5.243,
    "Load shedding": 16.755,
}


@dataclass
class RunConfig:
    label: str
    source_network: Path
    backup_network: Path
    output_network: Path
    vre_scale: dict[str, float]
    annual_generation_caps_twh: dict[str, float]
    annual_generation_cap_sources: dict[str, str]
    nuclear_availability: dict[str, Any]
    log_slug: str


@dataclass
class ScaleAudit:
    carrier: str
    multiplier: float
    dynamic_generators: int
    static_generators: int
    before_twh: float
    after_twh: float


@dataclass
class NuclearAvailabilityAudit:
    enabled: bool
    carrier: str
    configured_p_max_pu: float | None
    target_annual_generation_twh: float
    target_p_max_pu: float
    generators: int
    p_nom_mw: float
    before_p_max_pu: float
    after_p_max_pu: float


class AttrDict(dict):
    """Dictionary with attribute access for the minimal Snakemake shim."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def _relative(path: Path) -> Path:
    try:
        return path.relative_to(REPO_ROOT)
    except ValueError:
        return path


def _repo_path(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else REPO_ROOT / path


def default_run_config() -> RunConfig:
    return RunConfig(
        label="Module 14",
        source_network=SOURCE_NETWORK,
        backup_network=BACKUP_NETWORK,
        output_network=OUTPUT_NETWORK,
        vre_scale=dict(VRE_SCALE),
        annual_generation_caps_twh={"ocgt_diesel": OCGT_CAP_TWH},
        annual_generation_cap_sources={
            "ocgt_diesel": "Eskom observed 2023 OCGT generation target"
        },
        nuclear_availability={"enable": False},
        log_slug="module14-joint-solve",
    )


def load_run_config(overlay: Path | None) -> RunConfig:
    cfg = default_run_config()
    if overlay is None:
        return cfg

    overlay_path = _repo_path(overlay)
    with overlay_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    block = data.get("module14b_diagnostic", data)
    if not isinstance(block, dict):
        raise ValueError(f"Overlay {overlay_path} must contain a mapping")

    cfg.label = str(block.get("label", "Module 14b"))
    cfg.source_network = _repo_path(block.get("source_network", cfg.source_network))
    cfg.backup_network = _repo_path(block.get("backup_network", cfg.backup_network))
    cfg.output_network = _repo_path(block.get("output_network", cfg.output_network))
    cfg.vre_scale = {
        str(k): float(v) for k, v in (block.get("vre_scale", cfg.vre_scale) or {}).items()
    }
    cfg.annual_generation_caps_twh = {
        str(k): float(v)
        for k, v in (
            block.get("annual_generation_caps_twh", cfg.annual_generation_caps_twh)
            or {}
        ).items()
    }
    cfg.annual_generation_cap_sources = {
        str(k): str(v)
        for k, v in (
            block.get(
                "annual_generation_cap_sources",
                cfg.annual_generation_cap_sources,
            )
            or {}
        ).items()
    }
    cfg.nuclear_availability = dict(
        block.get("nuclear_availability", cfg.nuclear_availability) or {}
    )
    cfg.log_slug = str(block.get("log_slug", "module14b-coal49-nuclear50"))
    return cfg


def _snapshot_weights(n: pypsa.Network) -> pd.Series:
    return n.snapshot_weightings["generators"].reindex(n.snapshots)


def _annual_generator_dispatch_twh(n: pypsa.Network) -> pd.Series:
    if n.generators_t.p.empty:
        return pd.Series(dtype=float)
    weighted = n.generators_t.p.multiply(_snapshot_weights(n), axis=0)
    return weighted.sum(axis=0).groupby(n.generators.carrier).sum() / MWH_PER_TWH


def _annual_storage_dispatch_twh(n: pypsa.Network) -> pd.Series:
    if n.storage_units.empty or n.storage_units_t.p_dispatch.empty:
        return pd.Series(dtype=float)
    weighted = n.storage_units_t.p_dispatch.multiply(_snapshot_weights(n), axis=0)
    return (
        weighted.sum(axis=0).groupby(n.storage_units.carrier).sum() / MWH_PER_TWH
    )


def _annual_storage_store_twh(n: pypsa.Network) -> pd.Series:
    if n.storage_units.empty or n.storage_units_t.p_store.empty:
        return pd.Series(dtype=float)
    weighted = n.storage_units_t.p_store.multiply(_snapshot_weights(n), axis=0)
    return (
        weighted.sum(axis=0).groupby(n.storage_units.carrier).sum() / MWH_PER_TWH
    )


def _load_twh(n: pypsa.Network) -> float:
    return float(n.loads_t.p_set.multiply(_snapshot_weights(n), axis=0).sum().sum()) / MWH_PER_TWH


def _carrier_dispatch(dispatch: pd.Series, carriers: list[str]) -> float:
    return float(dispatch.reindex(carriers, fill_value=0.0).sum())


def dispatch_summary(n: pypsa.Network) -> dict[str, float]:
    gen_dispatch = _annual_generator_dispatch_twh(n)
    storage_dispatch = _annual_storage_dispatch_twh(n)
    storage_store = _annual_storage_store_twh(n)
    hydro_ror = _carrier_dispatch(gen_dispatch, ["hydro", "ror"])
    hydro_ror += _carrier_dispatch(storage_dispatch, ["hydro"])

    return {
        "Network load": _load_twh(n),
        "Coal dispatch": _carrier_dispatch(gen_dispatch, ["coal"]),
        "Nuclear dispatch": _carrier_dispatch(gen_dispatch, ["nuclear"]),
        "OCGT diesel dispatch": _carrier_dispatch(gen_dispatch, list(OCGT_CARRIERS)),
        "Wind dispatch": _carrier_dispatch(gen_dispatch, ["onwind"]),
        "Solar dispatch": _carrier_dispatch(gen_dispatch, ["solar"]),
        "CSP dispatch": _carrier_dispatch(gen_dispatch, ["csp"]),
        "Hydro/ROR dispatch": hydro_ror,
        "PHS generation": _carrier_dispatch(storage_dispatch, ["PHS"]),
        "PHS pumping": _carrier_dispatch(storage_store, ["PHS"]),
        "Load shedding": _carrier_dispatch(gen_dispatch, ["load shedding"]),
    }


def backup_source_network(cfg: RunConfig) -> None:
    if not cfg.source_network.exists():
        raise FileNotFoundError(f"Source network not found: {cfg.source_network}")
    if cfg.backup_network.exists():
        print(f"PRE-14 backup already exists: {_relative(cfg.backup_network)}")
        return
    cfg.backup_network.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cfg.source_network, cfg.backup_network)
    print(f"Created PRE-14 backup: {_relative(cfg.backup_network)}")


def scale_vre_profiles(n: pypsa.Network, vre_scale: dict[str, float]) -> list[ScaleAudit]:
    audits: list[ScaleAudit] = []
    dynamic_cols = set(n.generators_t.p_max_pu.columns)

    for carrier, multiplier in vre_scale.items():
        carrier_generators = n.generators.index[n.generators.carrier == carrier]
        dynamic = pd.Index([g for g in carrier_generators if g in dynamic_cols])
        static = pd.Index([g for g in carrier_generators if g not in dynamic_cols])

        before = 0.0
        after = 0.0
        if len(dynamic) > 0:
            before += float(n.generators_t.p_max_pu[dynamic].sum().sum())
            n.generators_t.p_max_pu.loc[:, dynamic] = (
                n.generators_t.p_max_pu.loc[:, dynamic] * multiplier
            ).clip(lower=0.0, upper=1.0)
            after += float(n.generators_t.p_max_pu[dynamic].sum().sum())

        if carrier == "ror" and len(static) > 0:
            before += float(n.generators.loc[static, "p_max_pu"].sum() * len(n.snapshots))
            n.generators.loc[static, "p_max_pu"] = (
                n.generators.loc[static, "p_max_pu"] * multiplier
            ).clip(lower=0.0, upper=1.0)
            after += float(n.generators.loc[static, "p_max_pu"].sum() * len(n.snapshots))

        audits.append(
            ScaleAudit(
                carrier=carrier,
                multiplier=multiplier,
                dynamic_generators=len(dynamic),
                static_generators=len(static) if carrier == "ror" else 0,
                before_twh=before / MWH_PER_TWH,
                after_twh=after / MWH_PER_TWH,
            )
        )

    return audits


def apply_nuclear_availability(
    n: pypsa.Network,
    availability: dict[str, Any],
    annual_caps_twh: dict[str, float],
) -> NuclearAvailabilityAudit:
    enabled = bool(availability.get("enable", False))
    carrier = str(availability.get("carrier", "nuclear"))
    configured_p_max_pu = availability.get("target_p_max_pu", None)
    configured_p_max_pu = (
        float(configured_p_max_pu) if configured_p_max_pu is not None else None
    )
    target_twh = float(availability.get("target_annual_generation_twh", 0.0))
    if target_twh <= 0 and configured_p_max_pu is None:
        target_twh = float(annual_caps_twh.get(carrier, 0.0))
    if not enabled:
        return NuclearAvailabilityAudit(
            enabled=False,
            carrier=carrier,
            configured_p_max_pu=configured_p_max_pu,
            target_annual_generation_twh=target_twh,
            target_p_max_pu=0.0,
            generators=0,
            p_nom_mw=0.0,
            before_p_max_pu=0.0,
            after_p_max_pu=0.0,
        )
    gens = n.generators.index[n.generators.carrier == carrier]
    if gens.empty:
        raise ValueError(f"Nuclear availability requested for {carrier!r}, but no generators match")
    if target_twh <= 0 and configured_p_max_pu is None:
        raise ValueError("Nuclear availability target must be positive")
    if n.generators_t.p_max_pu.columns.intersection(gens).size:
        raise ValueError(
            "Nuclear availability diagnostic currently supports static p_max_pu only; "
            "dynamic nuclear p_max_pu columns are present."
        )

    p_nom_mw = float(n.generators.loc[gens, "p_nom"].sum())
    annual_potential_mwh = p_nom_mw * float(_snapshot_weights(n).sum())
    if configured_p_max_pu is not None:
        target_p_max_pu = configured_p_max_pu
        target_twh = annual_potential_mwh * target_p_max_pu / MWH_PER_TWH
    else:
        target_p_max_pu = target_twh * MWH_PER_TWH / annual_potential_mwh
    if not 0 < target_p_max_pu <= 1:
        raise ValueError(
            f"Nuclear target p_max_pu outside (0, 1]: {target_p_max_pu:.6f}"
        )

    before = float(n.generators.loc[gens, "p_max_pu"].astype(float).mean())
    n.generators.loc[gens, "p_max_pu"] = target_p_max_pu
    after = float(n.generators.loc[gens, "p_max_pu"].astype(float).mean())
    return NuclearAvailabilityAudit(
        enabled=True,
        carrier=carrier,
        configured_p_max_pu=configured_p_max_pu,
        target_annual_generation_twh=target_twh,
        target_p_max_pu=target_p_max_pu,
        generators=len(gens),
        p_nom_mw=p_nom_mw,
        before_p_max_pu=before,
        after_p_max_pu=after,
    )


def _resolve_opc_workbook(config: dict[str, Any]) -> Path:
    packaged = (
        REPO_ROOT
        / "data/za_reference/pypsa_rsa_benchmark_2023/sub_scenarios/operational_constraints.xlsx"
    )
    if packaged.exists():
        return packaged

    pypsa_rsa_root = Path(config.get("pypsa_rsa_root", ""))
    fallback = (
        pypsa_rsa_root
        / "scenarios/Benchmark_2023/sub_scenarios/operational_constraints.xlsx"
    )
    if fallback.exists():
        return fallback
    raise FileNotFoundError(f"Operational constraints workbook not found: {fallback}")


def _normalise_annual_caps(n: pypsa.Network, caps: dict[str, float]) -> dict[str, float]:
    if not caps:
        raise ValueError("At least one annual generation cap must be configured")
    normalised: dict[str, float] = {}
    for carrier, cap in caps.items():
        if carrier in OCGT_CARRIERS:
            present = [c for c in OCGT_CARRIERS if (n.generators.carrier == c).any()]
            if not present:
                raise ValueError("No OCGT cap carrier found; expected ocgt_diesel or OCGT.")
            if len(present) > 1:
                raise ValueError(
                    "Both ocgt_diesel and OCGT are present. Configure caps for the "
                    "actual carriers explicitly before solving."
                )
            normalised[present[0]] = float(cap)
        else:
            if not (n.generators.carrier == carrier).any():
                raise ValueError(
                    f"Annual cap requested for carrier {carrier!r}, but no matching generators exist"
                )
            normalised[carrier] = float(cap)
    return normalised


def _carrier_to_cap(n: pypsa.Network) -> str:
    present = [carrier for carrier in OCGT_CARRIERS if (n.generators.carrier == carrier).any()]
    if not present:
        raise ValueError("No OCGT cap carrier found; expected ocgt_diesel or OCGT.")
    if len(present) > 1:
        raise ValueError(
            "Both ocgt_diesel and OCGT are present. The existing Module 13j cap "
            "helper applies caps per carrier, but Module 14 requires one combined "
            "annual cap. Inspect carriers before solving."
        )
    return present[0]


def _solver_options(n: pypsa.Network) -> dict[str, Any]:
    solving = n.meta.get("solving", {}) if isinstance(n.meta, dict) else {}
    solver = solving.get("solver", {}) if isinstance(solving, dict) else {}
    options_name = solver.get("options", "gurobi-default")
    options_map = solving.get("solver_options", {}) if isinstance(solving, dict) else {}
    options = dict(options_map.get(options_name, {}))
    options.setdefault("threads", 2)
    return options


def _make_snakemake_shim(
    n: pypsa.Network,
    *,
    opc_workbook: Path,
    annual_caps_twh: dict[str, float],
    cap_sources: dict[str, str],
) -> SimpleNamespace:
    config = dict(n.meta) if isinstance(n.meta, dict) else {}
    config.setdefault("za_operational_constraints", {})
    config.setdefault("za_scarcity_cap", {})

    params = AttrDict(
        {
            "za_operational_constraints_enable": True,
            "za_operational_constraints_scenario": "LOW_GAS",
            "za_operational_constraints_model_year": 2023,
            "za_scarcity_cap_enable": True,
            "za_scarcity_cap_model_year": 2023,
            "za_scarcity_cap_annual_generation_caps_twh": annual_caps_twh,
            "za_scarcity_cap_annual_generation_cap_sources": cap_sources,
        }
    )
    return SimpleNamespace(
        config=config,
        params=params,
        input=AttrDict({"operational_constraints": str(opc_workbook)}),
        output=AttrDict({}),
    )


def _remove_disabled_min_up_down_constraints(n: pypsa.Network) -> None:
    config = getattr(n, "config", {})
    uc_cfg = config.get("za_coal_disaggregation", {}).get("uc", {})
    if not uc_cfg.get("enable", False) or uc_cfg.get("apply_min_up_down_time", False):
        return

    drop = [
        "Generator-com-up-time",
        "Generator-com-down-time",
        "Generator-com-status-min_up_time_must_stay_up",
        "Generator-com-status-min_down_time_must_stay_up",
    ]
    existing = [name for name in drop if name in n.model.constraints]
    if existing:
        n.model.remove_constraints(existing)
        print(f"Removed ZA coal UC min-up/min-down constraints: {existing}")


def solve_module14(n: pypsa.Network, cfg: RunConfig) -> tuple[str, str, Path, dict[str, float]]:
    config = dict(n.meta) if isinstance(n.meta, dict) else {}
    opc_workbook = _resolve_opc_workbook(config)
    annual_caps = _normalise_annual_caps(n, cfg.annual_generation_caps_twh)
    cap_sources = {
        carrier: cfg.annual_generation_cap_sources.get(carrier, "explicit_diagnostic_overlay")
        for carrier in annual_caps
    }
    snakemake = _make_snakemake_shim(
        n,
        opc_workbook=opc_workbook,
        annual_caps_twh=annual_caps,
        cap_sources=cap_sources,
    )

    def extra_functionality(network: pypsa.Network, snapshots: pd.DatetimeIndex) -> None:
        network.config = config
        print("Registering LOW_GAS OPC constraints")
        apply_operational_constraints(network, snapshots, snakemake)
        for carrier, cap in annual_caps.items():
            print(f"Registering annual cap: {carrier} <= {cap:.3f} TWh")
        apply_scarcity_cap(network, snapshots, snakemake)
        _remove_disabled_min_up_down_constraints(network)

    has_committable = bool(n.generators.get("committable", pd.Series(False)).fillna(False).any())
    kwargs = {
        "solver_name": "gurobi",
        "solver_options": _solver_options(n),
        "extra_functionality": extra_functionality,
    }
    if has_committable:
        kwargs["linearized_unit_commitment"] = True

    print(f"Solving with Gurobi options: {kwargs['solver_options']}")
    try:
        status, condition = n.optimize(**kwargs)
    except AttributeError:
        from pypsa.optimization.optimize import optimize

        status, condition = optimize(n, **kwargs)

    return str(status), str(condition), opc_workbook, annual_caps


def format_summary(status: str, condition: str, summary: dict[str, float]) -> str:
    lines = [
        f"Solve status: {status} / {condition}",
        f"Network load: {summary['Network load']:.3f} TWh",
        f"Coal dispatch: {summary['Coal dispatch']:.3f} TWh",
        f"Nuclear dispatch: {summary['Nuclear dispatch']:.3f} TWh",
        f"OCGT diesel dispatch: {summary['OCGT diesel dispatch']:.3f} TWh",
        f"Wind dispatch: {summary['Wind dispatch']:.3f} TWh",
        f"Solar dispatch: {summary['Solar dispatch']:.3f} TWh",
        f"CSP dispatch: {summary['CSP dispatch']:.3f} TWh",
        f"Hydro/ROR dispatch: {summary['Hydro/ROR dispatch']:.3f} TWh",
        f"PHS generation: {summary['PHS generation']:.3f} TWh",
        f"PHS pumping: {summary['PHS pumping']:.3f} TWh",
        f"Load shedding: {summary['Load shedding']:.3f} TWh",
    ]
    return "\n".join(lines)


def acceptance_checks(
    status: str,
    condition: str,
    baseline: dict[str, float],
    summary: dict[str, float],
    cfg: RunConfig,
) -> list[tuple[str, bool, str]]:
    checks = [
        (
            "Solve status ok / optimal",
            status == "ok" and condition == "optimal",
            f"{status} / {condition}",
        ),
        (
            "Network load within 220,902 GWh +/- 5 GWh",
            abs(summary["Network load"] * GWH_PER_TWH - 220_902.0) <= 5.0,
            f"{summary['Network load'] * GWH_PER_TWH:.3f} GWh",
        ),
        (
            "OCGT diesel dispatch <= 5,243 GWh",
            summary["OCGT diesel dispatch"] * GWH_PER_TWH <= 5_243.0 + 1e-3,
            f"{summary['OCGT diesel dispatch'] * GWH_PER_TWH:.3f} GWh",
        ),
    ]
    if "nuclear" in cfg.annual_generation_caps_twh:
        nuclear_cap = cfg.annual_generation_caps_twh["nuclear"] * GWH_PER_TWH
        checks.append(
            (
                "Nuclear dispatch <= configured cap",
                summary["Nuclear dispatch"] * GWH_PER_TWH <= nuclear_cap + 1e-3,
                f"{summary['Nuclear dispatch'] * GWH_PER_TWH:.3f} <= {nuclear_cap:.3f} GWh",
            )
        )
    checks.extend(
        [
        (
            "Wind dispatch increased vs PRE-14",
            summary["Wind dispatch"] > baseline["Wind dispatch"],
            f"{baseline['Wind dispatch']:.3f} -> {summary['Wind dispatch']:.3f} TWh",
        ),
        (
            "Solar dispatch increased vs PRE-14",
            summary["Solar dispatch"] > baseline["Solar dispatch"],
            f"{baseline['Solar dispatch']:.3f} -> {summary['Solar dispatch']:.3f} TWh",
        ),
        (
            "Coal dispatch in 163-167 TWh range",
            163.0 <= summary["Coal dispatch"] <= 167.0,
            f"{summary['Coal dispatch']:.3f} TWh",
        ),
        (
            "Output network exists",
            cfg.output_network.exists(),
            str(_relative(cfg.output_network)),
        ),
        (
            "PRE-14 backup exists",
            cfg.backup_network.exists(),
            str(_relative(cfg.backup_network)),
        ),
        ]
    )
    return checks


def write_shared_log(
    *,
    status: str,
    condition: str,
    baseline: dict[str, float],
    summary: dict[str, float],
    scale_audits: list[ScaleAudit],
    nuclear_audit: NuclearAvailabilityAudit,
    opc_workbook: Path,
    annual_caps: dict[str, float],
    checks: list[tuple[str, bool, str]],
    cfg: RunConfig,
) -> Path:
    now = datetime.now()
    log_path = (
        VAULT_ROOT
        / "5-logs/shared"
        / f"{now:%Y-%m-%d-%H%M}-{cfg.log_slug}.md"
    )

    dispatch_rows = [
        f"| Metric | {cfg.label} TWh | Eskom target TWh | PRE-14 TWh |",
        "|---|---:|---:|---:|",
    ]
    for metric in [
        "Coal dispatch",
        "Nuclear dispatch",
        "OCGT diesel dispatch",
        "Wind dispatch",
        "Solar dispatch",
        "CSP dispatch",
        "Hydro/ROR dispatch",
        "PHS generation",
        "PHS pumping",
        "Load shedding",
    ]:
        target = ESKOM_TARGETS_TWH.get(metric, "")
        target_txt = f"{target:.3f}" if isinstance(target, float) else ""
        dispatch_rows.append(
            f"| {metric} | {summary[metric]:.3f} | {target_txt} | {baseline.get(metric, 0.0):.3f} |"
        )

    cap_rows = ["| Carrier | Annual cap TWh | Source |", "|---|---:|---|"]
    for carrier, cap in annual_caps.items():
        cap_rows.append(
            f"| {carrier} | {cap:.3f} | {cfg.annual_generation_cap_sources.get(carrier, 'explicit_diagnostic_overlay')} |"
        )

    nuclear_rows = [
        "| Enabled | Carrier | Config p_max_pu | Implied target TWh | Applied p_max_pu | Generators | p_nom MW | p_max_pu before | p_max_pu after |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        "| "
        f"{nuclear_audit.enabled} | {nuclear_audit.carrier} | "
        f"{'' if nuclear_audit.configured_p_max_pu is None else f'{nuclear_audit.configured_p_max_pu:.6f}'} | "
        f"{nuclear_audit.target_annual_generation_twh:.3f} | "
        f"{nuclear_audit.target_p_max_pu:.6f} | "
        f"{nuclear_audit.generators} | {nuclear_audit.p_nom_mw:.3f} | "
        f"{nuclear_audit.before_p_max_pu:.6f} | {nuclear_audit.after_p_max_pu:.6f} |",
    ]

    scale_rows = [
        "| Carrier | Multiplier | Dynamic generators | Static generators | Profile-sum before | Profile-sum after |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for audit in scale_audits:
        scale_rows.append(
            "| "
            f"{audit.carrier} | {audit.multiplier:.3f} | "
            f"{audit.dynamic_generators} | {audit.static_generators} | "
            f"{audit.before_twh:.6f} | {audit.after_twh:.6f} |"
        )

    check_rows = ["| Gate | Status | Detail |", "|---|---|---|"]
    for name, passed, detail in checks:
        check_rows.append(f"| {name} | {'PASS' if passed else 'FAIL'} | {detail} |")

    content = f"""---
type: shared-log
date: '{now:%Y-%m-%d}'
time: '{now:%H:%M}'
created: '{now:%Y-%m-%d}'
actors:
  - Codex
workstreams:
  - pypsa-earth
---

# Shared Log - {now:%Y-%m-%d %H:%M}

## What Changed

- Ran `{cfg.label}` in [[6-codebases/repos/pypsa-earth]] by applying configured in-memory availability scaling and annual caps in the same optimization.
- Preserved the Module 13n source network at [[6-codebases/repos/pypsa-earth/{_relative(cfg.backup_network)}]].
- Wrote the solved network at [[6-codebases/repos/pypsa-earth/{_relative(cfg.output_network)}]].

## Inputs And Constraints

- Source network: [[6-codebases/repos/pypsa-earth/{_relative(cfg.source_network)}]]
- LOW-GAS OPC workbook: `{opc_workbook}`

{chr(10).join(cap_rows)}

{chr(10).join(scale_rows)}

## Nuclear Availability

{chr(10).join(nuclear_rows)}

## Solve Status

- Status: `{status} / {condition}`

## Dispatch Summary

{chr(10).join(dispatch_rows)}

## Acceptance Gates

{chr(10).join(check_rows)}

## Caveats

- Hydro/ROR summary includes generator carriers `hydro`/`ror` if present and hydro `StorageUnit` dispatch because the current accepted network stores hydro as storage units, not generator rows.
- Coal availability is owned by the upstream coal EAF CSV/network build; this
  standalone solve does not mutate coal availability.
- Diagnostic overlay settings are intentionally kept out of the main ZA validation config.
"""
    log_path.write_text(content, encoding="utf-8")
    return log_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--overlay",
        type=Path,
        help="Optional removable diagnostic YAML overlay.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    os.chdir(REPO_ROOT)
    cfg = load_run_config(args.overlay)
    backup_source_network(cfg)

    print(f"Loading source network: {_relative(cfg.source_network)}")
    n = pypsa.Network(cfg.source_network)
    baseline = dispatch_summary(n)

    print("Scaling VRE profiles in memory")
    scale_audits = scale_vre_profiles(n, cfg.vre_scale)
    for audit in scale_audits:
        print(
            f"  {audit.carrier}: x{audit.multiplier:.3f}, "
            f"dynamic={audit.dynamic_generators}, static={audit.static_generators}"
        )

    nuclear_audit = apply_nuclear_availability(
        n,
        cfg.nuclear_availability,
        cfg.annual_generation_caps_twh,
    )
    if nuclear_audit.enabled:
        print(
            "Applied nuclear availability: "
            f"p_max_pu {nuclear_audit.before_p_max_pu:.6f} -> "
            f"{nuclear_audit.after_p_max_pu:.6f} "
            f"for {nuclear_audit.target_annual_generation_twh:.3f} TWh target"
        )

    status, condition, opc_workbook, annual_caps = solve_module14(n, cfg)

    print(f"Exporting solved network: {_relative(cfg.output_network)}")
    cfg.output_network.parent.mkdir(parents=True, exist_ok=True)
    n.export_to_netcdf(cfg.output_network)

    summary = dispatch_summary(n)
    print()
    print(format_summary(status, condition, summary))

    checks = acceptance_checks(status, condition, baseline, summary, cfg)
    print()
    print("Acceptance gates:")
    for name, passed, detail in checks:
        print(f"  {'PASS' if passed else 'FAIL'} - {name}: {detail}")

    log_path = write_shared_log(
        status=status,
        condition=condition,
        baseline=baseline,
        summary=summary,
        scale_audits=scale_audits,
        nuclear_audit=nuclear_audit,
        opc_workbook=opc_workbook,
        annual_caps=annual_caps,
        checks=checks,
        cfg=cfg,
    )
    print(f"\nWrote shared log: {log_path.relative_to(VAULT_ROOT)}")

    failed = [name for name, passed, _ in checks if not passed]
    if failed:
        raise SystemExit(f"Module 14 acceptance gates failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
