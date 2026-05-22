# SPDX-FileCopyrightText: PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Produce the Module 13n calibration-adjusted Africa.csv demand file.

Reads:  data/za_validation/eskom_2023_hourly_clean.csv
Writes: data/ssp2-2.6/2030/era5_2023_calibrated/Africa.csv

See doc/active/calibration-plan/13n_calibration_demand_adjustment.md.
Run once: python scripts/build_za_calibration_demand.py
"""

from pathlib import Path

import pandas as pd


ESKOM_HOURLY = Path("data/za_validation/eskom_2023_hourly_clean.csv")
OUTPUT = Path("data/ssp2-2.6/2030/era5_2023_calibrated/Africa.csv")


def main() -> None:
    df = pd.read_csv(ESKOM_HOURLY, index_col=0, parse_dates=True)

    unattributed = (
        df["Dispatchable Generation"]
        - df["Thermal Generation"]
        - df["Nuclear Generation"]
        - df["Eskom Gas Generation"]
        - df["Eskom OCGT Generation"]
        - df["Hydro Water Generation"]
        - df["Pumped Water Generation"]
        - df["Dispatchable IPP OCGT"]
    )

    demand = (
        df["RSA Contracted Demand"]
        - df["International Imports"]
        + df["International Exports"]
        - df["Other RE"]
        - unattributed
    )

    minimum_mw = demand.min()
    assert minimum_mw > 0, f"Negative demand: min={minimum_mw:.1f} MW"

    annual_gwh = demand.sum() / 1e3
    assert abs(annual_gwh - 220901) < 2, f"Annual total off: {annual_gwh:.0f} GWh"

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    out = pd.DataFrame(
        {
            "region_code": "ZA",
            "time": df.index.strftime("%Y-%m-%d %H:%M:%S"),
            "region_name": "South Africa",
            "Electricity demand": demand.values,
        }
    )
    out.to_csv(OUTPUT, index=False, sep=";", float_format="%.9f")
    print(f"Written: {OUTPUT}  ({annual_gwh:,.0f} GWh)")


if __name__ == "__main__":
    main()
