# Opus Implementation Brief: Module 09b + Module 11

## Context

Modules 01–10 of the ZA 2023 baseline calibration are complete.
Module 10 (diagnostic) revealed 10 RSA transmission corridors with no OSM
representation, carrying 12 GW of RSA capacity that would be absent from the
model. These must be added as custom lines before module 11 can be built.

Working directory: `6-codebases/repos/pypsa-earth/`
Active config: `configs/za/za_2023_fixed_validation.yaml`
Implementation plan: `doc/active/calibration-plan/`

Read `doc/active/calibration-plan/index.md` for the full module list.
Read `doc/active/calibration-plan/11_fixed_capacity_network_build.md` for
module 11 spec.

---

## Part 1 — Module 09b: Add Custom Lines for 10 Unmatched Corridors

### Background

The St Clair N-1 limits from module 09 cover 55/65 RSA corridors.
The remaining 10 corridors have `no_osm_lines_found` in
`data/za_audit/za_osm_vs_stclair_ratings_comparison.csv`.
These corridors must be injected as custom lines so the model has the
correct transmission topology.

### The 10 Corridors to Add

| bus0 | bus1 | voltage_kv | st_clair_n1_mw | n_circuits |
|---|---|---|---|---|
| Bloemfontein | Highveld South | 400 | 492 | 1 |
| Carletonville | Pretoria | 275 | 465 | 1 |
| Highveld South | West Rand | 400 | 1120 | 1 |
| Johannesburg | Middelburg | 400 | 1018 | 1 |
| Johannesburg | Polokwane | 400 | 557 | 2 |
| Johannesburg | Vaal | 275 | 633 | 1 |
| Johannesburg | Warmbad | 275 | 461 | 1 |
| **Johannesburg** | **Witbank** | **400** | **6170** | **6** |
| Nigel | Welkom | 275 | 277 | 1 |
| Nigel | Witbank | 275 | 859 | 2 |

Johannesburg–Witbank is by far the largest gap (6,170 MW, 6 circuits).

### What to Build

1. Write a script `scripts/build_za_custom_lines.py` that:
   - Reads `data/za_audit/za_osm_vs_stclair_ratings_comparison.csv`
   - Filters rows where `notes == "no_osm_lines_found"`
   - Looks up bus coordinates from `networks/za_2023_fixed_validation/elec_s_34.nc`
     (`n.buses[['x','y']]`; bus names are Eskom supply-area names)
   - Constructs a custom lines CSV with columns:
     `name, bus0, bus1, x, r, s_nom, s_nom_extendable, length, num_parallel, carrier`
   - For each corridor: derive `length` from Haversine of bus centroids;
     use standard 400 kV or 275 kV line parameters for `x` and `r`
     (per-km values from `resources/za_2023_fixed_validation/costs_2030_elec.csv`
     or technology-data defaults); set `s_nom = st_clair_n1_mw`;
     `s_nom_extendable = False`
   - Writes to `data/za_audit/za_custom_missing_lines.csv`

2. Add a Snakemake rule `build_za_custom_lines` that runs this script.

3. Wire the output into `add_electricity` / `prepare_network` so the custom
   lines are merged into the network before `elec_s_34.nc` is built.
   PyPSA-Earth supports `custom_lines` in the config — if that path exists,
   use it; otherwise inject via the local hook (see Part 2).

4. Write `data/za_audit/za_custom_lines_audit.csv` confirming each corridor
   was added with the correct `s_nom`.

5. Acceptance gate: re-run `build_za_earth_rsa_diagnostic` and confirm the
   10 corridors no longer appear as `no_osm_lines_found`.

---

## Part 2 — Module 11: Fixed Capacity Network Build

Read `doc/active/calibration-plan/11_fixed_capacity_network_build.md` in full
before implementing.

### Decisions already made (do not re-open)

| Question | Decision |
|---|---|
| 10 unmatched corridors | Added in Part 1 above |
| `apply_za_local_carriers` hook | Write it as part of this module if not already implemented under another name. Check `scripts/` first. |
| Smoke builds | Opus runs Stage 1 (7-day) and Stage 2 (1-month). User runs Stage 3 (full 8760). |
| Uncalibrated baseline | Deferred to Module 12. Do not build it here. |

### Local Hook: `apply_za_local_carriers`

Check whether `scripts/apply_za_local_carriers.py` or an equivalent already
exists. If not, write it. The rule must:

- Run after `add_electricity`, before any solve
- Read `data/za_audit/za_local_carrier_cost_rows.csv` and attach local ZA
  carriers (sasol_coal, sasol_gas, biomass, etc.) without mutating upstream
  Carrier rows
- Read `data/za_audit/za_2023_other_re_attachment.csv` and attach `other_re`
  as a non-extendable Generator with `p_nom = 50.58 MW` and the Eskom
  8760 profile as `p_max_pu` (clipped, curtailment allowed → `p_min_pu = 0`)

### Smoke Build Protocol

**Stage 1 (run):** `2023-07-01` to `2023-07-07`, Gurobi `Threads=2`.
Gate: solves without error; load-shedding ≤ 5% of demand; no infeasibility.

**Stage 2 (run):** July 2023 full month, Gurobi `Threads=2`.
Gate: monthly generation by carrier within 30% of Eskom anchor; no infeasibility.

**Stage 3 (do not run):** Leave configured and documented; user runs separately.

### Acceptance Gates (from module 11 spec)

- Fixed-capacity `elec.nc` builds reproducibly
- `data/za_audit/za_fixed_network_audit.csv` written with all required columns
- All carrier/capacity checks pass or blockers explicitly documented
- Stage 1 and Stage 2 smoke builds pass
