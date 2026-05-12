# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""ZA Calibration Plan Module 10 — Earth-vs-RSA baseline diagnostic.

Audit-only sub-package: compares what PyPSA-Earth retrieves by default
against what PyPSA-RSA uses, across four dimensions — powerplants, lines
per voltage, substations, and per-corridor line ratings.

This package writes diagnostic CSVs and one canonical report. It does not
modify any model input written by modules 01-09 except `za_grid_reconciliation.csv`
(in-place NaN fill) and `za_powerplant_reconciliation.csv` (in-place back-fill
of `capacity_mw_ppm` / `source_ppm`).
"""
