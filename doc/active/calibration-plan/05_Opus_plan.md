Calibration Plan Module 05 — System Boundary And Carrier        
 Taxonomy Implementation Plan                                    
                                                                 
 Context                                                       
                                                                 
 Modules 00–04 of the ZA Calibration Plan are complete on main
 of
 6-codebases/repos/pypsa-earth. Module 05
 (doc/active/calibration-plan/05_system_boundary_and_carrier_tax
 onomy.md) locks
 the V1 modeling boundary and the carrier taxonomy so downstream
  modules
 (06 demand, 07 costs, 08 fleet, 09 grid, 10 local carriers, 11
 dispatch) cannot
 make ad hoc choices.

 Module 05 is doc + config + spec. It does not build, solve, or
 write
 fleet/cost/grid overrides. Its outputs are:

 1. canonical taxonomy doc doc/za_carrier_taxonomy.md
 2. machine-readable mirror
 data/za_audit/za_carrier_taxonomy.csv
 3. config-side locks in
 configs/za/za_2023_fixed_validation.yaml
 4. forward-looking smoke-test script for the CSP/solar
 assertion (fires when
 module 10's apply_za_local_carriers hook materializes the
 network)
 5. notebook + HTML overview
 6. provenance + impl log + vault updates

 Implementation actor: Claude (Opus) implements directly
 in-session. No
 Codex handoff. User supervises.

 Delegation rules (from Module 05 plan §Carrier Registration
 Contract)

 - 05 owns: canonical local-carrier names, profile intent,
 emissions intent,
 reporting metadata (color / nice_name), validation target,
 availability
 treatment, system-boundary locks, CSP lock.
 - 07 owns: the populated cost rows in
 data/za_audit/za_local_carrier_cost_rows.csv (numeric values).
 - 08 owns: the active-2023 biomass decision and final fleet
 reconciliation.
 - 10 owns: the apply_za_local_carriers hook that adds local
 rows to the
 network after add_electricity (must not mutate upstream Carrier
  rows).

 Module 05 must therefore ship the structure (carrier names,
 metadata
 schema) without the values that downstream modules own.

 Pin re-confirmation (already done in plan phase)

 - PyPSA-RSA pin 89872c1ea703af3d8a3f198706d1ab7958f50a5f is
 HEAD = origin/main.
 - Claude must re-confirm at module entry and record both hashes
  in
 doc/za_implementation_log.md.

 User comment overrides (90_Comments_Questions.md §05)

 - "None" — no overrides for module 05.

 User scope decisions (this session)

 - Smoke-test gate handled via deferred script
 scripts/za_validation/smoke_carrier_taxonomy.py that fires when
  a network
 built by module 10 exists; gate marked "pending module 10" in
 impl log.
 - electricity.extendable_carriers locked to all-empty (true V1
 fixed-fleet).

 ---
 Repos and absolute paths

 - PyPSA-Earth: /Users/nylan/Documents/BSE/Reliable-Electrificat
 ion-Planning-SA-Vault/6-codebases/repos/pypsa-earth
 - PyPSA-RSA:   /Users/nylan/Documents/BSE/Reliable-Electrificat
 ion-Planning-SA-Vault/6-codebases/repos/pypsa-rsa

 All Claude code/edits land inside the pypsa-earth repo.
 PyPSA-RSA is
 read-only; only its commit hash is referenced.

 ---
 Implementation steps

 Step 1 — Re-verify the pin and capture environment

 1. In pypsa-rsa: git rev-parse HEAD and git rev-parse
 origin/main.
 Record both hashes in doc/za_implementation_log.md under the
 new module
 05 entry.
 2. Capture pypsa-earth HEAD too.
 3. Activate conda env pypsa-earth
 (/opt/anaconda3/envs/pypsa-earth).

 Step 2 — Lock system boundary and carrier taxonomy in the
 config

 Modify configs/za/za_2023_fixed_validation.yaml. Add three new
 top-level
 blocks. Preserve all existing keys; do not mutate Module 04
 keys
 pypsa_rsa_root, pypsa_rsa_pinned_commit.

 2a — za_system_boundary block

 za_system_boundary:
   scope: "national South Africa 2023 electricity system"
   demand_target: "RSA Contracted Demand"
   load_shedding_target: "MLR + ILS + IOS"
   imports_exports: "exogenous time series owned by module 06"
   embedded_pv_treatment: "excluded as explicit plant capacity
 in V1; documented as residual demand/accounting issue"
   ipp_utility_inclusion: "included when present in Eskom
 reported generation and 2023 plant reconciliation"
   csp_2023_anchors:
     installed_capacity_mw: 500
     generation_twh: 1.375
     redstone_excluded: true
     profile_route: "native_atlite_first;
 documented_temporary_fallback_allowed"

 2b — Lock
 electricity.{conventional,renewable,extendable}_carriers

 Replace/extend electricity block:

 electricity:
   # ... existing keys preserved ...
   conventional_carriers: [coal, nuclear]    # upstream V1
 baseline; local carriers added by module 10 hook
   renewable_carriers: [solar, onwind, hydro, csp]
   extendable_carriers:
     Generator: []
     StorageUnit: []
     Store: []
     Link: []

 CSP stays in renewable_carriers (so atlite picks up the
 profile). All
 extendable_carriers lists empty — V1 is true fixed-fleet.

 Local carriers (sasol_coal, sasol_gas, ocgt_diesel, ocgt_gas,
 other_re) are not added to upstream conventional_carriers —
 module 10's
 hook adds them post-add_electricity.

 2c — za_local_carriers block (structural metadata only)

 za_local_carriers:
   sasol_coal:
     component: Generator
     color: "#4d4d4d"
     nice_name: "Sasol coal"
     profile_intent: "fixed dispatch from coal-equivalent
 availability profile (module 11)"
     emissions_intent: "explicit row in module 07 cost CSV"
     validation_target: "Eskom 2023 coal generation
 reconciliation (sub-row)"
     availability_treatment: "owned by module 08 fleet
 reconciliation"
   sasol_gas:
     component: Generator
     color: "#a06030"
     nice_name: "Sasol gas"
     profile_intent: "fixed dispatch; gas-equivalent
 availability"
     emissions_intent: "explicit row in module 07"
     validation_target: "Eskom 2023 OCGT/gas reconciliation
 (sub-row)"
     availability_treatment: "owned by module 08"
   ocgt_diesel:
     component: Generator
     color: "#cc6633"
     nice_name: "OCGT diesel"
     profile_intent: "peaker; high marginal cost; module 11
 dispatch"
     emissions_intent: "explicit row in module 07"
     validation_target: "Eskom 2023 OCGT/diesel reconciliation"
     availability_treatment: "owned by module 08"
   ocgt_gas:
     component: Generator
     color: "#d35050"
     nice_name: "OCGT gas"
     profile_intent: "peaker; module 11 dispatch"
     emissions_intent: "explicit row in module 07"
     validation_target: "Eskom 2023 OCGT/gas reconciliation"
     availability_treatment: "owned by module 08"
   other_re:
     component: Generator
     color: "#88c057"
     nice_name: "Other RE"
     profile_intent: "exogenous: Eskom 8760 'Other RE' series
 for V1 accounting"
     emissions_intent: "zero CO2 by default; row in module 07"
     validation_target: "Eskom 2023 Other RE energy total"
     availability_treatment: "exogenous time series, no
 availability filter"

 Cost numeric values are NOT in this block — module 07 owns
 data/za_audit/za_local_carrier_cost_rows.csv.

 Step 3 — Canonical taxonomy doc

 New file: doc/za_carrier_taxonomy.md (hand-written canonical
 doc).
 Sections in order:

 4. Provenance header — date, author (Claude Opus), pypsa-earth
 HEAD,
 pypsa-rsa pin, source plan path.
 5. System boundary — copy the lock table from Module 05 §System
  Boundary
 Locks verbatim.
 6. Carrier taxonomy — full RSA → V1 mapping table (15 rows:
 coal,
 sasol_coal, nuclear, ocgt_diesel, ocgt_avf/ocgt_gas, sasol_gas,
  wind,
 solar PV, solar_csp, reservoir hydro, run-of-river, pumped
 storage,
 battery, hydro_import, biomass, Other RE).
 7. Local carrier registration contract — delegations to modules
  07/08/10.
 8. CSP lock — 500 MW / 1.375 TWh / Redstone exclusion /
 fallback policy /
 storage-hour metadata preservation.
 9. Biomass policy — module 08 owns 2023-active decision;
 default to
 other_re accounting if no separately validated 2023 biomass
 plant.
 10. Carrier case policy — lowercase snake_case for local;
 upstream casing
 preserved for upstream carriers.
 11. Cross-references — pointers to:
   - configs/za/za_2023_fixed_validation.yaml#za_local_carriers
   - data/za_audit/za_carrier_taxonomy.csv
   - Module 04 audit CSVs that justify each row
   - Acceptance-gate smoke-test script
 9. Acceptance smoke-test code block — verbatim assertions from
 plan
 §Acceptance Gates lines 96–101.

 Step 4 — Machine-readable taxonomy CSV

 New generated file: data/za_audit/za_carrier_taxonomy.csv.

 Schema (one row per carrier):

 carrier_name, source_concept, treatment, component, is_local,
 color, nice_name,
 profile_intent, emissions_intent, validation_target,
 availability_treatment,
 owning_modules, notes

 Rows: all 15 RSA → V1 mappings from the taxonomy table.
 is_local=true for
 the 5 local carriers; false for upstream carriers.
 owning_modules is a
 pipe-separated list (e.g. 05|07|10).

 Step 5 — Generator script

 New file: scripts/build_za_carrier_taxonomy.py. Pattern mirrors
 scripts/build_za_source_audits.py:

 - Dual-mode: CLI (argparse --configfile) and Snakemake
 (globals().get("snakemake")).
 - Reads za_local_carriers + za_system_boundary from config.
 - Hand-codes the 15-row RSA→V1 mapping (mapping itself is the
 lock).
 - Writes data/za_audit/za_carrier_taxonomy.csv.
 - Cross-checks against Module 04 fixed_tech candidates: every
 distinct
 Carrier value in
 pypsa_rsa_fixed_technologies_2023_candidates.csv must
 map to exactly one V1 carrier; emit
 data/za_audit/za_carrier_taxonomy_crosscheck.csv with
 (rsa_carrier, count_in_audit, mapped_v1_carrier, status).
 - Appends rows to data/za_audit/source_hashes.csv and
 data/za_audit/input_file_manifest.csv.

 Step 6 — Snakemake rule

 Snakefile: add rule build_za_carrier_taxonomy before rule
 clean.

 rule build_za_carrier_taxonomy:
     input:
         config="configs/za/za_2023_fixed_validation.yaml",
         registry="data/za_audit/pypsa_rsa_source_registry.csv",
         fixed_tech="data/za_audit/pypsa_rsa_fixed_technologies_
 2023_candidates.csv",
     output:
         taxonomy_csv="data/za_audit/za_carrier_taxonomy.csv",
         crosscheck_csv="data/za_audit/za_carrier_taxonomy_cross
 check.csv",
     log: "logs/build_za_carrier_taxonomy.log"
     script: "scripts/build_za_carrier_taxonomy.py"

 doc/za_carrier_taxonomy.md is hand-written canonical doc, not a
  Snakemake
 output.

 Step 7 — Forward-looking smoke-test script

 New file: scripts/za_validation/smoke_carrier_taxonomy.py.

 Usage:
 python scripts/za_validation/smoke_carrier_taxonomy.py
 path/to/network.nc
 Exit codes: 0 pass, 1 assertion failed, 2 network missing
 (skip).

 Assertions (verbatim from plan §Acceptance Gates):

 assert "csp" in n.carriers.index
 assert n.generators.query("carrier=='csp'").p_nom.sum() > 400
 # MW
 assert "solar" in n.carriers.index
 assert n.generators.query("carrier=='solar'").p_nom.sum() >
 5000  # MW
 # CSP and solar must be distinct non-zero carriers; CSP must
 never merge into solar.

 Exit-2 path lets the script be wired into CI now and only fire
 after module 10
 produces a network.

 Step 8 — Notebook + HTML export

 New: notebooks/za_validation/05_carrier_taxonomy/carrier_taxono
 my_overview.ipynb.

 Pattern mirrors notebooks/za_validation/04_source_audits/source
 _audit_overview.ipynb.

 Sections:

 1. Read data/za_audit/za_carrier_taxonomy.csv → render full
 table.
 2. Render za_carrier_taxonomy_crosscheck.csv and assert all RSA
  carriers
 resolve.
 3. Read config za_local_carriers + za_system_boundary blocks →
 display.
 4. Cross-reference with Module 04 fixed_tech: bar chart of MW
 by V1 carrier
 (from pypsa_rsa_fixed_technologies_2023_candidates.csv filtered
  to
 included_2023=true).
 5. CSP lock check: confirm 500 MW / 1.375 TWh anchors are in
 config.
 6. Biomass policy: surface count of 2023-active biomass rows in
  audit; if
 zero, confirm other_re fallback applies.
 7. Acceptance gate self-check: print every gate item from plan
 lines 90–101
 and mark satisfied / pending-module-10.

 Export HTML via jupyter nbconvert to
 doc/za_validation/figures/05_carrier_taxonomy/carrier_taxonomy_
 overview.html.

 Step 9 — Provenance and impl log

 - Append "Module 05" section to doc/za_data_provenance.md with
 hash table
 for: doc/za_carrier_taxonomy.md, taxonomy CSV, crosscheck CSV,
 notebook,
 HTML, smoke-test script.
 - Append "Module 05" entry to doc/za_implementation_log.md per
 AGENTS.md
 schema (Status, Decisions, Deviations, Source inputs, Output
 artifacts,
 Verification, Open follow-ups). Mark CSP/solar smoke-test gate
 as
 pending module 10; all other gates satisfied.

 Step 10 — Vault-side updates

 - Shared log: 5-logs/shared/2026-05-08-XXXX-implement-pypsa-ear
 th-calibration-module-05.md
 - User log:   5-logs/users/nylan-ramnauth/2026-05-08-XXXX-imple
 ment-pypsa-earth-calibration-module-05.md
 - _status.md: pypsa-earth row "modules 00–04" → "modules
 00–05"; next gate
 → "Calibration Plan module 06 (demand, import/export, model
 inputs)".
 - _todo.md: append partial-update line under pypsa-earth P0
 task:
 Claude (Opus) implemented Calibration Plan module 05 on
 2026-05-08; next session starts module 06.

 ---
 Acceptance gates (verbatim from plan lines 89–101)

 Claude must self-check every bullet from
 doc/active/calibration-plan/05_system_boundary_and_carrier_taxo
 nomy.md lines
 89–101 before declaring module 05 complete:

 - Carrier taxonomy table written to doc/za_carrier_taxonomy.md.
 - All local carriers have cost/emissions/reporting treatment
 delegated
 to module 07 (delegation lines present in taxonomy doc and
 config block).
 - Imports/exports and embedded PV treatment documented in
 za_system_boundary block + taxonomy doc.
 - CSP cannot normalize as PV in the planned custom plant smoke
 (CSP +
 solar are separate carriers in config and in 5-row
 local-carrier block).
 - [pending module 10] Smoke-test assertions:
 assert "csp" in n.carriers.index assert
 n.generators.query("carrier=='csp'").p_nom.sum() > 400 assert
 "solar" in n.carriers.index assert
 n.generators.query("carrier=='solar'").p_nom.sum() > 5000
 Script shipped at
 scripts/za_validation/smoke_carrier_taxonomy.py;
 fires when module 10 produces a network.

 Failing acceptance items must either be fixed before merging or
  recorded as
 explicit deviations in the impl log.

 ---
 Verification

 Inside pypsa-earth repo, env pypsa-earth:

 1. python scripts/build_za_carrier_taxonomy.py --configfile
 configs/za/za_2023_fixed_validation.yaml
 2. snakemake --configfile
 configs/za/za_2023_fixed_validation.yaml --dry-run
 build_za_carrier_taxonomy
 3. snakemake --configfile
 configs/za/za_2023_fixed_validation.yaml
 build_za_carrier_taxonomy
 4. Spot-check: wc -l data/za_audit/za_carrier_taxonomy.csv ≥ 16
  lines (header + 15 rows).
 5. Spot-check: python -c "import pandas as pd; df=pd.read_csv('
 data/za_audit/za_carrier_taxonomy_crosscheck.csv'); assert
 (df['status']=='resolved').all()"
 6. Smoke-test runs with no network (exit 2):
 python scripts/za_validation/smoke_carrier_taxonomy.py
 /nonexistent.nc; echo $? → 2
 7. Notebook execute + HTML export:
 jupyter nbconvert --to notebook --execute notebooks/za_validati
 on/05_carrier_taxonomy/carrier_taxonomy_overview.ipynb --output
  carrier_taxonomy_overview.executed.ipynb
 then
 jupyter nbconvert --to html notebooks/za_validation/05_carrier_
 taxonomy/carrier_taxonomy_overview.ipynb --output
 ../../../doc/za_validation/figures/05_carrier_taxonomy/carrier_
 taxonomy_overview.html.
 8. Re-run snakemake --configfile
 configs/za/za_2023_fixed_validation.yaml --dry-run and confirm
 DAG resolves end-to-end (modules 00–05 all up to date).

 Module 05 is doc/config/spec — no solve, no model build. The
 CSP/solar
 network smoke test fires when module 10 lands.

 ---
 Critical files reference (for Claude)

 To create:
 - doc/za_carrier_taxonomy.md — canonical taxonomy doc
 - data/za_audit/za_carrier_taxonomy.csv — generated mirror
 - data/za_audit/za_carrier_taxonomy_crosscheck.csv —
 RSA-carrier resolution check
 - scripts/build_za_carrier_taxonomy.py — generator
 - scripts/za_validation/smoke_carrier_taxonomy.py — deferred
 smoke test
 - notebooks/za_validation/05_carrier_taxonomy/carrier_taxonomy_
 overview.ipynb
 - doc/za_validation/figures/05_carrier_taxonomy/carrier_taxonom
 y_overview.html
 - 5-logs/shared/2026-05-08-XXXX-implement-pypsa-earth-calibrati
 on-module-05.md
 - 5-logs/users/nylan-ramnauth/2026-05-08-XXXX-implement-pypsa-e
 arth-calibration-module-05.md

 To modify:
 - configs/za/za_2023_fixed_validation.yaml — add
 za_system_boundary + za_local_carriers; lock
 electricity.{conventional,renewable,extendable}_carriers
 - Snakefile — add rule build_za_carrier_taxonomy
 - doc/za_implementation_log.md — append Module 05 entry
 - doc/za_data_provenance.md — append Module 05 hash table
 - data/za_audit/source_hashes.csv — append rows
 - data/za_audit/input_file_manifest.csv — append rows
 - _status.md — pypsa-earth row + next-gate line
 - _todo.md — partial-update line

 Pattern files (read-only references):
 - Plan: doc/active/calibration-plan/05_system_boundary_and_carr
 ier_taxonomy.md
 - AGENTS protocol: AGENTS.md
 - Comments override: 6-codebases/Plans/Calibration
 Plan/90_Comments_Questions.md §#
 05_system_boundary_and_carrier_taxonomy (= "None")
 - Module 04 master script: scripts/build_za_source_audits.py
 - Module 04 helper package: scripts/za_audits/
 - Module 04 notebook: notebooks/za_validation/04_source_audits/
 source_audit_overview.ipynb
 - Module 04 audit CSVs: data/za_audit/pypsa_rsa_*.csv,
 especially
 pypsa_rsa_fixed_technologies_2023_candidates.csv,
 pypsa_rsa_eskom_pu_profiles_audit.csv,
 pypsa_rsa_cost_fuel_emissions_audit.csv.
 - Existing config: configs/za/za_2023_fixed_validation.yaml
 (preserve all
 Module 00–04 keys when adding new blocks).
 - Upstream defaults: config.default.yaml lines 190–235 (carrier
  blocks),
 880–1115 (plotting/colors/nice_names).
 - add_electricity.py lines 101–112
 (_add_missing_carriers_from_costs) — pattern module 10's hook
 will follow.