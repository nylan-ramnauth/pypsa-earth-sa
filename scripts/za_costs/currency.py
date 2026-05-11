# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""EUR <-> ZAR conversion helpers used by Module 07 audit emission and by
Module 10's `apply_za_local_carriers` hook.

Convention: ``eur_zar_rate = ZAR per 1 EUR``. So ``eur_to_zar`` multiplies
and ``zar_to_eur`` divides.
"""
from __future__ import annotations


def eur_to_zar(value_eur: float, eur_zar_rate: float) -> float:
    if eur_zar_rate is None or eur_zar_rate <= 0:
        raise ValueError(f"eur_zar_rate must be > 0, got {eur_zar_rate!r}")
    return float(value_eur) * float(eur_zar_rate)


def zar_to_eur(
    value_zar: float,
    eur_zar_rate: float,
    base_year_rate: float | None = None,
) -> float:
    """Convert ZAR to EUR. If ``base_year_rate`` is supplied it overrides
    ``eur_zar_rate`` — use that when the source value carries a base-year
    timestamp distinct from the frozen 2023 rate.
    """
    rate = float(base_year_rate) if base_year_rate is not None else float(eur_zar_rate)
    if rate <= 0:
        raise ValueError(f"effective rate must be > 0, got {rate!r}")
    return float(value_zar) / rate


if __name__ == "__main__":  # roundtrip sanity check
    rate_2023 = 20.3477
    sample = 12345.6789
    err = abs(zar_to_eur(eur_to_zar(sample, rate_2023), rate_2023) - sample)
    if err > 1e-9:
        raise SystemExit(f"roundtrip failed: |err|={err}")
    print(f"currency roundtrip OK |err|={err:.3e}")
