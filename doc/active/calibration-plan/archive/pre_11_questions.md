# Pre-Module 11 Questions

Answer inline. Opus will read this before implementing.

---

## Q1 — 10 unmatched corridors (12 GW missing)

Module 10 found 10 RSA transmission corridors with no OSM line.
These carry 12 GW of RSA capacity and will be **completely absent** from
the module 11 network.

Options:
- **A** — Add custom lines for the 10 corridors now (amends module 09, blocks module 11 until done)
- **B** — Accept the gap, document it, proceed to module 11 as-is

**Answer:**  A

---

## Q2 — Local hook `apply_za_local_carriers`

The module 11 spec requires a Snakemake rule `apply_za_local_carriers` that
attaches ZA-specific carriers and `other_re` dispatch after `add_electricity`.
The rule is referenced in the config but the script does not exist yet.

Should Opus write this script as part of module 11, or has it been implemented
elsewhere under a different name?

**Answer:** Opus can write this script as part of module 11 if it has not been implemented under a different name

---

## Q3 — Smoke builds: run or just wire up?

Module 11 requires three staged solves (7-day, 1-month, full 8760) using
Gurobi before the module is considered complete.

- **A** — Opus writes the pipeline code and you run the solves yourself
- **B** — Opus writes the code and runs stage 1 (7-day) to verify; you run stages 2–3
- **C** — Opus writes and runs all three stages end-to-end

**Answer:** D: Run Stages 1 and 2 and I will run stage 3 myself.

---

## Q4 — Uncalibrated baseline

Module 11 says to also build a stock `za_2023_uncalibrated_baseline` run
(pure PyPSA-Earth defaults, no ZA overrides) for the before/after comparison
in module 12.

Should Opus build this baseline as part of module 11, or defer it to module 12?

**Answer:** Defer to Module 12
