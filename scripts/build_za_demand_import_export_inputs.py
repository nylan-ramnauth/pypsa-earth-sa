# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build ZA 2023 demand, import/export, and exogenous Other RE inputs."""

import argparse
import csv
import datetime as dt
import hashlib
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

logger = logging.getLogger("build_za_demand_import_export_inputs")

DATA_VALIDATION = Path("data/za_validation")
DATA_AUDIT = Path("data/za_audit")
GEGIS_OUTPUT = Path("data/ssp2-2.6/2030/era5_2023_custom/Africa.csv")
REPORT_OUTPUT = Path("doc/za_demand_import_export_model_inputs.md")
SOURCE_HASHES = DATA_AUDIT / "source_hashes.csv"
INPUT_MANIFEST = DATA_AUDIT / "input_file_manifest.csv"

ESKOM_HOURLY = DATA_VALIDATION / "eskom_2023_hourly_clean.csv"
ESKOM_TARGETS = DATA_VALIDATION / "eskom_2023_targets_by_carrier.csv"
RSA_LOAD_AUDIT = DATA_AUDIT / "pypsa_rsa_load_weight_audit.csv"

DEMAND_OUTPUT = DATA_VALIDATION / "za_2023_demand_profile.csv"
IMPORT_EXPORT_OUTPUT = DATA_VALIDATION / "za_2023_import_export_timeseries.csv"
OTHER_RE_OUTPUT = DATA_VALIDATION / "za_2023_other_re_timeseries.csv"
LOAD_WEIGHTS_OUTPUT = DATA_AUDIT / "za_2023_load_allocation_weights.csv"
RSA_COMPARISON_OUTPUT = DATA_AUDIT / "pypsa_rsa_gva_pop_load_weight_comparison.csv"
IMPORT_EXPORT_ATTACHMENT_OUTPUT = DATA_AUDIT / "za_2023_import_export_attachment.csv"
OTHER_RE_ATTACHMENT_OUTPUT = DATA_AUDIT / "za_2023_other_re_attachment.csv"

DATE_COLUMN = "Date Time Hour Beginning"
EXPECTED_HOURS = 8760
START = pd.Timestamp("2023-01-01 00:00:00")
END = pd.Timestamp("2023-12-31 23:00:00")
TWH_TOL = 1e-6
WEIGHT_TOL = 1e-9

REQUIRED_ESKOM_COLUMNS = [
    DATE_COLUMN,
    "RSA Contracted Demand",
    "International Imports",
    "International Exports",
    "Other RE",
]

ATTACHMENT_COLUMNS = [
    "layer_key",
    "attachment_type",
    "source_id",
    "target_region_id",
    "weight",
    "source_file",
    "source_hash",
    "notes",
]


def sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_config(path: Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M local")


def _validate_hourly(clean: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in REQUIRED_ESKOM_COLUMNS if column not in clean.columns]
    if missing:
        raise ValueError(f"Missing required Eskom columns: {missing}")
    clean = clean.copy()
    clean[DATE_COLUMN] = pd.to_datetime(clean[DATE_COLUMN], errors="raise")
    clean = clean.sort_values(DATE_COLUMN).reset_index(drop=True)
    if len(clean) != EXPECTED_HOURS:
        raise ValueError(f"Expected {EXPECTED_HOURS} Eskom rows, found {len(clean)}.")
    if clean[DATE_COLUMN].iloc[0] != START or clean[DATE_COLUMN].iloc[-1] != END:
        raise ValueError(
            f"Unexpected Eskom time range: {clean[DATE_COLUMN].iloc[0]} to {clean[DATE_COLUMN].iloc[-1]}."
        )
    expected = pd.date_range(START, END, freq="h")
    if not clean[DATE_COLUMN].equals(pd.Series(expected)):
        missing_hours = expected.difference(clean[DATE_COLUMN])
        duplicate_hours = clean.loc[clean[DATE_COLUMN].duplicated(), DATE_COLUMN].tolist()
        raise ValueError(f"Eskom hourly index is not complete. Missing={missing_hours[:5]}, duplicates={duplicate_hours[:5]}")
    for column in REQUIRED_ESKOM_COLUMNS[1:]:
        clean[column] = pd.to_numeric(clean[column], errors="raise")
    return clean


def _target_value(targets: pd.DataFrame, target: str, unit: str | None = None) -> float:
    rows = targets.loc[targets["target"] == target]
    if unit is not None:
        rows = rows.loc[rows["unit"] == unit]
    if rows.empty:
        raise ValueError(f"Missing target row: {target!r}, unit={unit!r}")
    return float(rows.iloc[0]["value"])


def _write_demand(clean: pd.DataFrame, targets: pd.DataFrame) -> dict:
    out = pd.DataFrame(
        {
            "time": clean[DATE_COLUMN].dt.strftime("%Y-%m-%d %H:%M:%S"),
            "rsa_contracted_demand_mw": clean["RSA Contracted Demand"],
        }
    )
    DEMAND_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(DEMAND_OUTPUT, index=False, float_format="%.9f")

    gegis = pd.DataFrame(
        {
            "region_code": "ZA",
            "time": clean[DATE_COLUMN].dt.strftime("%Y-%m-%d %H:%M:%S"),
            "region_name": "South Africa",
            "Electricity demand": clean["RSA Contracted Demand"],
        }
    )
    GEGIS_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    gegis.to_csv(GEGIS_OUTPUT, index=False, sep=";", float_format="%.9f")

    demand_twh = float(clean["RSA Contracted Demand"].sum() / 1e6)
    target_twh = _target_value(targets, "RSA Contracted Demand", "TWh")
    if abs(demand_twh - target_twh) > TWH_TOL:
        raise ValueError(f"Demand TWh mismatch: output={demand_twh}, target={target_twh}")
    return {"demand_twh": demand_twh, "target_twh": target_twh}


def _write_import_export(clean: pd.DataFrame) -> dict:
    out = pd.DataFrame(
        {
            "time": clean[DATE_COLUMN].dt.strftime("%Y-%m-%d %H:%M:%S"),
            "international_imports_mw": clean["International Imports"],
            "international_exports_mw": clean["International Exports"],
        }
    )
    out["net_import_mw"] = out["international_imports_mw"] - out["international_exports_mw"]
    out.to_csv(IMPORT_EXPORT_OUTPUT, index=False, float_format="%.9f")
    return {
        "imports_twh": float(clean["International Imports"].sum() / 1e6),
        "exports_twh": float(clean["International Exports"].sum() / 1e6),
        "net_import_twh": float((clean["International Imports"] - clean["International Exports"]).sum() / 1e6),
    }


def _write_other_re(clean: pd.DataFrame, targets: pd.DataFrame) -> dict:
    p_nom = _target_value(targets, "Other RE installed capacity", "MW")
    if p_nom <= 0:
        raise ValueError(f"Other RE p_nom must be positive, found {p_nom}")
    raw_ratio = clean["Other RE"] / p_nom
    clipped = raw_ratio.clip(lower=0, upper=1)
    out = pd.DataFrame(
        {
            "time": clean[DATE_COLUMN].dt.strftime("%Y-%m-%d %H:%M:%S"),
            "other_re_mw": clean["Other RE"],
            "p_nom_mw": p_nom,
            "p_max_pu_unclipped": raw_ratio,
            "p_max_pu": clipped,
            "p_min_pu": 0.0,
            "was_clipped": np.abs(clipped - raw_ratio) > 1e-12,
        }
    )
    out.to_csv(OTHER_RE_OUTPUT, index=False, float_format="%.9f")
    daily_max_ratio = (
        pd.Series(raw_ratio.to_numpy(), index=clean[DATE_COLUMN])
        .resample("D")
        .max()
        .max()
    )
    return {
        "other_re_twh": float(clean["Other RE"].sum() / 1e6),
        "p_nom_mw": p_nom,
        "max_unclipped_ratio": float(raw_ratio.max()),
        "daily_max_ratio": float(daily_max_ratio),
        "clipped_hours": int(out["was_clipped"].sum()),
        "warning": bool(daily_max_ratio > 1.05),
    }


def _valid_geometries(series):
    from shapely.validation import make_valid

    return series.apply(lambda geom: make_valid(geom) if geom is not None else geom)


def _pypsa_earth_style_weights(config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    import fiona
    import geopandas as gpd

    pypsa_rsa_root = Path(config["pypsa_rsa_root"])
    gpkg = pypsa_rsa_root / "data" / "bundle" / "supply_regions" / "rsa_supply_regions.gpkg"
    gadm = Path("resources") / config["run"]["name"] / "shapes" / "gadm_shapes.geojson"
    if not gpkg.exists():
        raise FileNotFoundError(f"Missing PyPSA-RSA supply regions: {gpkg}")
    if not gadm.exists():
        raise FileNotFoundError(f"Missing PyPSA-Earth GADM shapes: {gadm}")

    layers = set(fiona.listlayers(str(gpkg)))
    admin = gpd.read_file(gadm)
    admin = admin.loc[admin["country"] == "ZA"].copy()
    admin["geometry"] = _valid_geometries(admin["geometry"])
    admin = admin.to_crs("EPSG:6933")

    source_hash = f"{sha256_of_file(gadm)}|{sha256_of_file(gpkg)}"
    source_file = f"{gadm}|{gpkg}"
    records: list[dict] = []
    diagnostics: list[dict] = []

    for layer in ["1", "10", "34"]:
        if layer not in layers:
            raise ValueError(f"Layer {layer} missing from {gpkg}")
        regions = gpd.read_file(gpkg, layer=layer).copy()
        regions["geometry"] = _valid_geometries(regions["geometry"])
        regions = regions.to_crs("EPSG:6933")
        name_col = "name"
        gdp_values = []
        pop_values = []
        for _, region in regions.iterrows():
            gdp = 0.0
            pop = 0.0
            geom = region.geometry
            for _, adm in admin.iterrows():
                if geom.intersects(adm.geometry):
                    inter_area = geom.intersection(adm.geometry).area
                    if adm.geometry.area > 0:
                        frac = inter_area / adm.geometry.area
                        gdp += frac * float(adm["gdp"])
                        pop += frac * float(adm["pop"])
            gdp_values.append(gdp)
            pop_values.append(pop)
        gdp_s = pd.Series(gdp_values, index=regions[name_col].astype(str))
        pop_s = pd.Series(pop_values, index=regions[name_col].astype(str))
        gdp_n = gdp_s / gdp_s.sum() if gdp_s.sum() else pd.Series(0.0, index=gdp_s.index)
        pop_n = pop_s / pop_s.sum() if pop_s.sum() else pd.Series(0.0, index=pop_s.index)
        factors = 0.6 * gdp_n + 0.4 * pop_n
        if factors.sum() == 0:
            factors = pd.Series(np.ones(len(regions)) / len(regions), index=regions[name_col].astype(str))
            method = "uniform_fallback"
        else:
            factors = factors / factors.sum()
            method = "pypsa_earth_0.6_gdp_0.4_pop_area_overlay"
        for target_region_id, weight in factors.items():
            records.append(
                {
                    "layer_key": layer,
                    "attachment_type": "demand",
                    "source_id": "RSA Contracted Demand",
                    "target_region_id": target_region_id,
                    "weight": float(weight),
                    "source_file": source_file,
                    "source_hash": source_hash,
                    "notes": method,
                }
            )
        diagnostics.extend(
            {
                "layer_key": layer,
                "target_region_id": idx,
                "pypsa_earth_weight": float(factors.loc[idx]),
                "pypsa_earth_gdp_component": float(gdp_n.loc[idx]) if idx in gdp_n.index else np.nan,
                "pypsa_earth_pop_component": float(pop_n.loc[idx]) if idx in pop_n.index else np.nan,
                "source_file": source_file,
                "source_hash": source_hash,
            }
            for idx in factors.index
        )

    weights = pd.DataFrame(records, columns=ATTACHMENT_COLUMNS)
    diag = pd.DataFrame(diagnostics)
    return weights, diag


def _compare_pypsa_rsa_weights(config: dict, pypsa_earth_diag: pd.DataFrame) -> pd.DataFrame:
    import fiona
    import geopandas as gpd

    audit = pd.read_csv(RSA_LOAD_AUDIT) if RSA_LOAD_AUDIT.exists() else pd.DataFrame()
    audited_layers = set()
    if not audit.empty and "layer" in audit.columns:
        audited_layers = {str(int(float(v))) for v in audit["layer"].dropna() if str(v) != "nan"}

    gpkg = Path(config["pypsa_rsa_root"]) / "data" / "bundle" / "supply_regions" / "rsa_supply_regions.gpkg"
    layers = set(fiona.listlayers(str(gpkg)))
    rows: list[dict] = []
    for layer in ["1", "10", "34"]:
        earth = pypsa_earth_diag.loc[pypsa_earth_diag["layer_key"] == layer]
        if layer not in layers:
            continue
        regions = gpd.read_file(gpkg, layer=layer)
        has_gva = "GVA2016" in regions.columns and pd.to_numeric(regions["GVA2016"], errors="coerce").fillna(0).sum() > 0
        has_pop = "POP2016" in regions.columns and pd.to_numeric(regions["POP2016"], errors="coerce").fillna(0).sum() > 0
        if has_gva:
            gva_weights = pd.to_numeric(regions["GVA2016"], errors="coerce").fillna(0)
            gva_weights = gva_weights / gva_weights.sum()
        else:
            gva_weights = pd.Series(np.nan, index=regions.index)
        if has_pop:
            pop_weights = pd.to_numeric(regions["POP2016"], errors="coerce").fillna(0)
            pop_weights = pop_weights / pop_weights.sum()
        else:
            pop_weights = pd.Series(np.nan, index=regions.index)
        earth_map = earth.set_index("target_region_id")["pypsa_earth_weight"].to_dict()
        for idx, region in regions.iterrows():
            target = str(region["name"])
            earth_weight = float(earth_map.get(target, np.nan))
            gva_weight = float(gva_weights.loc[idx]) if has_gva else np.nan
            pop_weight = float(pop_weights.loc[idx]) if has_pop else np.nan
            rows.append(
                {
                    "layer_key": layer,
                    "target_region_id": target,
                    "pypsa_earth_weight": earth_weight,
                    "gva_2016_weight": gva_weight,
                    "pop_2016_weight": pop_weight,
                    "gva_deviation": earth_weight - gva_weight if has_gva else np.nan,
                    "pop_deviation": earth_weight - pop_weight if has_pop else np.nan,
                    "status": "diagnostic_available" if has_gva or has_pop else "diagnostic_unavailable",
                    "notes": "PyPSA-RSA GVA_2016/POP_2016 diagnostic only; not used for V1 allocation"
                    if (has_gva or has_pop)
                    else f"No regional GVA_2016/POP_2016 columns in audited layer {layer}; audited_layers={sorted(audited_layers)}",
                }
            )
    out = pd.DataFrame(rows)
    out.to_csv(RSA_COMPARISON_OUTPUT, index=False, float_format="%.12f")
    return out


def _check_weight_sums(df: pd.DataFrame, label: str) -> None:
    for key, group in df.groupby(["layer_key", "attachment_type", "source_id"], dropna=False):
        total = float(group["weight"].sum())
        if abs(total - 1.0) > WEIGHT_TOL:
            raise ValueError(f"{label} weights for {key} sum to {total}, expected 1.0")


def _write_attachment_tables(weights: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    clean_hash = sha256_of_file(ESKOM_HOURLY)
    demand_weights = weights.loc[weights["attachment_type"] == "demand"].copy()
    demand_weights.to_csv(LOAD_WEIGHTS_OUTPUT, index=False, float_format="%.12f")

    import_rows = []
    export_rows = []
    other_re_rows = []
    for layer in ["1", "10", "34"]:
        layer_weights = demand_weights.loc[demand_weights["layer_key"] == layer]
        if layer == "1":
            import_targets = {"ZA": 1.0}
        elif layer == "10":
            import_targets = {"Gauteng": 1.0}
        else:
            import_targets = {"Pretoria": 1.0}
        for target, weight in import_targets.items():
            import_rows.append(
                {
                    "layer_key": layer,
                    "attachment_type": "import",
                    "source_id": "International Imports",
                    "target_region_id": target,
                    "weight": weight,
                    "source_file": str(ESKOM_HOURLY),
                    "source_hash": clean_hash,
                    "notes": "conservative hydro_import proxy; module 09 resolves final bus IDs",
                }
            )
        for _, row in layer_weights.iterrows():
            export_rows.append(
                {
                    **row.to_dict(),
                    "attachment_type": "export",
                    "source_id": "International Exports",
                    "source_file": str(ESKOM_HOURLY),
                    "source_hash": clean_hash,
                    "notes": "gross exports proxy uses demand weights because Eskom source has no border split; module 09 may replace",
                }
            )
            other_re_rows.append(
                {
                    **row.to_dict(),
                    "attachment_type": "other_re",
                    "source_id": "Other RE",
                    "source_file": str(ESKOM_HOURLY),
                    "source_hash": clean_hash,
                    "notes": "Other RE proxy uses demand weights because plant locations are not exposed in Eskom hourly source",
                }
            )

    import_export = pd.DataFrame(import_rows + export_rows, columns=ATTACHMENT_COLUMNS)
    other_re = pd.DataFrame(other_re_rows, columns=ATTACHMENT_COLUMNS)
    _check_weight_sums(demand_weights, "demand")
    _check_weight_sums(import_export, "import/export")
    _check_weight_sums(other_re, "other_re")
    import_export.to_csv(IMPORT_EXPORT_ATTACHMENT_OUTPUT, index=False, float_format="%.12f")
    other_re.to_csv(OTHER_RE_ATTACHMENT_OUTPUT, index=False, float_format="%.12f")
    return import_export, other_re


def _write_report(demand_stats: dict, import_export_stats: dict, other_re_stats: dict, comparison: pd.DataFrame) -> None:
    warn = "yes" if other_re_stats["warning"] else "no"
    diagnostic_available = int((comparison["status"] == "diagnostic_available").sum()) if not comparison.empty else 0
    diagnostic_unavailable = int((comparison["status"] == "diagnostic_unavailable").sum()) if not comparison.empty else 0
    text = f"""# ZA Demand Import Export Model Inputs

## Summary

Module 06 converts the cleaned Eskom 2023 hourly data into model-facing demand,
gross import/export, and `other_re` input artifacts for the fixed 2023 South
Africa validation build.

## Demand

- Demand target: `RSA Contracted Demand`.
- Output rows: {EXPECTED_HOURS}.
- Annual demand: {demand_stats['demand_twh']:.9f} TWh.
- Module 02 target: {demand_stats['target_twh']:.9f} TWh.
- GEGIS export: `{GEGIS_OUTPUT}`.

The ZA overlay must use `load_options.weather_year: 2023_custom` and
`load_options.prediction_year: 2030`, which makes upstream
`build_demand_profiles.py:get_load_paths_gegis` resolve the South Africa demand
input through the GEGIS CSV route.

## Import Export Sign Convention

- `International Imports` is a positive supply injection into South Africa.
- `International Exports` is a positive withdrawal from South Africa.
- Net import is reported only as `imports - exports`; model inputs keep gross
  imports and gross exports separate.

Annual gross imports: {import_export_stats['imports_twh']:.9f} TWh.
Annual gross exports: {import_export_stats['exports_twh']:.9f} TWh.
Annual net import: {import_export_stats['net_import_twh']:.9f} TWh.

## Other RE

`Other RE` is an exogenous local carrier input, not negative demand. Module 10
must add it as a non-extendable `Generator` with carrier `other_re`, `p_nom =
{other_re_stats['p_nom_mw']:.6f} MW`, `p_min_pu = 0`, and `p_max_pu` from
`{OTHER_RE_OUTPUT}`.

- Annual Other RE energy: {other_re_stats['other_re_twh']:.9f} TWh.
- Maximum raw `Other RE / p_nom`: {other_re_stats['max_unclipped_ratio']:.6f}.
- Clipped hours: {other_re_stats['clipped_hours']}.
- Daily maximum ratio exceeded 1.05 warning threshold: {warn}.

## Spatial Attachments

Demand weights for candidate layers `1`, `10`, and `34` use PyPSA-Earth-style
allocation: area-overlay GADM GDP/population components with normalized
`0.6 * gdp + 0.4 * pop`. PyPSA-RSA `GVA_2016` and `POP_2016` are diagnostic
only and are not used as V1 allocation weights.

Conservative proxy attachments are used for non-demand series:

- imports: national `ZA`, `Gauteng` for layer `10`, `Pretoria` for layer `34`.
- exports: demand-weight proxy because the Eskom source has no border split.
- Other RE: demand-weight proxy because the Eskom hourly source has no plant
  locations.

PyPSA-RSA diagnostic rows available: {diagnostic_available}; unavailable:
{diagnostic_unavailable}. Module 09 resolves final PyPSA-Earth bus IDs and may
replace proxy attachments with stronger grid evidence.

## Artifacts

- `{DEMAND_OUTPUT}`
- `{GEGIS_OUTPUT}`
- `{IMPORT_EXPORT_OUTPUT}`
- `{OTHER_RE_OUTPUT}`
- `{LOAD_WEIGHTS_OUTPUT}`
- `{RSA_COMPARISON_OUTPUT}`
- `{IMPORT_EXPORT_ATTACHMENT_OUTPUT}`
- `{OTHER_RE_ATTACHMENT_OUTPUT}`
"""
    REPORT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUTPUT.write_text(text, encoding="utf-8")


def _upsert_csv(path: Path, key_column: str, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = pd.read_csv(path, dtype=str)
        if key_column in existing.columns:
            remove_keys = {str(row[key_column]) for row in rows}
            existing = existing.loc[~existing[key_column].isin(remove_keys)]
        else:
            existing = pd.DataFrame(columns=columns)
    else:
        existing = pd.DataFrame(columns=columns)
    out = pd.concat([existing, pd.DataFrame(rows)], ignore_index=True)
    out = out.reindex(columns=columns)
    out.to_csv(path, index=False)


def _record_provenance() -> None:
    now = _now()
    artifacts = [
        ("za-demand-import-export-script", "script", Path("scripts/build_za_demand_import_export_inputs.py"), "Module 06 builder script"),
        ("za-2023-demand-profile", "csv", DEMAND_OUTPUT, "Module 06 demand profile"),
        ("za-2023-gegis-demand-africa", "csv", GEGIS_OUTPUT, "Module 06 GEGIS-compatible demand export"),
        ("za-2023-import-export-timeseries", "csv", IMPORT_EXPORT_OUTPUT, "Module 06 gross import/export timeseries"),
        ("za-2023-other-re-timeseries", "csv", OTHER_RE_OUTPUT, "Module 06 Other RE exogenous timeseries"),
        ("za-2023-load-allocation-weights", "csv", LOAD_WEIGHTS_OUTPUT, "Module 06 load allocation weights"),
        ("za-pypsa-rsa-gva-pop-load-weight-comparison", "csv", RSA_COMPARISON_OUTPUT, "Module 06 diagnostic GVA/POP comparison"),
        ("za-2023-import-export-attachment", "csv", IMPORT_EXPORT_ATTACHMENT_OUTPUT, "Module 06 import/export attachment table"),
        ("za-2023-other-re-attachment", "csv", OTHER_RE_ATTACHMENT_OUTPUT, "Module 06 Other RE attachment table"),
        ("za-demand-import-export-report", "markdown", REPORT_OUTPUT, "Module 06 model-input report"),
    ]
    hash_rows = [
        {
            "source_id": sid,
            "source_type": typ,
            "path_or_url": str(path),
            "hash_algorithm": "sha256",
            "hash": sha256_of_file(path) if path.exists() else "",
            "commit_or_version": "",
            "recorded_at": now,
            "notes": notes,
        }
        for sid, typ, path, notes in artifacts
    ]
    manifest_rows = [
        {
            "artifact_id": sid,
            "artifact_type": typ,
            "path": str(path),
            "status": "present" if path.exists() else "missing",
            "sha256": sha256_of_file(path) if path.exists() else "",
            "source_commit_or_version": "",
            "recorded_at": now,
            "notes": notes,
        }
        for sid, typ, path, notes in artifacts
    ]
    _upsert_csv(
        SOURCE_HASHES,
        "source_id",
        hash_rows,
        ["source_id", "source_type", "path_or_url", "hash_algorithm", "hash", "commit_or_version", "recorded_at", "notes"],
    )
    _upsert_csv(
        INPUT_MANIFEST,
        "artifact_id",
        manifest_rows,
        ["artifact_id", "artifact_type", "path", "status", "sha256", "source_commit_or_version", "recorded_at", "notes"],
    )


def _run(config: dict) -> int:
    DATA_VALIDATION.mkdir(parents=True, exist_ok=True)
    DATA_AUDIT.mkdir(parents=True, exist_ok=True)
    clean = _validate_hourly(pd.read_csv(ESKOM_HOURLY))
    targets = pd.read_csv(ESKOM_TARGETS)
    demand_stats = _write_demand(clean, targets)
    import_export_stats = _write_import_export(clean)
    other_re_stats = _write_other_re(clean, targets)
    weights, earth_diag = _pypsa_earth_style_weights(config)
    comparison = _compare_pypsa_rsa_weights(config, earth_diag)
    _write_attachment_tables(weights)
    _write_report(demand_stats, import_export_stats, other_re_stats, comparison)
    _record_provenance()
    logger.info("Module 06 outputs written; demand %.6f TWh", demand_stats["demand_twh"])
    return 0


def _main_from_snakemake() -> int:
    snakemake = globals().get("snakemake", None)
    if snakemake is None:
        return 2
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    return _run(dict(snakemake.config))


if "snakemake" in globals():
    raise SystemExit(_main_from_snakemake())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--configfile", required=True, type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    raise SystemExit(_run(_load_config(args.configfile)))
