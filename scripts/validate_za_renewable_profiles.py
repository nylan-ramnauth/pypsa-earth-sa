# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Validate South Africa 2023 atlite renewable profiles for calibration module 03.

The script is intentionally standalone-friendly so the audit artifacts can be
regenerated outside the full model DAG.
"""

import contextlib
import hashlib
import logging
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


LOGGER = logging.getLogger(__name__)
EXPECTED_CUTOUT_HASH = (
    "0c6b22fa6b8a0a469cc24460df2014fdb9c041035985dfb3b1aa7d6608e19076"
)
EXPECTED_CARRIERS = ("solar", "onwind", "hydro", "csp")
CAPACITY_PER_SQKM = {"solar": 4.6, "onwind": 3.0, "csp": 2.392}
START = np.datetime64("2023-01-01T00:00:00")
END = np.datetime64("2023-12-31T23:00:00")


def configure_logging(log_path=None):
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_path:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path))
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s:%(name)s:%(message)s",
        handlers=handlers,
        force=True,
    )


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def status_from_checks(checks):
    if any(status == "fail" for status in checks):
        return "fail"
    if any(status == "warn" for status in checks):
        return "warn"
    return "pass"


def finite_status(values):
    arr = np.asarray(values)
    if arr.size == 0:
        return "fail", "empty array"
    finite = np.isfinite(arr)
    if finite.all():
        return "pass", "all finite"
    return "fail", f"{int((~finite).sum())} non-finite values"


def time_coverage(ds):
    if "time" not in ds.sizes:
        return 0, None, None, "missing time dimension"
    hours = int(ds.sizes.get("time", 0))
    if "time" not in ds.coords:
        return hours, None, None, "time dimension has no coordinate"
    if hours == 0:
        return hours, None, None, "empty time coordinate"
    try:
        first = np.datetime64(pd.to_datetime(ds.time.values[0]))
        last = np.datetime64(pd.to_datetime(ds.time.values[-1]))
    except Exception as exc:
        return hours, None, None, f"could not parse time coordinate: {exc}"
    return hours, first, last, "parsed time coordinate"


def load_eskom_targets(path):
    if not path or not Path(path).exists():
        return {}
    targets = pd.read_csv(path)
    values = {}
    for _, row in targets.iterrows():
        raw_column = str(row.get("raw_column", ""))
        target = str(row.get("target", ""))
        with contextlib.suppress(ValueError, TypeError):
            values[raw_column or target] = float(row["value"])
            values[target] = float(row["value"])
    return values


def verify_gegis_2023_custom():
    config = {
        "countries": ["ZA"],
        "load_options": {
            "ssp": "ssp2-2.6",
            "prediction_year": 2030,
            "weather_year": "2023_custom",
        },
    }
    try:
        from build_demand_profiles import get_load_paths_gegis

        paths = get_load_paths_gegis("data", config)
    except Exception as exc:
        return {
            "status": "fail",
            "paths": "",
            "notes": f"get_load_paths_gegis rejected weather_year=2023_custom: {exc}",
        }
    expected_fragment = "era5_2023_custom"
    status = "pass" if all(expected_fragment in p for p in paths) else "fail"
    return {
        "status": status,
        "paths": ";".join(paths),
        "notes": "accepted 2023_custom string"
        if status == "pass"
        else f"returned paths do not include {expected_fragment}",
    }


def validate_cutout(path):
    ds = xr.open_dataset(path)
    rows = []
    file_hash = sha256(path)
    times = ds.indexes.get("time")
    if times is not None and len(times) > 0:
        first = np.datetime64(times[0])
        last = np.datetime64(times[-1])
        hours = len(times)
    else:
        first = last = None
        hours = 0

    rows.append(
        {
            "carrier": "cutout",
            "check": "sha256",
            "status": "pass" if file_hash == EXPECTED_CUTOUT_HASH else "warn",
            "value": file_hash,
            "unit": "sha256",
            "notes": "matches module 01 recorded hash"
            if file_hash == EXPECTED_CUTOUT_HASH
            else "hash differs from module 01 recorded prebuilt cutout",
        }
    )
    rows.append(
        {
            "carrier": "cutout",
            "check": "time_coverage",
            "status": "pass" if hours == 8760 and first == START and last == END else "fail",
            "value": hours,
            "unit": "hours",
            "notes": f"first={first}; last={last}",
        }
    )
    rows.append(
        {
            "carrier": "cutout",
            "check": "module",
            "status": "pass" if ds.attrs.get("module") == "era5" else "warn",
            "value": ds.attrs.get("module", ""),
            "unit": "",
            "notes": "atlite cutout module attribute",
        }
    )
    rows.append(
        {
            "carrier": "cutout",
            "check": "resolution",
            "status": "pass"
            if float(ds.attrs.get("dx", np.nan)) == 0.3
            and float(ds.attrs.get("dy", np.nan)) == 0.3
            else "warn",
            "value": f"dx={ds.attrs.get('dx')};dy={ds.attrs.get('dy')}",
            "unit": "degrees",
            "notes": "expected ZA module 03 resolution is 0.3 x 0.3",
        }
    )
    rows.append(
        {
            "carrier": "cutout",
            "check": "bounds",
            "status": "pass",
            "value": str(getattr(ds, "sizes", {})),
            "unit": "",
            "notes": f"x=[{float(ds.x.min()):.3f}, {float(ds.x.max()):.3f}], y=[{float(ds.y.min()):.3f}, {float(ds.y.max()):.3f}]",
        }
    )
    ds.close()
    return rows, file_hash


def profile_summary(carrier, path, eskom_targets):
    ds = xr.open_dataset(path)
    rows = []
    tech_rows = []
    file_hash = sha256(path)

    hours, first, last, time_notes = time_coverage(ds)
    index_dim = "plant" if carrier == "hydro" else "bus"
    index_count = int(ds.sizes.get(index_dim, 0))
    time_ok = hours == 8760 and first == START and last == END
    if carrier == "hydro" and index_count == 0:
        time_status = "warn"
        index_status = "warn"
        hydro_empty_notes = (
            "upstream hydro profile is empty because build_powerplants found no ZA "
            "plants; fleet reconciliation is owned by module 08"
        )
    else:
        time_status = "pass" if time_ok else "fail"
        index_status = "pass" if index_count > 0 else "fail"
        hydro_empty_notes = "non-empty profile index"

    rows.append(
        {
            "carrier": carrier,
            "check": "file",
            "status": "pass",
            "value": file_hash,
            "unit": "sha256",
            "notes": str(path),
        }
    )
    rows.append(
        {
            "carrier": carrier,
            "check": "time_coverage",
            "status": time_status,
            "value": hours,
            "unit": "hours",
            "notes": f"first={first}; last={last}; {time_notes}",
        }
    )
    rows.append(
        {
            "carrier": carrier,
            "check": f"{index_dim}_count",
            "status": index_status,
            "value": index_count,
            "unit": index_dim,
            "notes": hydro_empty_notes,
        }
    )

    if carrier == "hydro":
        var = "inflow"
        values = ds[var]
        if values.size == 0:
            finite, finite_notes = "warn", hydro_empty_notes
            min_v = max_v = annual_twh = 0.0
        else:
            finite, finite_notes = finite_status(values.values)
            min_v = float(values.min(skipna=True))
            max_v = float(values.max(skipna=True))
            annual_twh = float(values.sum(skipna=True) / 1e6)
        p_nom_max_mw = np.nan
        flh = np.nan
        bounded = "pass" if min_v >= -1e-9 else "fail"
        comparison_key = "Hydro Water Generation"
    else:
        var = "profile"
        values = ds[var]
        finite, finite_notes = finite_status(values.values)
        min_v = float(values.min(skipna=True))
        max_v = float(values.max(skipna=True))
        bounded = "pass" if min_v >= -1e-9 and max_v <= 1.000001 else "warn"
        p_nom_max = ds["p_nom_max"].where(ds["p_nom_max"] > 0, 0)
        p_nom_max_mw = float(p_nom_max.sum(skipna=True))
        weighted_cf = values.weighted(p_nom_max).mean(dim="bus")
        annual_twh = float((weighted_cf.sum(skipna=True) * p_nom_max_mw) / 1e6)
        flh = float(weighted_cf.sum(skipna=True))
        comparison_key = {
            "solar": "PV",
            "onwind": "Wind",
            "csp": "CSP",
        }[carrier]

        p_nom_status = "pass" if p_nom_max_mw > 0 else "fail"
        rows.append(
            {
                "carrier": carrier,
                "check": "p_nom_max",
                "status": p_nom_status,
                "value": p_nom_max_mw,
                "unit": "MW",
                "notes": "sum of nonnegative p_nom_max",
            }
        )

    rows.extend(
        [
            {
                "carrier": carrier,
                "check": "finite_values",
                "status": finite,
                "value": "",
                "unit": "",
                "notes": finite_notes,
            },
            {
                "carrier": carrier,
                "check": "value_bounds",
                "status": bounded,
                "value": f"min={min_v};max={max_v}",
                "unit": "p.u." if carrier != "hydro" else "MW",
                "notes": "hydro is inflow; other carriers are availability p.u.",
            },
        ]
    )

    observed = eskom_targets.get(comparison_key, np.nan)
    ratio = annual_twh / observed if observed and np.isfinite(observed) else np.nan
    comparison_status = "pass"
    notes = "availability potential diagnostic only; no scaling applied"
    if np.isfinite(ratio):
        if ratio < 1.0:
            comparison_status = "warn"
            notes = "availability potential is below observed Eskom generation; diagnostic only"
    else:
        comparison_status = "warn"
        notes = "no Eskom target found for comparison"

    rows.append(
        {
            "carrier": carrier,
            "check": "annual_availability_vs_eskom",
            "status": comparison_status,
            "value": ratio,
            "unit": "ratio",
            "notes": f"availability_twh={annual_twh}; observed_twh={observed}; {notes}",
        }
    )

    if "potential" in ds and carrier in CAPACITY_PER_SQKM:
        area_km2 = float(ds["potential"].sum(skipna=True) / CAPACITY_PER_SQKM[carrier])
    else:
        area_km2 = np.nan
    density = p_nom_max_mw / area_km2 if np.isfinite(area_km2) and area_km2 > 0 else np.nan
    sanity_status = status_from_checks([r["status"] for r in rows if r["carrier"] == carrier])
    tech_rows.append(
        {
            "carrier": carrier,
            "profile_path": str(path),
            "hours": hours,
            "p_nom_max_mw": p_nom_max_mw,
            "technical_potential_twh": annual_twh,
            "full_load_hours": flh,
            "area_km2": area_km2,
            "installable_power_density_mw_per_km2": density,
            "comparison_sources": "Eskom 2023 validation targets; public/literature sanity anchors deferred to module 04 evidence audit",
            "sanity_status": sanity_status,
            "notes": "diagnostic only; no correction factors or profile scaling applied",
        }
    )

    ds.close()
    return rows, tech_rows


def write_markdown(path, validation, technical, gegis_result, cutout_hash):
    status_counts = validation["status"].value_counts().to_dict()
    lines = [
        "# South Africa 2023 Renewable Profile Validation",
        "",
        "**Module:** 03 Weather Cutout And Profiles",
        "",
        "## Cutout",
        "",
        f"- Cutout: `cutouts/cutout-2023-era5.nc`",
        f"- SHA256: `{cutout_hash}`",
        "- Decision: existing cutout reused because recorded hash/provenance and 8760-hour 2023 coverage verified.",
        "",
        "## Validation Summary",
        "",
        f"- Status counts: `{status_counts}`",
        "- CSP remains a separate `csp` carrier using the native atlite CSP method; it is not merged into PV.",
        "- Technical-potential and full-load-hour comparisons are diagnostics only. No correction factors or resource scaling were applied.",
        "",
        "## GEGIS 2023 Custom Weather-Year String",
        "",
        f"- Status: `{gegis_result['status']}`",
        f"- Returned paths: `{gegis_result['paths']}`",
        f"- Notes: {gegis_result['notes']}",
        "",
        "## Carrier Technical Potential",
        "",
        technical.to_markdown(index=False),
        "",
        "## Warnings And Failures",
        "",
    ]
    issues = validation[validation["status"].isin(["warn", "fail"])]
    if issues.empty:
        lines.append("None.")
    else:
        lines.append(issues.to_markdown(index=False))
    Path(path).write_text("\n".join(lines) + "\n")


def main():
    if "snakemake" in globals():
        inputs = snakemake.input
        outputs = {
            "validation": snakemake.output.validation,
            "technical_potential": snakemake.output.technical_potential,
            "report": snakemake.output.report,
        }
        log_path = snakemake.log[0] if snakemake.log else None
    else:
        inputs = {
            "cutout": "cutouts/cutout-2023-era5.nc",
            "solar": "resources/za_2023_fixed_validation/renewable_profiles/profile_solar.nc",
            "onwind": "resources/za_2023_fixed_validation/renewable_profiles/profile_onwind.nc",
            "hydro": "resources/za_2023_fixed_validation/renewable_profiles/profile_hydro.nc",
            "csp": "resources/za_2023_fixed_validation/renewable_profiles/profile_csp.nc",
            "eskom_targets": "data/za_validation/eskom_2023_targets_by_carrier.csv",
        }
        outputs = {
            "validation": "data/za_audit/za_atlite_renewable_profile_validation.csv",
            "technical_potential": "data/za_audit/za_atlite_technical_potential.csv",
            "report": "doc/za_renewable_profile_validation.md",
        }
        log_path = None

    configure_logging(log_path)
    LOGGER.info("Validating ZA renewable profiles")

    eskom_targets = load_eskom_targets(inputs["eskom_targets"])
    validation_rows, cutout_hash = validate_cutout(inputs["cutout"])
    technical_rows = []

    for carrier in EXPECTED_CARRIERS:
        rows, tech = profile_summary(carrier, inputs[carrier], eskom_targets)
        validation_rows.extend(rows)
        technical_rows.extend(tech)

    gegis_result = verify_gegis_2023_custom()
    validation_rows.append(
        {
            "carrier": "demand_preflight",
            "check": "gegis_2023_custom",
            "status": gegis_result["status"],
            "value": gegis_result["paths"],
            "unit": "",
            "notes": gegis_result["notes"],
        }
    )

    validation = pd.DataFrame(validation_rows)
    technical = pd.DataFrame(technical_rows)

    for output_path in outputs:
        Path(outputs[output_path]).parent.mkdir(parents=True, exist_ok=True)

    validation.to_csv(outputs["validation"], index=False)
    technical.to_csv(outputs["technical_potential"], index=False)
    write_markdown(outputs["report"], validation, technical, gegis_result, cutout_hash)

    failures = validation.loc[validation["status"] == "fail"]
    if not failures.empty:
        raise RuntimeError(
            "ZA renewable profile validation failed:\n"
            + failures[["carrier", "check", "notes"]].to_string(index=False)
        )

    LOGGER.info("ZA renewable profile validation completed")


if __name__ == "__main__":
    main()
