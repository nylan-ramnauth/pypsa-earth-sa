# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Spatial-level lock CSV."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from .io import sha256_of_file


def write_lock_csv(
    path: Path,
    level: int,
    source_decision: str,
    layer_path: Path,
    layer_features: int,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "level": level,
        "source_decision": source_decision,
        "layer_path": str(layer_path),
        "layer_features": int(layer_features),
        "hash": sha256_of_file(layer_path),
        "decision_date": datetime.now().strftime("%Y-%m-%d"),
    }
    pd.DataFrame([row]).to_csv(path, index=False)
    return path
