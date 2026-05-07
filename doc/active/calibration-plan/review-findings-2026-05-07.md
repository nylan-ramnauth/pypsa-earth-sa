# Calibration Plan — Pre-Implementation Review Findings
**Date:** 2026-05-07 | **Reviewer:** Claude Opus 4.7 (via Claude Code)
**Scope:** All 14 modules (00–13) audited against pypsa-earth repo, pypsa-rsa repo, full wiki, and pre-implementation decisions questionnaire.

---

## Summary

| Count | Status |
|---|---|
| 2 | OK |
| 9 | NEEDS EDIT |
| 1 | BLOCKER |

**Top 3 risks to implementation sequencing:**
1. **Module 06 BLOCKER** — Eskom 8760 demand never wired to `build_demand_profiles.py`. Blocks 06→09→10→11→12→13.
2. **Local carrier injection hook unspecified** — `sasol_coal`, `sasol_gas`, `ocgt_diesel`, `ocgt_gas`, `other_re` injection hook referenced in 5 modules (01, 05, 07, 08, 10) but never specified anywhere.
3. **`docs/active/source_of_truth/` path** — does not exist in pypsa-earth repo (`doc/` exists, not `docs/`). Module 13's handoff receiving-contract column is entirely unenforceable.

**Good news found:** `cutouts/cutout-2023-era5.nc` already exists in the repo. Module 03's ERA5 build prerequisite is already satisfied.

---

## Module 00 — Governance And Scope
**Status:** OK
**Issues found:**
- References `docs/active/source_of_truth/` throughout. Path does not exist in pypsa-earth repo. This is scaffolding for Track 1 (copy plans into repo), but the name must be settled before Track 1.
- Assumes reliability plan lives inside the pypsa-earth repo. Currently it lives in vault under `6-codebases/Plans/`.

**Recommended edits:**
- Add a clarification: "plan files are in the vault at `6-codebases/Plans/`; mirrored into repo at `doc/active/` as part of Track 1 bootstrap." Settle the final repo path before copying.

---

## Module 01 — Repo Bootstrap And Config
**Status:** NEEDS EDIT
**Issues found:**
- Plan says `config/za/`. Repo uses `configs/` (plural). Creating `config/za/` creates a confusing parallel directory that Snakemake does not auto-merge.
- Plan does not say HOW the za overlay reaches the Snakemake workflow. The Snakefile loads 4 configfiles in fixed order; nothing in `configs/za/` is auto-included.
- Pre-flight asks agent to "verify prebuilt 2023 cutout" but does not say the cutout already exists as `cutouts/cutout-2023-era5.nc`. Should detect-and-reuse, not rebuild.
- `config/za/za_2023_grid_audit.yaml` and `config/za/za_expansion_base.yaml` listed as required artifacts but no later module uses them by name — dead artifacts.
- `electricity.extendable_carriers: { Store: [] }` override disables upstream `[battery, H2]` default — must be flagged explicitly.
- Pre-flight does not require recording `load_options` (ssp/weather_year/prediction_year), needed for Module 06 demand work.

**Recommended edits:**
- Replace all `config/za/` with `configs/za/` throughout modules 01, 03, 05, 10.
- Add "Overlay composition" section: "append `configfile: 'configs/za/za_2023_fixed_validation.yaml'` to the Snakefile block at lines 38–41, OR invoke with `--configfile configs/za/za_2023_fixed_validation.yaml`. Do not edit `config.yaml` directly."
- Drop `za_2023_grid_audit.yaml` and `za_expansion_base.yaml` or justify their use.
- Add: "Pre-flight detects `cutouts/cutout-2023-era5.nc`; if present, records its hash and treats `build_cutout` dependency as satisfied (`enable.build_cutout: false, enable.retrieve_cutout: false`)."
- Add `load_options` to the pre-flight inventory.
- Lock Gurobi solver options here (not floating as a preflight artifact): `solving.solver_options.za_gurobi: { Threads: 2, Method: 2, Crossover: 0, BarConvTol: 1e-8, Seed: 0 }`. Module 11 says "do not override Module 01 preflight options" — those options must be pinned here, not left as TBD.

---

## Module 02 — Eskom Validation Data Pipeline
**Status:** NEEDS EDIT
**Issues found:**
- Input file path is just `eskom_data_2023_full.csv`. Actual file is at `<repo-root>/eskom_data_2023_full.csv` (repo root, not `data/`). Path must be anchored.
- Raw CSV coverage starts `2022-12-01`, not `2023-01-01`. Filter step is correct but plan should flag actual coverage span so parser report records dropped rows precisely.
- Time format: `Date Time Hour Beginning` uses 12-hour AM/PM clock (`12:00:00 AM`). Plan does not specify format string.
- For each locked anchor value, plan does not cite source (Eskom annual report page, System Adequacy Outlook, etc.).
- `Eskom Gas Generation = 0` in 2023 raw data is expected (not a parser error) — plan should say this explicitly.

**Recommended edits:**
- Change "Input" to: "`<pypsa-earth-repo-root>/eskom_data_2023_full.csv` (current location; consider moving to `data/za_validation/raw/` during bootstrap)."
- Add: "Raw CSV coverage starts 2022-12-01; 2023 filter drops pre/post rows; parser report must record pre-count and post-count."
- Add: "Time format: `%Y-%m-%d %I:%M:%S %p` (12-hour AM/PM)."
- For each locked anchor, add a `source` column (Eskom annual report, page number).
- Note: "Eskom Gas Generation = 0 in 2023 raw data is expected and is not a parser error."

---

## Module 03 — Weather Cutout And Profiles
**Status:** NEEDS EDIT
**Issues found:**
- `atlite.default: cutout-2023-za-era5` — actual existing repo cutout is named `cutout-2023-era5.nc` (no `za` infix). As written, agent rebuilds a cutout that already exists.
- Plan says `enable.retrieve_cutout: false, build_cutout: true`. With the prebuilt cutout already present, this should be `build_cutout: false`.
- `za_baseline.csp_profile_mode: native | fallback` — plan-invented config key with no consumer in repo. Which script reads it? What does fallback produce?
- Profile output path uses `resources/<run>/...` generic placeholder. With `run.name: za_2023_fixed`, the path is `resources/za_2023_fixed/renewable_profiles/profile_<tech>.nc`. Use the concrete run name throughout.

**Recommended edits:**
- Change `atlite.default: cutout-2023-za-era5` to `atlite.default: cutout-2023-era5` (match existing file).
- Replace `enable:` block with: "If `cutouts/cutout-2023-era5.nc` exists with verified provenance, set `enable.retrieve_cutout: false`, `enable.build_cutout: false`. Otherwise set `build_cutout: true`."
- Add: "Set `run.name: za_2023_fixed` in za overlay. All downstream output paths use `resources/za_2023_fixed/...`."
- Either delete `za_baseline.csp_profile_mode` or implement it: name the script that reads it, declare the fallback artifact path, link carrier metadata.

---

## Module 04 — Source Data Audits
**Status:** OK
**Issues found:**
- Both flat and nested copies of some pypsa-rsa files exist (e.g. `data/bundle/Existing_Lines.shp` and `data/bundle/Shapefiles/Existing_Lines.shp`). Registry must pick canonical copy.
- Frozen pypsa-rsa commit `89872c1e...` must be verified on entry (`git rev-parse HEAD`).

**Recommended edits:**
- Add: "where flat and nested copies both exist, record both with hashes and designate the deeper scenario-tagged copy as canonical unless a content diff is recorded."
- Add: "`git rev-parse HEAD` in pypsa-rsa must match `89872c1ea703af3d8a3f198706d1ab7958f50a5f`; otherwise rerun audit before locking."

---

## Module 05 — System Boundary And Carrier Taxonomy
**Status:** NEEDS EDIT
**Issues found:**
- `bioenergy` vs upstream `biomass`: upstream `conventional_carriers` uses `biomass`. Plan uses `bioenergy`. Silent collision risk.
- `ocgt_diesel` vs `ocgt_gas` vs upstream `OCGT` (uppercase): case mismatch could silently bypass upstream carrier logic.
- Local carrier cost rows (`sasol_coal`, `sasol_gas`, `ocgt_diesel`, `ocgt_gas`, `other_re`) require entries in `costs.csv`, carrier rows in the network, and CO2 emissions factors — deferred to Module 07 and 10, but no registration table exists anywhere.

**Recommended edits:**
- Reconcile `bioenergy` vs upstream `biomass`: pick one canonical name and document the alias.
- State case-policy: "all local carrier names are lowercase snake_case; upstream carriers retain upstream casing (`OCGT`, `CCGT`, `H2`)."
- Add "Carrier Registration Contract" subsection: "Module 07 owns cost rows; Module 10 owns the local hook that writes carrier rows to the network. This module owns canonical name, profile intent, and emissions factor. The hook runs after `add_electricity` and must not mutate upstream `Carrier` rows."

---

## Module 06 — Demand Import Export Model Inputs
**Status:** BLOCKER
**Issues found:**
- `build_demand_profiles.py` is hardcoded to consume GEGIS data from `data/ssp2-2.6/<year>/era5_<weather_year>/Africa.{csv,nc}`. The plan's contract file `data/za_validation/za_2023_demand_profile.csv` has **no wiring into this pipeline**. No module explains how the Eskom 8760 reaches `build_demand_profiles.py`.
- **However:** repo already ships `data/ssp2-2.6/2030/era5_2023_custom/Africa.csv` — a GEGIS-compatible slot exists. The correct fix is to write the Eskom-derived 8760 into this slot in GEGIS schema, then set `load_options.weather_year: 2023_custom`. Plan ignores this slot entirely.
- Plan says single-node attaches to "the national ZA bus" — but `build_demand_profiles.py` distributes demand by GADM/GDP/population to each bus. Single-node is resolved by `clusters: 1` which collapses allocation to one bus; plan should say this explicitly.
- Module 06 declares bus attachment "tables" but defers schema to Module 09. Module 09 says it "binds" those tables. Neither owns the column spec or sum-to-one constraint — circular dependency.
- `Other RE` clipping policy (`p_min_pu = p_max_pu = series / p_nom`) says "clipped to [0,1]" but hours where `Eskom Other RE / p_nom > 1` can occur. Clipping policy not specified.

**Recommended edits:**
- Add "Integration Contract" subsection: "The Eskom 8760 profile is exported in GEGIS-compatible schema to `data/ssp2-2.6/2030/era5_2023_custom/Africa.csv` (slot already present in repo). Set `load_options.weather_year: 2023_custom`, `load_options.prediction_year: 2030` in the za overlay. Validate GEGIS-schema columns required by `build_demand_profiles.py:get_load_paths_gegis`."
- Add alternative path: "If GEGIS-route is rejected, a local Snakemake rule `build_za_demand_profiles` overrides `resources/<run>/demand_profiles.csv` directly. Document the hook here."
- Define bus attachment schema in Module 06 (columns, sum-to-one constraint, layer key) so Module 09 only resolves bus IDs, not invents schema.
- Lock `Other RE` clipping policy: "values < 0 → 0; values > p_nom → 1 with parser warning logged when daily-max ratio exceeds 1.05."
- Single-node attachment: "single-node = Module 09 declares `clusters: 1`; GEGIS allocation collapses to one bus by construction. No separate hook needed."

---

## Module 07 — Costs Fuels Efficiencies And COUE
**Status:** NEEDS EDIT
**Issues found:**
- No `costs_2023.csv` exists in repo. Cost files are `costs.csv`, `costs_2025.csv`, `costs_2030.csv`. `config.default.yaml` defaults to `costs.year: 2030`. Plan does not say which year to use for a 2023 baseline.
- Plan says "this module owns the baseline load-shedding cost" but **never picks a value**. Module 11 needs a concrete number.
- Local carrier cost rows (`sasol_coal` etc.) — mechanism for injection unspecified: does this monkey-patch `costs.csv`, write a sidecar CSV, or add to `process_cost_data.py`?
- Currency not locked: upstream uses EUR; pypsa-rsa uses ZAR. Decision needed before writing any COUE row.

**Recommended edits:**
- Add: "Lock `costs.year: 2030` (upstream default, no 2023 file available). Document as known limitation."
- Add: "V1 load-shedding cost = `[answer from Q-003 below or 100 EUR/kWh inherited from upstream default]`. Implemented via `solving.options.load_shedding: <value>`. Unit: EUR/kWh as stored; multiplied by 1000 to EUR/MWh in `solve_network.py:161`."
- Add: "Local carrier cost rows are written to `data/za_audit/za_local_carrier_cost_rows.csv` and injected by the Module 10 local hook AFTER `add_electricity.py`. The hook adds `n.carriers` rows and `Generator.marginal_cost` overrides; it does NOT modify `costs.csv`."
- Lock currency: "All costs in EUR; ZAR values converted using 2023 exchange rate documented in `za_costs_fuels_efficiencies_audit.csv`."

---

## Module 08 — Fleet Reconciliation And Custom Powerplants
**Status:** NEEDS EDIT
**Issues found:**
- Plan: "Put `id` first so `read_csv(..., index_col=0)` does not consume `Name`." Actual `data/custom_powerplants.csv` header starts with `Name,Fueltype,...` — no `id` column. Adding `id` as first column may break `build_powerplants.py` if it expects `Name` at index 0. Upstream `add_electricity.py` uses `pd.read_csv(...)` without `index_col=0`, so `id`-first rule solves a non-problem.
- `hydro_import` is in the normalization smoke list, but Module 08's own text says "`hydro_import` is not a `custom_powerplants.csv` plant" — internally inconsistent.
- The upstream powerplants filter `electricity.powerplants_filter` is `(DateOut >= 2022 or DateOut != DateOut) and (DateIn <= 2023 or DateIn != DateIn)` (verified in `config.default.yaml:220`). Plan must align this filter window and cite it explicitly.
- `data/custom_powerplants.csv` is currently header-only (empty). Plan should say "replace atomically with reconciled fleet."

**Recommended edits:**
- Remove or validate the "Put `id` first" rule against `build_powerplants.py`. As-is the rule is unjustified.
- Drop `hydro_import` from normalization smoke list.
- Pin `electricity.powerplants_filter` in the za overlay so the 2023 in/out window is explicit.
- Add: "repo ships empty `data/custom_powerplants.csv` (header-only); this module replaces it atomically."

---

## Module 09 — Grid Spatial And Transmission Model
**Status:** NEEDS EDIT
**Issues found:**
- Plan cites `docs/active/source_of_truth/00_overview.md` for the `clusters: 34` lock. That path does not exist in the repo. The correct citation is the user's project decision (DEC-001 / user questionnaire answer Stage 4b).
- `subregion.method: custom` and `enable.custom_busmap: true` confirmed valid in `config.default.yaml`.
- `data/custom_busmap_elec_s_34.csv` name matches pypsa-earth wildcard `custom_busmap_elec_s{simpl}_{clusters}.csv` with `simpl: ""` — OK.
- Plan does not pick between: (A) hand-built busmap or (B) custom subregion shapefile for the 34-region build. Both are options; one must be chosen.
- St Clair limit formula coefficients (53.736, -0.65) differ from pypsa literature (43.261, -0.6678). Source not cited.
- Locked spatial level must propagate to `scenario.clusters` in za overlay — plan does not require this.

**Recommended edits:**
- Replace citation to `docs/active/source_of_truth/00_overview.md` with "user project decision: Stage 4b (Eskom-34), per `pre-implementation-decisions.md` Q2."
- Pick V1 busmap path: "V1 path = custom busmap (`enable.custom_busmap: true`, file `data/custom_busmap_elec_s_34.csv`). Custom subregion shapes are fallback if coverage check fails."
- Cite source for St Clair coefficients (53.736, -0.65) — likely pypsa-rsa; verify and record.
- Add: "locked spatial level must be written to `scenario.clusters: [34]` in za overlay."

---

## Module 10 — Fixed Capacity Network Build
**Status:** NEEDS EDIT
**Issues found:**
- "Local network-injection hook" referenced in modules 01, 05, 07, 08, 10 but never specified: what rule, what inputs, what outputs?
- Network audit CSV schema: `bus_count` is underspecified for multi-bus runs (count of buses with ≥1 generator, or total generator count?).
- `extendable_carriers: { Generator: [], ... }` locks all extension off. `solve_network.py` adds load-shedding generators at solve time — these are technically extendable but are a safety valve, not a capacity expansion variable. Audit gate "no unintended extendable capacity" would trip on these.

**Recommended edits:**
- Add "Local Hook Contract" subsection: rule name = `apply_za_local_carriers`; input = `<network-from-add_electricity>`; output = `<network-with-local-carriers>`; consumes `data/za_audit/za_local_carrier_cost_rows.csv` and `data/za_audit/za_2023_other_re_attachment.csv`.
- Tighten audit schema: `bus_count` = number of buses with ≥1 generator/storage of this carrier; add `generator_count`; aggregate per-carrier across all buses.
- Add: "load-shedding generators added by `solve_network.py:add_load_shedding` are excluded from 'no extendable capacity' gate; document with `is_load_shedding_safety_valve: true` flag in audit CSV."

---

## Module 11 — Dispatch Calibration And Availability
**Status:** NEEDS EDIT
**Issues found:**
- "Do not override Module 01 preflight Gurobi options" — but Module 01 does not pin them; it says "record." Module 11 inherits an empty pin. User decision: `Threads = 1/2`, batched parallelism — must be locked in Module 01 (see Module 01 edits).
- `EAF = 1 - (PCLF + UCLF + OCLF)` — raw Eskom data column is `Total UCLF+OCLF` (sum) and `Total PCLF` (separate). Plan should cite exact column names from Module 02.
- Repo ships `data/eaf_weekly.csv` and `data/nuclear_p_max_pu.csv` (verified). Module 11 does not mention them. Must decide: use, ignore, or replace.
- Solved-network output path `results/za_2023_fixed/networks/elec_s_<clusters>_solved.nc` missing `_ec_l{ll}_{opts}` suffix from upstream pattern. Must resolve wildcards to a concrete path (e.g., with `ll: c1`, `opts: Co2L0`).

**Recommended edits:**
- Move Gurobi options to Module 01 (see Module 01 edits); Module 11 only says "use options from za overlay."
- Add exact Eskom column names: "UCLF + OCLF from parser-repaired `Total UCLF+OCLF`; PCLF from `Total PCLF`."
- Add: "Inspect `data/eaf_weekly.csv` and `data/nuclear_p_max_pu.csv` in pre-flight. V1 default: disable both (Eskom-derived EAF takes precedence); document if one is retained."
- Resolve output path to concrete pattern using locked `ll`/`opts` wildcards (e.g., `elec_s_34_ec_lc1_Co2L0.nc`).

---

## Module 12 — Validation Reporting And Acceptance
**Status:** OK
**Issues found:**
- "Missing source provenance" exclusion is vague; should gate against specific manifest files.
- PHS representation idiom (StorageUnit vs Store+Link) depends on pypsa-earth version — must be detected post-build.

**Recommended edits:**
- Tighten "missing source provenance": "every artifact in `data/za_audit/input_file_manifest.csv` and `source_hashes.csv` must have non-empty `hash` and `source`; otherwise Stage 1 blocks."
- Add: "detect PHS representation mode (StorageUnit vs Store+Link) post-build; validation script must use the correct idiom."

---

## Module 13 — Expansion And Reliability Handoff
**Status:** NEEDS EDIT
**Issues found:**
- Every "receiving contract" row references `docs/active/source_of_truth/07_implementation_handoff.md` — path does not exist in repo. Track 1 must settle the final repo path before Module 13 can be used.
- η_y stringency (0.25/0.60/0.90 for 2030/2040/2050, parametric per Q4) has no representation in the handoff table.
- Weather years 2019–2024 (Scenario 4, per Q3) require additional ERA5 cutouts beyond the 2023 baseline — not mentioned in handoff table.
- Observation schema adapter (geometry join, `n_days_obs → n_observations`, `source_year=2023`, GeoParquet) not in handoff table.
- Eskom-34 busmap path not pinned — should be `data/custom_busmap_elec_s_34.csv`.

**Recommended edits:**
- Replace all `docs/active/source_of_truth/` references with settled Track 1 repo path (e.g. `doc/active/reliability-plan/07_implementation_handoff.md`).
- Add "Reliability Stringency Parameters" row: "η_y values (0.25/0.60/0.90 default) passed as `za_reliability_eta_y.csv`; parametric, not hardcoded."
- Add weather-year handoff row: "Scenario 4 requires ERA5 cutouts for 2019–2024; 2023 cutout is pre-existing; additional years built by reliability workstream or separate scoping task."
- Add observation schema row: "settlement-level GeoParquet with geometry joined by `settlement_id`, `n_days_obs → n_observations`, `source_year = 2023`, CRS = EPSG:4326."
- Pin busmap path: "`data/custom_busmap_elec_s_34.csv`."

---

## Cross-Module Dependency Gaps

| Gap | Affects modules |
|---|---|
| `06 ↔ 09` circular schema dependency (bus attachment table owner) | 06, 09 |
| `01 → 11` solver options not pinned in Module 01 | 01, 11 |
| `02 → 06 → 10` Other RE clipping policy unowned | 02, 06, 10 |
| `05 → 07 → 10` local carrier registration hook (n.carriers writer) | 05, 07, 10 |
| `08 → 09` bus column ownership (who overwrites `data/custom_powerplants.csv`'s `bus` field?) | 08, 09 |
| `13 ↔ user decisions` η_y / weather years / observation schema missing from handoff | 13 |
