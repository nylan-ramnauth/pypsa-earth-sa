# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build clean Eskom 2023 validation data for the ZA calibration workflow."""

import csv
import hashlib
from pathlib import Path

import pandas as pd

DATE_COLUMN = "Date Time Hour Beginning"
DATE_FORMAT = "%Y-%m-%d %I:%M:%S %p"
START = pd.Timestamp("2023-01-01 00:00")
END = pd.Timestamp("2023-12-31 23:00")
EXPECTED_HOURS = 8760
ANNUAL_TWH_TOL = 1e-6
HOURLY_MW_TOL = 1e-3
FLOAT_EPS = 1e-9

RAW_INPUT = Path("data/za_audit/raw/eskom_data_2023_full.csv")
HOURLY_OUTPUT = Path("data/za_validation/eskom_2023_hourly_clean.csv")
TARGET_OUTPUT = Path("data/za_validation/eskom_2023_targets_by_carrier.csv")
REPORT_OUTPUT = Path("data/za_audit/eskom_2023_parser_report.csv")

REQUIRED_NUMERIC_COLUMNS = [
    "RSA Contracted Demand",
    "Residual Demand",
    "Dispatchable Generation",
    "Thermal Generation",
    "Nuclear Generation",
    "Eskom Gas Generation",
    "Eskom OCGT Generation",
    "Hydro Water Generation",
    "Pumped Water Generation",
    "ILS Usage",
    "Manual Load_Reduction(MLR)",
    "IOS Excl ILS and MLR",
    "Dispatchable IPP OCGT",
    "Pumped Water SCO Pumping",
    "Wind",
    "PV",
    "CSP",
    "Other RE",
    "Total RE",
    "International Exports",
    "International Imports",
    "Wind Installed Capacity",
    "PV Installed Capacity",
    "CSP Installed Capacity",
    "Other RE Installed Capacity",
    "Total RE Installed Capacity",
    "Installed Eskom Capacity",
    "Total UCLF+OCLF",
]

ENERGY_TARGETS = [
    ("RSA Contracted Demand", "RSA Contracted Demand", 225.875, "Eskom 2023 raw data; external primary cross-check pending"),
    ("Residual Demand", "Residual Demand", 207.190, "Eskom 2023 raw data"),
    ("Dispatchable Generation", "Dispatchable Generation", 190.434, "Eskom 2023 raw data"),
    ("Thermal Generation", "Thermal Generation", 165.627, "Eskom 2023 raw data"),
    ("Nuclear Generation", "Nuclear Generation", 8.127, "Eskom 2023 raw data; CSIR Utility Statistics Report 2024 cross-check pending"),
    ("Eskom Gas Generation", "Eskom Gas Generation", None, "Eskom 2023 raw data"),
    ("Eskom OCGT Generation", "Eskom OCGT Generation", 3.566, "Eskom 2023 raw data"),
    ("Dispatchable IPP OCGT", "Dispatchable IPP OCGT", 1.677, "Eskom 2023 raw data"),
    ("Hydro Water Generation", "Hydro Water Generation", 1.992, "Eskom 2023 raw data"),
    ("Pumped Water Generation", "Pumped Water Generation", 4.294, "Eskom 2023 raw data"),
    ("Pumped Water SCO Pumping", "Pumped Water SCO Pumping", -5.658, "Eskom 2023 raw data; negative value is energy consumed for pumping"),
    ("Wind", "Wind", 11.613, "Eskom 2023 raw data; CSIR Utility Statistics Report 2024 cross-check pending"),
    ("PV", "PV", 5.015, "Eskom 2023 raw data; CSIR Utility Statistics Report 2024 cross-check pending"),
    ("CSP", "CSP", 1.375, "Eskom 2023 raw data; CSIR Utility Statistics Report 2024 cross-check pending"),
    ("Other RE", "Other RE", 0.238, "Eskom 2023 raw data"),
    ("Total RE", "Total RE", 18.241, "Computed from Eskom raw data; equals Wind + PV + CSP + Other RE"),
    ("Manual Load Reduction", "Manual Load_Reduction(MLR)", 16.562, "Eskom 2023 raw data"),
    ("ILS Usage", "ILS Usage", None, "Eskom 2023 raw data"),
    ("IOS Excl ILS and MLR", "IOS Excl ILS and MLR", None, "Eskom 2023 raw data"),
    ("International Imports", "International Imports", None, "Eskom 2023 raw data"),
    ("International Exports", "International Exports", None, "Eskom 2023 raw data"),
]

CAPACITY_TARGETS = [
    ("Wind installed capacity", "Wind Installed Capacity", 3442.57, "MW", "Eskom 2023 raw data; CSIR Utility Statistics Report 2024 cross-check pending"),
    ("PV installed capacity start", "PV Installed Capacity", 2212.09, "MW", "Eskom 2023 raw data; start-of-year value"),
    ("PV installed capacity end", "PV Installed Capacity", 2287.09, "MW", "Eskom 2023 raw data; end-of-year value used for Module 12 capacity validation"),
    ("CSP installed capacity", "CSP Installed Capacity", 500.00, "MW", "Eskom 2023 raw data; CSIR Utility Statistics Report 2024 cross-check pending"),
    ("Other RE installed capacity", "Other RE Installed Capacity", 50.58, "MW", "Eskom 2023 raw data; external primary cross-check pending"),
    ("Total RE installed capacity start", "Total RE Installed Capacity", 6205.24, "MW", "Eskom 2023 raw data; start-of-year value"),
    ("Total RE installed capacity end", "Total RE Installed Capacity", 6280.24, "MW", "Eskom 2023 raw data; end-of-year value used for Module 12 capacity validation"),
    ("Installed Eskom Capacity", "Installed Eskom Capacity", 46686.00, "MW", "Eskom 2023 raw data; Eskom Annual Report 2023 cross-check pending"),
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repair_rows(path: Path) -> tuple[list[str], list[list[str]], dict[str, int]]:
    with path.open(newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        rows = []
        stats = {
            "raw_rows": 0,
            "exact_rows": 0,
            "repaired_rows": 0,
            "bad_field_count_rows": 0,
        }

        for line_no, row in enumerate(reader, start=2):
            stats["raw_rows"] += 1
            if len(row) == len(header) + 1:
                row = row[:37] + [f"{row[37]}.{row[38]}"] + row[39:]
                stats["repaired_rows"] += 1
            elif len(row) == len(header):
                stats["exact_rows"] += 1
            else:
                stats["bad_field_count_rows"] += 1
                raise ValueError(
                    f"Unexpected field count on line {line_no}: {len(row)} fields; expected {len(header)} or {len(header) + 1}."
                )
            rows.append(row)

    return header, rows, stats


def _target_row(
    target: str,
    value: float,
    unit: str,
    source: str,
    raw_column: str,
    method: str,
    tolerance: str,
    status: str,
    notes: str,
) -> dict[str, object]:
    return {
        "target": target,
        "value": value,
        "unit": unit,
        "source": source,
        "raw_column": raw_column,
        "method": method,
        "tolerance": tolerance,
        "status": status,
        "notes": notes,
    }


def _report_row(
    check_id: str,
    category: str,
    status: str,
    value: object,
    unit: str = "",
    tolerance: str = "",
    notes: str = "",
) -> dict[str, object]:
    return {
        "check_id": check_id,
        "category": category,
        "status": status,
        "value": value,
        "unit": unit,
        "tolerance": tolerance,
        "notes": notes,
    }


def build_eskom_validation_data(raw_input: Path, hourly_output: Path, target_output: Path, report_output: Path) -> None:
    raw_input = Path(raw_input)
    hourly_output = Path(hourly_output)
    target_output = Path(target_output)
    report_output = Path(report_output)

    if not raw_input.exists():
        raise FileNotFoundError(f"Missing raw Eskom CSV: {raw_input}")

    raw_hash = _sha256(raw_input)
    header, rows, repair_stats = _repair_rows(raw_input)
    missing_required = [column for column in REQUIRED_NUMERIC_COLUMNS if column not in header]
    if DATE_COLUMN not in header:
        missing_required.append(DATE_COLUMN)
    if missing_required:
        raise ValueError(f"Missing required Eskom columns: {missing_required}")

    df = pd.DataFrame(rows, columns=header)
    df[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN], format=DATE_FORMAT, errors="raise")
    for column in header:
        if column != DATE_COLUMN:
            df[column] = pd.to_numeric(df[column], errors="raise")

    pre_2023_rows = int((df[DATE_COLUMN] < START).sum())
    post_2023_rows = int((df[DATE_COLUMN] > END).sum())
    clean = df.loc[(df[DATE_COLUMN] >= START) & (df[DATE_COLUMN] <= END)].copy()
    clean = clean.sort_values(DATE_COLUMN).reset_index(drop=True)

    if len(clean) != EXPECTED_HOURS:
        raise ValueError(f"Expected {EXPECTED_HOURS} rows for 2023, found {len(clean)}.")
    if clean[DATE_COLUMN].duplicated().any():
        duplicated = clean.loc[clean[DATE_COLUMN].duplicated(), DATE_COLUMN].tolist()
        raise ValueError(f"Duplicate hourly timestamps in 2023 data: {duplicated[:5]}")
    expected_index = pd.date_range(START, END, freq="h")
    missing_hours = expected_index.difference(clean[DATE_COLUMN])
    if len(missing_hours):
        raise ValueError(f"Missing hourly timestamps in 2023 data: {missing_hours[:5].tolist()}")

    total_re_diff = clean["Total RE"] - (clean["Wind"] + clean["PV"] + clean["CSP"] + clean["Other RE"])
    residual_rhs = (
        clean["Dispatchable Generation"]
        + clean["Manual Load_Reduction(MLR)"]
        + clean["ILS Usage"]
        + clean["IOS Excl ILS and MLR"]
    )
    residual_diff = clean["Residual Demand"] - residual_rhs
    rsa_diff_twh = (
        clean["RSA Contracted Demand"].sum() - clean["Residual Demand"].sum() - clean["Total RE"].sum()
    ) / 1e6

    total_re_max = float(total_re_diff.abs().max())
    residual_max = float(residual_diff.abs().max())
    residual_annual = float(residual_diff.sum() / 1e6)
    if total_re_max > HOURLY_MW_TOL + FLOAT_EPS:
        raise ValueError(f"Total RE hourly identity failed: max abs diff {total_re_max} MW.")
    if residual_max > HOURLY_MW_TOL + FLOAT_EPS or abs(residual_annual) > ANNUAL_TWH_TOL + FLOAT_EPS:
        raise ValueError(
            "Residual demand identity failed: "
            f"max hourly {residual_max} MW; annual {residual_annual} TWh."
        )

    hourly_output.parent.mkdir(parents=True, exist_ok=True)
    clean.to_csv(hourly_output, index=False, float_format="%.9f")

    targets = []
    for target, column, locked_anchor, source in ENERGY_TARGETS:
        value = float(clean[column].sum() / 1e6)
        status = "pass"
        notes = "raw 2023 hourly MW average summed and converted to TWh"
        if target == "Eskom Gas Generation" and abs(value) > ANNUAL_TWH_TOL:
            status = "warn"
            notes += "; actual raw 2023 total is nonzero despite preliminary plan note that zero was expected"
        if locked_anchor is not None:
            rounded_delta = value - locked_anchor
            if abs(rounded_delta) > 0.001:
                status = "warn"
                notes += f"; differs from preliminary rounded anchor by {rounded_delta:.6f} TWh"
        targets.append(
            _target_row(
                target=target,
                value=round(value, 9),
                unit="TWh",
                source=source,
                raw_column=column,
                method="sum(hourly MW average) / 1e6",
                tolerance=str(ANNUAL_TWH_TOL),
                status=status,
                notes=notes,
            )
        )

    mlr_ils_ios = (
        clean["Manual Load_Reduction(MLR)"].sum()
        + clean["ILS Usage"].sum()
        + clean["IOS Excl ILS and MLR"].sum()
    ) / 1e6
    targets.append(
        _target_row(
            target="MLR + ILS + IOS",
            value=round(float(mlr_ils_ios), 9),
            unit="TWh",
            source="Computed from Eskom 2023 raw data",
            raw_column="Manual Load_Reduction(MLR) + ILS Usage + IOS Excl ILS and MLR",
            method="sum(component hourly MW averages) / 1e6",
            tolerance=str(ANNUAL_TWH_TOL),
            status="pass",
            notes="observed reduced/unserved demand proxy for validation reporting",
        )
    )

    first = clean.iloc[0]
    last = clean.iloc[-1]
    for target, column, locked_anchor, unit, source in CAPACITY_TARGETS:
        row = first if "start" in target else last
        value = float(row[column])
        status = "pass" if abs(value - locked_anchor) <= 1e-6 else "warn"
        targets.append(
            _target_row(
                target=target,
                value=round(value, 9),
                unit=unit,
                source=source,
                raw_column=column,
                method="first 2023 hour" if "start" in target else "last 2023 hour",
                tolerance="1e-6 MW",
                status=status,
                notes="capacity anchor for later validation modules",
            )
        )

    target_output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(targets).to_csv(target_output, index=False)

    report_rows = [
        _report_row("raw-input-path", "provenance", "pass", str(raw_input), notes="canonical staged Eskom raw CSV"),
        _report_row("raw-input-sha256", "provenance", "pass", raw_hash, notes="hash of staged raw CSV"),
        _report_row("raw-column-count", "schema", "pass", len(header), notes="header column count"),
        _report_row("raw-column-headers", "schema", "pass", " | ".join(header), notes="printed for accounting identity inspection"),
        _report_row("raw-row-count", "parser", "pass", repair_stats["raw_rows"], "rows"),
        _report_row("exact-row-count", "parser", "pass", repair_stats["exact_rows"], "rows"),
        _report_row("repaired-row-count", "parser", "pass", repair_stats["repaired_rows"], "rows", notes="rows repaired for split Total UCLF+OCLF comma decimal"),
        _report_row("bad-field-count-rows", "parser", "pass", repair_stats["bad_field_count_rows"], "rows"),
        _report_row("pre-2023-rows-dropped", "filter", "pass", pre_2023_rows, "rows"),
        _report_row("post-2023-rows-dropped", "filter", "pass", post_2023_rows, "rows"),
        _report_row("clean-hourly-row-count", "filter", "pass", len(clean), "rows", notes="exactly 8760 hourly observations"),
        _report_row("clean-start", "filter", "pass", clean[DATE_COLUMN].min()),
        _report_row("clean-end", "filter", "pass", clean[DATE_COLUMN].max()),
        _report_row("required-numeric-columns", "schema", "pass", len(REQUIRED_NUMERIC_COLUMNS), "columns", notes=", ".join(REQUIRED_NUMERIC_COLUMNS)),
        _report_row("total-re-hourly-identity", "accounting", "pass", total_re_max, "MW", str(HOURLY_MW_TOL), "Total RE = Wind + PV + CSP + Other RE"),
        _report_row("residual-demand-hourly-identity", "accounting", "pass", residual_max, "MW", str(HOURLY_MW_TOL), "Residual Demand = Dispatchable Generation + MLR + ILS + IOS"),
        _report_row("residual-demand-annual-identity", "accounting", "pass", residual_annual, "TWh", str(ANNUAL_TWH_TOL), "annual residual-demand identity difference"),
        _report_row("rsa-contracted-demand-identity", "accounting", "warn", round(float(rsa_diff_twh), 12), "TWh", str(ANNUAL_TWH_TOL), "RSA Contracted Demand - Residual Demand - Total RE; retained as source discrepancy"),
        _report_row("eskom-gas-generation-total", "target", "warn", round(float(clean["Eskom Gas Generation"].sum() / 1e6), 9), "TWh", str(ANNUAL_TWH_TOL), "raw 2023 total is nonzero; retained as source value and not treated as parser error"),
    ]
    report_output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(report_rows).to_csv(report_output, index=False)


def _paths_from_snakemake():
    if "snakemake" not in globals():
        return RAW_INPUT, HOURLY_OUTPUT, TARGET_OUTPUT, REPORT_OUTPUT
    raw_input = Path(snakemake.input.raw)
    hourly_output = Path(snakemake.output.hourly)
    target_output = Path(snakemake.output.targets)
    report_output = Path(snakemake.output.report)
    return raw_input, hourly_output, target_output, report_output


if __name__ == "__main__":
    build_eskom_validation_data(*_paths_from_snakemake())
