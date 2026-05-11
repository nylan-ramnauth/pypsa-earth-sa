# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""I/O helpers for ZA Module 09 — inlined to keep the package self-contained.

Mirrors `scripts/za_audits/io.py` rather than importing it because `za_audits`
is not on sys.path from the orchestrator's import chain.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable


def sha256_of_file(path: str | Path) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_parent(path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def write_geojson(gdf, path: str | Path) -> Path:
    p = ensure_parent(path)
    gdf.to_file(p, driver="GeoJSON")
    return p


def join_hashes(paths: Iterable[str | Path]) -> str:
    return "|".join(sha256_of_file(p) for p in paths)
