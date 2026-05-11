# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Module 08 — Fleet Reconciliation And Custom Powerplants.

Builds ``data/custom_powerplants.csv`` (frozen 2023 ZA fleet) and the
reconciliation audit / named-plant inventory / Eskom anchor / smoke diff
artifacts consumed by Module 10 (network build) and Module 12 (validation).

This is a Module 04 → 08 transformation. Source workbooks are NOT re-parsed;
the Module 04 audit CSVs in ``data/za_audit/`` are the only allowed sources.
"""
