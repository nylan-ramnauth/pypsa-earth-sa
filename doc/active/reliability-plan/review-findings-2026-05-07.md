# Reliability Plan — Pre-Implementation Review Findings
**Date:** 2026-05-07 | **Reviewer:** Claude Opus 4.7 (via Claude Code)
**Scope:** All 8 modules (00–07) audited against pypsa-earth repo, Reliability-Assessment repo, full wiki, DEC-002, and pre-implementation decisions questionnaire.

---

## Summary

| Count | Status |
|---|---|
| 3 | OK |
| 3 | NEEDS EDIT |
| 2 | BLOCKER |

**Contradictions with DEC-002 that must be resolved before implementation:**
1. **Module 06 BLOCKER** — weather-year set `{2013, 2018, 2019, 2020}` contradicts questionnaire Q3 answer `2019–2024`.
2. **Module 07 BLOCKER** — still DRAFT; all 8 sections unfilled.
3. **No outright contradiction with DEC-002 deterministic LP method** — modules 01, 02, 05, 06 all reflect the deterministic single-shot LP with slack, and module 06 explicitly excludes Lagrange from V1 scope. Only module 00 lacks an explicit DEC-002 anchor.

**Verified against repo:**
- `scripts/solve_network.py` exists — module 02's patch target is real.
- `Snakefile` line 66: `load_data_paths = get_load_paths_gegis("data", config)` is parse-time — confirms module 03's per-horizon-helper warning is necessary.
- `add_existing_baseyear.py` and `add_brownfield.py` exist — module 03/04 rule names map to real scripts.
- Reliability-Assessment Stage 5 column is `n_days_obs` (line 249) — rename to `n_observations` confirmed needed.

---

## Module 00 — Overview
**Status:** NEEDS EDIT
**Issues found:**
- No explicit reference to DEC-002. Module 00 does not contradict DEC-002 (correctly scopes V1 to "all-hours annual bus-level ENS constraint" with "slack"), but a reader has no anchor to the binding implementation method decision.
- Scenario 4 described as "EENS weather robustness" without naming the weather-year set. Module 06 specifies `{2013, 2018, 2019, 2020}` while questionnaire Q3 answer is `2019–2024`. Module 00 itself doesn't conflict, but there's no pointer downstream.
- "Required Configuration Surface" does not include `solving.solver.options.gurobi.Threads` or solver reproducibility keys.

**Recommended edits:**
- Add near the top of "Locked V1 Scope": "V1 reliability constraint method is the deterministic single-shot LP with ENS cap + slack penalty per [[3-wiki/decisions/2026-05-07-v1-reliability-implementation-uses-deterministic-eens-constraints|DEC-002]]; Lagrange relaxation (Zampara 2025) is conceptual reference only."
- In "Main Scenarios" under "EENS weather robustness": append "weather year set defined in `06_reproducibility_and_scenarios.md` Scenario 4 lock — configurable list, default `[2019, 2020, 2021, 2022, 2023, 2024]`."

---

## Module 01 — Reliability Formulation
**Status:** NEEDS EDIT
**Issues found:**
- Core formulation matches DEC-002 exactly: `ENS_b,y,all <= ENS_limit_b,y,all + slack_b,y` with slack penalty added to `n.model.objective`. No Lagrange anywhere. Good.
- η values (0.25 / 0.60 / 0.90 for 2030/2040/2050) are written as "central pathway values" — but the text does not explicitly state "these must be exposed as config params, not hardcoded constants." Per questionnaire Q4, configurability is a binding requirement.
- **Unit confusion (IMPORTANT):** Module 01 says "slack penalty calibrated relative to `1000 * solving.options.load_shedding`." Module 07 numerical defaults list `load_shedding = 100 (EUR/kWh; upstream default)` and `slack.penalty_eur_per_mwh = 100000`. The math: 100 EUR/kWh × 1000 kWh/MWh = 100,000 EUR/MWh, then `1000 * load_shedding` → 100,000,000 EUR/MWh. V1 target is 100,000 EUR/MWh. The formula is only correct if `load_shedding` is in EUR/MWh (= 100,000), NOT EUR/kWh (= 100). Must reconcile units.

**Recommended edits:**
- After "Central pathway values are...", add: "η values for each horizon must be exposed as config params under `reliability.pathway.improvement_eta_by_horizon[y]` — NOT hardcoded. Scenario sweeps and Scenario 5 stringency frontiers change them at runtime."
- Add unit-reconciliation note in Slack section: "Slack penalty target is 100,000 EUR/MWh per V1 lock. `solve_network.py` stores `load_shedding` in EUR/kWh and multiplies by 1000 to get EUR/MWh. Therefore `slack.penalty_eur_per_mwh = 1 * load_shedding_in_eur_per_mwh = load_shedding_in_eur_per_kwh * 1000`. Lock the unit in Module 07 Section 4."

---

## Module 02 — Solver Integration
**Status:** OK
**Issues found:**
- Hook location and `extra_functionality` patching strategy is correct — `scripts/solve_network.py` confirmed present.
- Mode taxonomy (`diagnostic`, `ens_only`, `ens_and_budget`) is consistent with DEC-002 deterministic LP. No Lagrange outer loop.
- `assign_all_duals=True` for dual extraction matches the dual-of-ENS-cap interpretation in DEC-002.
- `skip_iterations: true` locked. Good.
- `noisy_costs: true` fails validation — consistent with reproducibility lock.

**Recommended edits:** none.

---

## Module 03 — Myopic Electricity-Only Workflow
**Status:** OK
**Issues found:**
- Warning "Do not reuse the upstream parse-time global `load_data_paths`" verified necessary — `Snakefile` line 66 is parse-time. Module 03 correctly flags this and provides a per-horizon helper.
- Required rules (`solve_elec_myopic_pathway`, `add_existing_elec_baseyear`, `add_elec_brownfield`, etc.) match actual pypsa-earth scripts.
- GEGIS `weather_year` for demand (era5_2013) vs Atlite supply-side weather year for Scenario 4 — distinction is correct but potentially confusing to implementer.

**Recommended edits:** optionally clarify that `weather_year` in the GEGIS demand section is the demand-side ERA5 year for SSP load profiles, distinct from the Atlite supply-side weather year used in Scenario 4.

---

## Module 04 — Carry-Forward Contract
**Status:** OK
**Issues found:**
- Component-by-component carry-forward semantics are internally consistent and align with DEC-002 investment-cost framing.
- `keep_existing_capacities: false` requirement correctly addressed.
- `StorageUnit` explicit-handling note is a real upstream gap worth verifying in `add_brownfield.py`.

**Recommended edits:** none.

---

## Module 05 — Tests And Acceptance
**Status:** OK
**Issues found:**
- All fixtures map to V1 deterministic LP. Consistent with DEC-002.
- Iteration fixture correctly enforces `skip_iterations: true`.
- Scenario 4 smoke gate ("Run Scenario 4 weather-year EENS cases only after deterministic ENS pathway passes") correctly frames weather years as **independent post-hoc sweeps**, not a multi-scenario solve.

**Recommended edits:** none.

---

## Module 06 — Reproducibility And Scenarios
**Status:** BLOCKER
**Issues found:**
- **BLOCKER — weather-year set contradicts questionnaire Q3.** Module 06 line 207: `candidate weather years: {2013, 2018, 2019, 2020}` for V1. Questionnaire Q3 answer: `2019–2024`. Direct contradiction with a user-supplied decision. Must be resolved before implementation.
- Scenario 4 design ("per-weather-year independent solves with post-hoc weighted aggregation; multi-scenario LP and Lagrange relaxation explicitly out of V1 scope") correctly reflects DEC-002. Good.
- Central η values (0.25/0.60/0.90) correct. But "configurable" intent is only implied; must be explicit per Q4.
- Scenario 4 weather-year probability weights: "equal weights are V1 default" — consistent with independent-sweeps design.

**Recommended edits:**
- **Critical:** Replace line 207 candidate weather years with the list from Q-001 answer (configurable list, default `[2019, 2020, 2021, 2022, 2023, 2024]`). Add: "2024 ERA5 cutout availability must be verified by the dry-run gate; if incomplete, drop with recorded exclusion reason."
- Add to "Central Target Parameters": "`eta_2030`, `eta_2040`, `eta_2050` are config parameters under `reliability.pathway.improvement_eta_by_horizon[y]` — defaults only, not hardcoded. Scenario sweeps change them at runtime."
- Add one-liner in Scenario 4 description: "This independent-sweep design is the V1 implementation per [[DEC-002]]; multi-scenario stochastic LP / Lagrange decomposition is conceptual reference only."

---

## Module 07 — Implementation Handoff (DRAFT → must reach FROZEN)
**Status:** BLOCKER
**Cannot be promoted to FROZEN until the following are filled.**

### Section 1 — Repo Layout (all unfilled)
Must fill:
- PyPSA-Earth fork URL: `https://github.com/nylanramnauth-droid/pypsa-earth-sa` (from wiki architecture page)
- Local clone path: `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth/`
- Upstream remote: `https://github.com/pypsa-meets-earth/pypsa-earth.git` (no push)
- Working branch: **from Q-REL-01** (user decision needed — recommend `feature/reliability-v1`)
- Release tag the fork is based on: get via `git describe --tags` in repo
- `solve_network.py` patch table line ranges: get via inspecting the file
- Plan files mirrored to repo path: resolve the `docs/active/source_of_truth/` vs `doc/active/` question

### Section 2 — Version Pins (all unfilled, values known from questionnaire)
Fill with:
- Gurobi version: `13.0.0`
- License type: `academic, named-user`
- License path: `/Users/nylan/gurobi.lic`
- License expiry: `2027-01-20`
- PyPSA-Earth release tag: get via repo inspection
- Fork commit hash for V1 freeze: record on first freeze commit
- `pypsa`, `linopy`, Python versions: get via `pip freeze` in locked env
- Dual-sign fixture pass date: pending fixture run

### Section 3 — External Input Contract (partially unfilled)
Add a dedicated **Observation Schema Adapter** subsection:
```
Input:  Reliability-Assessment repo
        settlement_reliability_yearly_strict_yearlykeep_postdoe.parquet
        (columns: settlement_id, year, n_days_obs, uptime, population, lon, lat)
Adapter steps:
  1. Join settlement geometry from settlement GPKG by settlement_id
  2. Rename: n_days_obs → n_observations
  3. Derive: source_year = 2023 (from year column 2023-01-01 or filename)
  4. Write as GeoParquet with CRS = EPSG:4326
Output path: data/reliability/observations/ntl_settlement_2023.parquet (lock this path)
Owner: dealt with in parallel workstream — pypsa model consumes the output; it does NOT own production
Expected schema: settlement_id, geometry, population, uptime, n_observations, source_year, CRS
```
Also fill: NTL settlement file path, Eskom-34 busmap path (`data/custom_busmap_elec_s_34.csv`, from Cal module 09), cost-data retrieval choice, Atlite cutout list (2019–2024 configurable).

### Section 4 — Numerical Defaults (values known, units need reconciliation)
Fill with:
- Gurobi `Threads = 1` (from questionnaire; switch to 2 only if benchmark warrants)
- **Unit reconciliation (IMPORTANT):** `solving.options.load_shedding` is stored in EUR/kWh (upstream default = 100 EUR/kWh = 100,000 EUR/MWh). `solve_network.py` multiplies by 1000 when applying it. Therefore `slack.penalty_eur_per_mwh = load_shedding_eur_per_kwh * 1000 = 100 * 1000 = 100,000`. Change the "Source" column from `1000 * load_shedding` to `load_shedding_eur_per_kwh * 1000` and add a unit column.

### Section 5 — Snakemake Stubs
Scaffold provided. `RDIR = run["name"] + "/"` confirmed compatible with upstream `Snakefile`. Verify `<RDIR>` substitution matches the za overlay `run.name: za_2023_fixed`.

### Section 6 — Scenario Disambiguation
Add explicit weather-year list: `[2019, 2020, 2021, 2022, 2023, 2024]` (configurable, from Q-001 answer), once Module 06 is corrected.

### Top of module — DEC-002 anchor (missing)
Add: "All numerical and configuration locks below assume the V1 deterministic single-shot LP method per [[3-wiki/decisions/2026-05-07-v1-reliability-implementation-uses-deterministic-eens-constraints|DEC-002]]. No Lagrange / dual-decomposition machinery is implemented in V1."

---

## What the Implementing Agent Must Do to Freeze Module 07

The following require **repo inspection** (Codex, not Claude):
1. `git describe --tags` → PyPSA-Earth release tag
2. Read `scripts/solve_network.py` → patch table line ranges for `extra_functionality` hook insertion
3. `pip freeze` in the locked conda/venv env → `pypsa`, `linopy`, `atlite`, Python versions
4. Verify `cutouts/` for 2019–2024 ERA5 cutout availability

The following require **user answers** (from `dashboards/_questions.md`):
- Q-REL-01: working branch name
- Q-001: weather year list confirmation (partially answered)

The following are **known from questionnaire** and can be filled directly:
- All Gurobi values (version, license path, expiry, Threads)
- Observation schema adapter steps
- η_y defaults and config-param requirement
