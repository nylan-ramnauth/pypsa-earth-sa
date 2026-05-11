# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Frozen 2023 EUR/ZAR exchange-rate fetch + base-year rate lookup.

Source: ECB historical EUR FX reference rates, mirrored by the
`alexprengere/currencyconverter` GitHub repository as `eurofxref-hist.zip`.

The plan §"Frozen exchange rate" pins the URL to the spot file
`eurofxref.csv`, but that file only carries the most recent ECB trading day.
The historical series required by Module 07 lives in
`eurofxref-hist.zip` in the same directory. The pinned URL constant below
points to the historical archive so the 2023-12-29 row is reachable.
"""
from __future__ import annotations

import hashlib
import io
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

EUROFXREF_HIST_URL = (
    "https://raw.githubusercontent.com/alexprengere/currencyconverter/"
    "master/currency_converter/eurofxref-hist.zip"
)

PREFERRED_DATES_2023 = ["2023-12-29", "2023-12-28", "2023-12-31"]


@dataclass(frozen=True)
class FxRow:
    date: str
    eur_zar_rate: float
    source_url: str
    archive_sha256: str
    archive_member: str
    note: str


def _fetch_archive(url: str) -> tuple[bytes, str]:
    with urllib.request.urlopen(url, timeout=30) as resp:
        raw = resp.read()
    digest = hashlib.sha256(raw).hexdigest()
    return raw, digest


def _load_history(raw_zip: bytes) -> tuple[pd.DataFrame, str]:
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as zf:
        member = next(n for n in zf.namelist() if n.endswith(".csv"))
        with zf.open(member) as fh:
            df = pd.read_csv(fh, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    df = df.dropna(axis=1, how="all")
    if "ZAR" not in df.columns:
        raise RuntimeError(
            f"ZAR column missing from eurofxref archive (member={member})"
        )
    df["Date"] = df["Date"].astype(str).str.strip()
    return df, member


def fetch_2023_eur_zar(url: str = EUROFXREF_HIST_URL) -> FxRow:
    """Fetch the frozen 2023 EUR/ZAR rate.

    Returns the earliest preferred 2023 date that has a non-N/A ZAR value.
    Raises if none of the preferred dates resolve.
    """
    raw, archive_sha = _fetch_archive(url)
    df, member = _load_history(raw)
    for d in PREFERRED_DATES_2023:
        sub = df.loc[df["Date"] == d]
        if sub.empty:
            continue
        val = sub.iloc[0]["ZAR"]
        if val in (None, "", "N/A"):
            continue
        rate = float(val)
        if rate <= 0:
            continue
        return FxRow(
            date=d,
            eur_zar_rate=rate,
            source_url=url,
            archive_sha256=archive_sha,
            archive_member=member,
            note=(
                "ECB EUR/ZAR reference rate, sourced from "
                "alexprengere/currencyconverter eurofxref-hist.zip "
                "(historical archive, not the spot eurofxref.csv "
                "referenced in plan)."
            ),
        )
    raise RuntimeError(
        f"None of the preferred 2023 dates resolved a ZAR rate: "
        f"{PREFERRED_DATES_2023}"
    )


def base_year_eur_zar(year: int, archive_zip: Optional[bytes] = None) -> float:
    """Return the year-average ECB EUR/ZAR rate for ``year``.

    Used to convert PyPSA-RSA ZAR values to EUR at the source's own base
    year (not the frozen 2023 rate). Fetches the archive on demand if not
    supplied.
    """
    if archive_zip is None:
        archive_zip, _ = _fetch_archive(EUROFXREF_HIST_URL)
    df, _ = _load_history(archive_zip)
    df["Date"] = df["Date"].astype(str)
    sub = df.loc[df["Date"].str.startswith(f"{year}-")].copy()
    if sub.empty:
        raise RuntimeError(f"No EUR/ZAR rows for year {year}")
    sub["zar_num"] = pd.to_numeric(sub["ZAR"], errors="coerce")
    series = sub["zar_num"].dropna()
    if series.empty:
        raise RuntimeError(f"All ZAR rows N/A for year {year}")
    return float(series.mean())


def write_fxrate_csv(row: FxRow, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "date": row.date,
                "eur_zar_rate": row.eur_zar_rate,
                "source": row.source_url,
                "note": row.note,
                "archive_sha256": row.archive_sha256,
                "archive_member": row.archive_member,
            }
        ]
    ).to_csv(out_path, index=False, float_format="%.6f")
