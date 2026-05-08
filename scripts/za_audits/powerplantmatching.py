# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""ZA Module 04 — full powerplantmatching extraction for South Africa.

The default PyPSA-Earth `build_powerplants.py` filters out solar and wind. For
the audit, we keep every fueltype/technology including wind, PV, CSP, hydro,
storage, bioenergy, and waste, with source provenance flags retained.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

PPM_TARGET_COUNTRIES = ["South Africa"]
COLUMNS_TO_RETAIN = [
    "Name",
    "Fueltype",
    "Technology",
    "Set",
    "Country",
    "Capacity",
    "Efficiency",
    "DateIn",
    "DateRetrofit",
    "DateOut",
    "lat",
    "lon",
    "Duration",
    "Volume_Mm3",
    "DamHeight_m",
    "StorageCapacity_MWh",
    "EIC",
    "projectID",
]


def _empty_dataframe(reason: str) -> pd.DataFrame:
    df = pd.DataFrame(columns=COLUMNS_TO_RETAIN + ["source_count", "source_flags", "raw_project_ids"])
    df.attrs["audit_note"] = reason
    return df


def _ppm_call(config_path: Path) -> pd.DataFrame:
    """Match upstream powerplantmatching sources for South Africa.

    The packaged `from_url=True` dataset is Europe-only, so we re-run the
    matching pipeline restricted to South Africa, mirroring the way
    `scripts/build_powerplants.py` calls ppm. This requires upstream source
    archives but does **not** require ENTSOE credentials because we exclude
    `EXTERNAL_DATABASE`. If ppm cannot return any South Africa rows, the caller
    falls back to an empty audit with an explanatory note.
    """
    import powerplantmatching as pm

    config_update = {
        "target_countries": PPM_TARGET_COUNTRIES,
        "matching_sources": ["GEO", "GPD", "GBPT", "GGPT", "GCPT", "GGTPT", "GNPT", "GSPT", "GWPT", "GHPT"],
        "fully_included_sources": ["GEO", "GPD", "GBPT", "GGPT", "GCPT", "GGTPT", "GNPT", "GSPT", "GWPT", "GHPT"],
        "main_query": "",
    }
    df = pm.powerplants(from_url=False, update=True, config_update=config_update)
    df = df[df["Country"] == "South Africa"].copy()
    return df


def build_powerplantmatching_audit(
    ppm_config_path: Path,
    full_out: Path,
    audit_out: Path,
) -> int:
    try:
        df = _ppm_call(Path(ppm_config_path))
    except Exception as exc:  # noqa: BLE001
        logger.exception("ppm extraction failed: %s", exc)
        df = _empty_dataframe(f"ppm.powerplants() failed: {exc}")

    if df.empty:
        full_out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(full_out, index=False)
        df.to_csv(audit_out, index=False)
        return 0

    # Source flag columns: ppm tags each source as a 0/1 column with the source
    # short-code as the column name (GEO, GPD, GBPT, ...). Detect them.
    source_short_codes = [
        "GEO", "GPD", "GBPT", "GGPT", "GCPT", "GGTPT", "GNPT", "GSPT", "GWPT", "GHPT",
        "CARMA", "ENTSOE", "OPSD", "WEPP", "ESE", "GEM_GGPT", "EXTERNAL_DATABASE",
    ]
    detected_source_cols = [c for c in df.columns if c in source_short_codes]
    if "projectID" in df.columns:
        df["raw_project_ids"] = df["projectID"].astype(str)
    else:
        df["raw_project_ids"] = ""

    if detected_source_cols:
        df["source_count"] = df[detected_source_cols].fillna(0).astype(int).sum(axis=1)
        df["source_flags"] = df.apply(
            lambda r: "|".join(c for c in detected_source_cols if int(r.get(c, 0) or 0) > 0),
            axis=1,
        )
    else:
        df["source_count"] = 1
        df["source_flags"] = "ppm"

    # Full export keeps every column ppm produced.
    full_out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(full_out, index=False)

    # Audit export keeps the canonical retained set.
    keep = [c for c in COLUMNS_TO_RETAIN if c in df.columns] + [
        "source_count",
        "source_flags",
        "raw_project_ids",
    ]
    audit_df = df[keep].copy()
    audit_df.to_csv(audit_out, index=False)

    return int(len(df))
