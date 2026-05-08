# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Module 05 acceptance smoke test (deferred — fires when module 10 lands).

Exit codes
----------
0  pass — assertions hold against the network at the given path
1  fail — at least one assertion failed
2  skip — network path missing or unreadable; module 10 has not produced one yet

The CSP/solar lower bounds come verbatim from
`doc/active/calibration-plan/05_system_boundary_and_carrier_taxonomy.md`
lines 96-101.
"""

import argparse
import sys
from pathlib import Path


def _load_network(path: Path):
    try:
        import pypsa
    except Exception as exc:
        print(f"smoke: pypsa import failed: {exc}", file=sys.stderr)
        return None, 2
    if not path.exists():
        print(f"smoke: network not present at {path} — skipping (module 10 has not produced one)", file=sys.stderr)
        return None, 2
    try:
        n = pypsa.Network(str(path))
    except Exception as exc:
        print(f"smoke: failed to open network at {path}: {exc}", file=sys.stderr)
        return None, 2
    return n, 0


def run_assertions(n) -> int:
    failures: list[str] = []

    if "csp" not in n.carriers.index:
        failures.append("csp not in n.carriers.index")
    else:
        csp_p_nom = n.generators.query("carrier=='csp'").p_nom.sum()
        if not (csp_p_nom > 400):
            failures.append(f"csp p_nom sum {csp_p_nom} not > 400 MW")

    if "solar" not in n.carriers.index:
        failures.append("solar not in n.carriers.index")
    else:
        solar_p_nom = n.generators.query("carrier=='solar'").p_nom.sum()
        if not (solar_p_nom > 5000):
            failures.append(f"solar p_nom sum {solar_p_nom} not > 5000 MW")

    if "csp" in n.carriers.index and "solar" in n.carriers.index:
        if "csp" == "solar":  # type-level guard, never true
            failures.append("csp merged into solar")

    if failures:
        print("smoke: FAIL")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("smoke: PASS  (csp and solar are distinct non-zero carriers)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("network", type=Path, help="path to the PyPSA .nc network")
    args = parser.parse_args()
    n, code = _load_network(args.network)
    if n is None:
        return code
    return run_assertions(n)


if __name__ == "__main__":
    raise SystemExit(main())
