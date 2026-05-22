# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Module 13m fleet-basis materialisation and audit helpers."""

from __future__ import annotations

import datetime as dt
import hashlib
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd

FLEET_MODES = {
    "rsa_var_hr_41p419",
    "eskom_nominal_2023",
    "calibrated_2023",
}

OFFICIAL_ESKOM_2023_NOMINAL_MW = {
    "Arnot": 2100.0,
    "Camden": 1481.0,
    "Duvha": 2875.0,
    "Grootvlei": 570.0,
    "Hendrina": 1098.0,
    "Kendal": 3840.0,
    "Komati": 0.0,
    "Kriel": 2640.0,
    "Kusile": 2880.0,
    "Lethabo": 3558.0,
    "Majuba": 3807.0,
    "Matimba": 3690.0,
    "Matla": 3450.0,
    "Medupi": 3600.0,
    "Tutuka": 3510.0,
}

CURRENT_RSA_VAR_HR_MW = {
    "Arnot": 2100.0,
    "Camden": 1481.0,
    "Duvha": 2875.0,
    "Grootvlei": 570.0,
    "Hendrina": 1098.0,
    "Kelvin": 160.0,
    "Kendal": 3840.0,
    "Kriel": 2640.0,
    "Kusile": 4320.0,
    "Lethabo": 3558.0,
    "Majuba": 3807.0,
    "Matimba": 3690.0,
    "Matla": 3450.0,
    "Medupi": 4320.0,
    "Tutuka": 3510.0,
}

SASOL_ASSETS = [
    {
        "station_or_asset": "Secunda_coal",
        "carrier": "sasol_coal",
        "p_nom_mw": 600.04,
        "lat": -26.5036,
        "lon": 29.1803,
        "source_evidence": "pypsa-rsa Benchmark_2023 fixed_technologies.xlsx VAR_HR",
    },
    {
        "station_or_asset": "Sasolburg_coal",
        "carrier": "sasol_coal",
        "p_nom_mw": 128.00,
        "lat": -26.5036,
        "lon": 29.1803,
        "source_evidence": "pypsa-rsa Benchmark_2023 fixed_technologies.xlsx VAR_HR",
    },
    {
        "station_or_asset": "Sasol_ice",
        "carrier": "sasol_gas",
        "p_nom_mw": 174.60,
        "lat": -26.8102,
        "lon": 27.8277,
        "source_evidence": "pypsa-rsa Benchmark_2023 fixed_technologies.xlsx VAR_HR",
    },
    {
        "station_or_asset": "Sasol_ocgt",
        "carrier": "sasol_gas",
        "p_nom_mw": 250.00,
        "lat": -26.8102,
        "lon": 27.8277,
        "source_evidence": "pypsa-rsa Benchmark_2023 fixed_technologies.xlsx VAR_HR",
    },
]

AUDIT_COLUMNS = [
    "mode",
    "sasol_enabled",
    "source_file",
    "station_or_asset",
    "carrier",
    "p_nom_mw",
    "official_eskom_2023_nominal_mw",
    "rsa_var_hr_mw",
    "current_model_previous_mw",
    "difference_vs_official_mw",
    "difference_vs_rsa_var_hr_mw",
    "included_in_coal_uc",
    "included_in_eskom_coal_validation",
    "bus",
    "source_class",
    "source_evidence",
    "notes",
]

BACKUP_MANIFEST_COLUMNS = [
    "created_at",
    "source_path",
    "backup_path",
    "source_sha256",
    "backup_sha256",
    "source_rows",
    "backup_rows",
    "reason",
    "git_status_summary",
]


def station_key(name: str) -> str:
    """Normalize custom-powerplant split names such as ``Hendrina_2``."""
    text = str(name).strip()
    parts = text.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0]
    return text


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resolved_config(config: dict[str, Any]) -> dict[str, Any]:
    cfg = config.get("za_2023_fleet_calibration", {}) or {}
    coal_cfg = cfg.get("coal_fleet", {}) or {}
    custom_cfg = cfg.get("custom_powerplants", {}) or {}
    sasol_cfg = cfg.get("sasol", {}) or {}

    requested_mode = str(coal_cfg.get("mode", "calibrated_2023"))
    if requested_mode not in FLEET_MODES:
        raise ValueError(
            f"Unknown za_2023_fleet_calibration.coal_fleet.mode={requested_mode!r}"
        )
    effective_mode = (
        "eskom_nominal_2023"
        if requested_mode == "calibrated_2023"
        else requested_mode
    )
    return {
        "enable": bool(cfg.get("enable", False)),
        "requested_mode": requested_mode,
        "effective_mode": effective_mode,
        "include_kelvin": bool(coal_cfg.get("include_kelvin", False)),
        "sasol_enabled": bool(sasol_cfg.get("enable", False)),
        "custom_powerplants_path": Path(
            custom_cfg.get("path", "data/custom_powerplants.csv")
        ),
        "backup_before_mutation": bool(
            custom_cfg.get("backup_before_mutation", True)
        ),
        "backup_dir": Path(custom_cfg.get("backup_dir", "data/za_audit/backups")),
    }


def selected_coal_capacities(
    mode: str,
    *,
    include_kelvin: bool = False,
) -> dict[str, float]:
    if mode == "rsa_var_hr_41p419":
        return dict(CURRENT_RSA_VAR_HR_MW)
    if mode != "eskom_nominal_2023":
        raise ValueError(f"Unsupported effective fleet mode {mode!r}")

    caps = {k: v for k, v in OFFICIAL_ESKOM_2023_NOMINAL_MW.items() if v > 0}
    if include_kelvin:
        caps["Kelvin"] = CURRENT_RSA_VAR_HR_MW["Kelvin"]
    return caps


def _row_count(path: Path) -> int:
    return int(len(pd.read_csv(path)))


def _git_status(path: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "status", "--short", "--", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return f"git_status_unavailable:{exc}"
    return proc.stdout.strip().replace("\n", " | ")


def backup_custom_powerplants(
    source: Path,
    backup_dir: Path,
    manifest_path: Path,
    *,
    reason: str,
) -> Path:
    if not source.exists():
        raise FileNotFoundError(f"custom_powerplants source is missing: {source}")

    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"custom_powerplants_pre_13m_{timestamp}.csv"
    shutil.copy2(source, backup_path)

    source_hash = sha256_of_file(source)
    backup_hash = sha256_of_file(backup_path)
    source_rows = _row_count(source)
    backup_rows = _row_count(backup_path)
    if source_hash != backup_hash or source_rows != backup_rows:
        raise RuntimeError(
            "custom_powerplants backup gate failed: "
            f"source_hash={source_hash}, backup_hash={backup_hash}, "
            f"source_rows={source_rows}, backup_rows={backup_rows}"
        )

    row = {
        "created_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_path": str(source),
        "backup_path": str(backup_path),
        "source_sha256": source_hash,
        "backup_sha256": backup_hash,
        "source_rows": source_rows,
        "backup_rows": backup_rows,
        "reason": reason,
        "git_status_summary": _git_status(source),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    existing = (
        pd.read_csv(manifest_path, dtype=str)
        if manifest_path.exists()
        else pd.DataFrame(columns=BACKUP_MANIFEST_COLUMNS)
    )
    out = pd.concat([existing, pd.DataFrame([row])], ignore_index=True)
    out = out.reindex(columns=BACKUP_MANIFEST_COLUMNS)
    out.to_csv(manifest_path, index=False)
    return backup_path


def materialise_custom_powerplants(
    current: pd.DataFrame,
    *,
    mode: str,
    include_kelvin: bool,
) -> pd.DataFrame:
    if "Name" not in current.columns or "Fueltype" not in current.columns:
        raise ValueError("custom_powerplants.csv must contain Name and Fueltype columns")

    current = current.copy()
    current["Name"] = current["Name"].astype(str)
    coal_mask = current["Fueltype"].astype(str).eq("Hard Coal")
    station = current["Name"].map(station_key)
    selected_caps = selected_coal_capacities(mode, include_kelvin=include_kelvin)

    if mode == "rsa_var_hr_41p419":
        return current

    keep = ~coal_mask
    coal = current.loc[coal_mask].copy()
    coal["_station"] = coal["Name"].map(station_key)
    coal["_capacity"] = pd.to_numeric(coal["Capacity"], errors="raise")

    calibrated_rows: list[pd.DataFrame] = []
    for station_name, target_capacity in selected_caps.items():
        rows = coal[coal["_station"] == station_name].copy()
        if rows.empty:
            continue
        if station_name in {"Kusile", "Medupi"}:
            unsuffixed = rows[~rows["Name"].str.contains(r"_\d+$", regex=True)].copy()
            if not unsuffixed.empty:
                rows = unsuffixed
        source_total = float(rows["_capacity"].sum())
        if source_total <= 0:
            raise ValueError(f"Non-positive custom split total for {station_name}")
        rows["Capacity"] = rows["_capacity"] / source_total * float(target_capacity)
        calibrated_rows.append(rows.drop(columns=["_station", "_capacity"]))

    out = pd.concat([current.loc[keep], *calibrated_rows], ignore_index=True)
    return out.reindex(columns=current.columns)


def _station_buses(df: pd.DataFrame, station_name: str) -> str:
    if "bus" not in df.columns:
        return ""
    mask = df["Name"].map(station_key).eq(station_name)
    buses = sorted({str(v) for v in df.loc[mask, "bus"].dropna() if str(v).strip()})
    return "|".join(buses)


def build_fleet_audit(
    *,
    original: pd.DataFrame,
    selected: pd.DataFrame,
    mode: str,
    requested_mode: str,
    sasol_enabled: bool,
    source_file: Path,
    include_kelvin: bool,
) -> pd.DataFrame:
    selected_caps = selected_coal_capacities(mode, include_kelvin=include_kelvin)
    original_coal = original[original["Fueltype"].astype(str).eq("Hard Coal")].copy()
    selected_coal = selected[selected["Fueltype"].astype(str).eq("Hard Coal")].copy()
    original_coal["station"] = original_coal["Name"].map(station_key)
    selected_coal["station"] = selected_coal["Name"].map(station_key)
    original_totals = (
        pd.to_numeric(original_coal["Capacity"], errors="coerce")
        .groupby(original_coal["station"])
        .sum()
        .to_dict()
    )
    selected_totals = (
        pd.to_numeric(selected_coal["Capacity"], errors="coerce")
        .groupby(selected_coal["station"])
        .sum()
        .to_dict()
    )

    rows: list[dict[str, Any]] = []
    stations = sorted(
        set(OFFICIAL_ESKOM_2023_NOMINAL_MW)
        | set(CURRENT_RSA_VAR_HR_MW)
        | set(selected_caps)
        | set(original_totals)
    )
    for station_name in stations:
        selected_mw = float(selected_totals.get(station_name, 0.0))
        official_mw = float(OFFICIAL_ESKOM_2023_NOMINAL_MW.get(station_name, 0.0))
        rsa_mw = float(CURRENT_RSA_VAR_HR_MW.get(station_name, 0.0))
        current_mw = float(original_totals.get(station_name, 0.0))
        included = selected_mw > 0
        rows.append(
            {
                "mode": requested_mode,
                "sasol_enabled": sasol_enabled,
                "source_file": str(source_file),
                "station_or_asset": station_name,
                "carrier": "coal",
                "p_nom_mw": selected_mw,
                "official_eskom_2023_nominal_mw": official_mw,
                "rsa_var_hr_mw": rsa_mw,
                "current_model_previous_mw": current_mw,
                "difference_vs_official_mw": selected_mw - official_mw,
                "difference_vs_rsa_var_hr_mw": selected_mw - rsa_mw,
                "included_in_coal_uc": bool(included),
                "included_in_eskom_coal_validation": bool(
                    included and station_name in OFFICIAL_ESKOM_2023_NOMINAL_MW
                ),
                "bus": _station_buses(selected_coal, station_name),
                "source_class": (
                    "official_eskom_2023_nominal"
                    if mode == "eskom_nominal_2023"
                    else "pypsa_rsa_var_hr"
                ),
                "source_evidence": (
                    "Eskom Integrated Report 2023 plant information"
                    if mode == "eskom_nominal_2023"
                    else "pypsa-rsa Benchmark_2023 fixed_technologies.xlsx VAR_HR"
                ),
                "notes": (
                    "calibrated_2023 aliases eskom_nominal_2023"
                    if requested_mode == "calibrated_2023"
                    else ""
                ),
            }
        )

    for asset in SASOL_ASSETS:
        rows.append(
            {
                "mode": requested_mode,
                "sasol_enabled": sasol_enabled,
                "source_file": str(source_file),
                "station_or_asset": asset["station_or_asset"],
                "carrier": asset["carrier"],
                "p_nom_mw": asset["p_nom_mw"] if sasol_enabled else 0.0,
                "official_eskom_2023_nominal_mw": "",
                "rsa_var_hr_mw": asset["p_nom_mw"],
                "current_model_previous_mw": 0.0,
                "difference_vs_official_mw": "",
                "difference_vs_rsa_var_hr_mw": (
                    0.0 if sasol_enabled else -float(asset["p_nom_mw"])
                ),
                "included_in_coal_uc": False,
                "included_in_eskom_coal_validation": False,
                "bus": "",
                "source_class": "pypsa_rsa_sasol_diagnostic",
                "source_evidence": asset["source_evidence"],
                "notes": (
                    "optional non-UC Sasol diagnostic enabled"
                    if sasol_enabled
                    else "optional non-UC Sasol diagnostic disabled"
                ),
            }
        )

    return pd.DataFrame(rows).reindex(columns=AUDIT_COLUMNS)


def run_materialisation(
    *,
    config: dict[str, Any],
    selected_out: Path,
    audit_out: Path,
    backup_manifest: Path,
) -> dict[str, Any]:
    cfg = resolved_config(config)
    source = cfg["custom_powerplants_path"]
    if not source.exists():
        raise FileNotFoundError(f"custom_powerplants.csv not found: {source}")

    original = pd.read_csv(source)
    if cfg["enable"] and cfg["backup_before_mutation"]:
        backup_custom_powerplants(
            source,
            cfg["backup_dir"],
            backup_manifest,
            reason=(
                "Module 13m before fleet-basis materialisation "
                f"({cfg['requested_mode']}, sasol={cfg['sasol_enabled']})"
            ),
        )

    selected = materialise_custom_powerplants(
        original,
        mode=cfg["effective_mode"],
        include_kelvin=cfg["include_kelvin"],
    )
    selected_out.parent.mkdir(parents=True, exist_ok=True)
    selected.to_csv(selected_out, index=False, float_format="%.6f")

    if cfg["enable"]:
        selected.to_csv(source, index=False, float_format="%.6f")

    audit = build_fleet_audit(
        original=original,
        selected=selected,
        mode=cfg["effective_mode"],
        requested_mode=cfg["requested_mode"],
        sasol_enabled=cfg["sasol_enabled"],
        source_file=source,
        include_kelvin=cfg["include_kelvin"],
    )
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(audit_out, index=False, float_format="%.6f")
    return {
        "mode": cfg["requested_mode"],
        "effective_mode": cfg["effective_mode"],
        "sasol_enabled": cfg["sasol_enabled"],
        "custom_powerplants_rows": len(selected),
        "coal_p_nom_mw": float(
            audit.loc[
                (audit["carrier"] == "coal") & (audit["included_in_coal_uc"]),
                "p_nom_mw",
            ].sum()
        ),
    }
