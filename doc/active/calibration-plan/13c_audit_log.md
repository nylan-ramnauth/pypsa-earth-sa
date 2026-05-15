# Module 13c Audit Log

**Status:** in progress  
**Owner:** nylan-ramnauth  
**Started:** 2026-05-15  
**Goal:** verify model_data_sources.md, pipeline diagram, run-scenarios.md, and
per-module acceptance gates 01–13 before Module 14 handoff.

## Quick access

| File | Purpose |
|---|---|
| [[model_data_sources]] | What is in the model and why — config, rules, data registry, toggle map, DAG |
| [[run-scenarios]] | How to reproduce every solve from scratch |
| [[za_implementation_log]] | What was done chronologically, module by module |
| [[za_model_limitations]] | What failed, accepted residuals, Module 14 fix paths |

---

## How to use

One section per document reviewed. Raise issues as numbered items.  
Tag each item:
- `[QUESTION]` — need clarification before proceeding
- `[RESOLVED]` — answered, no action needed
- `[OPEN — non-blocking]` — real issue, does not block Module 14
- `[OPEN — blocking]` — must fix before Module 14 can start

---

## Pre-audit agent findings (Opus, 2026-05-15)

Issues pre-identified by automated review before manual audit begins.
Tags applied per standard convention. Items marked `[FIXED]` were corrected
by the doc-update agent before manual review started.

### §7 — Blockers for Module 14 (must resolve before handoff)

1. `[OPEN — blocking]` **EAF scenario BASE vs HIGH_GAS contradiction.**
   `model_data_sources.md` and `model_data_sources.graph.*` say HIGH_GAS for
   `apply_za_coal_eaf`. Actual code and `za_coal_eaf_audit.csv` use BASE.
   OPC workbook uses HIGH_GAS; EAF plant_availability workbook uses BASE —
   two different workbooks, two different scenarios. Doc conflates them.

2. `[OPEN — blocking]` **Fleet row count "227" is wrong in `run-scenarios.md`.**
   Post-Sasol-removal, `custom_powerplants.csv` has 135 rows. The 227 claim
   was never updated.

3. `[OPEN — blocking]` **OCGT 5.5 TWh cap is workbook-sourced, not inline.**
   Both `model_data_sources.md` and `run-scenarios.md` say cap is "injected at
   solve time" / hardcoded; actually it is a 2026-05-13 row added to
   `operational_constraints.xlsx` in pypsa-rsa (HIGH_GAS / global /
   ocgt_diesel / output_energy / year / max / 5.5 TWh).

4. `[OPEN — blocking]` **`za_2023_uncalibrated_baseline.yaml` missing on disk.**
   Referenced by Module 11 spec and needed to reproduce
   `za_2023_uncalibrated_vs_calibrated.csv`. No such YAML in `configs/za/`.
   Baseline cannot be reproduced from current config state.

5. `[OPEN — blocking]` **3 Bioenergy rows in fleet silently dropped.**
   Joburg Landfill 7.56 MW, Ngodwana 25 MW, Sappi 144 MW = 176.56 MW.
   Present in `custom_powerplants.csv` but `biomass` is not in
   `conventional_carriers` or `renewable_carriers` → silently dropped by
   `add_electricity`. Undocumented data loss. Decision needed: remove rows,
   add carrier, or document known-omission.

6. `[OPEN — blocking]` **`za_grid_reconciliation.csv` missing 4 voltage rows.**
   Module 10 gate requires 220/275/400/765 kV back-fill; only `<220kV` row
   exists. Module 10 gate is a hard FAIL on current disk state.

7. `[OPEN — blocking]` **Module 13 acceptance is a limitations package, not a
   clean pass.** Coal +11.34%, wind −37%, solar −29%, PHS −97%, hydro −30%
   all fail carrier tolerance gates. Accepted via `doc/za_model_limitations.md`.
   Module 14 spec must explicitly state baseline is accepted-with-limitations.

8. `[OPEN — blocking]` **`run-scenarios.md` missing Module 13 validation
   orchestrator.** `scripts/za_validation/build_module13_validation.py`
   produces acceptance CSVs and manifest but is never mentioned. Fresh user
   cannot reproduce the acceptance package.

9. `[OPEN — blocking]` **`pypsa_rsa_root` is an absolute path in YAML.**
   Hardcoded to `/Users/nylan/...` in `za_2023_fixed_validation.yaml`. Fresh
   clone on any other machine fails multiple builders (Module 04 audits, EAF).

10. `[OPEN — blocking]` **`za_fixed_network_audit.csv` anchor column blank.**
    `capacity_mw_anchor` is empty for all rows; Module 11 anchor-delta gate is
    unverifiable from the CSV.

### Additional HIGH findings (from §1–§4)

11. `[OPEN — non-blocking]` **`ocgt_gas` is defined but has zero fleet capacity.**
    Carrier defined by `apply_za_local_carriers.py` with cost row, but
    `custom_powerplants.csv` has 0 Natural Gas rows (Sasol removal). Network
    shows `ocgt_gas: 0 MW, 0 generators`. `model_data_sources.md` implies
    carrier is populated. Should be documented as empty-carrier.

12. `[OPEN — non-blocking]` **PyPSA-RSA pin discrepancy between audit-time and
    solve-time.** `za_runtime_preflight.csv` records `89872c1e…` (Module 04 pin);
    YAML and `model_data_sources.md` Section 3.8 enforce `0831ce24…` (Module 12
    pin). Both are valid at their respective stages but the audit CSV is stale
    post-Module 12.

13. `[OPEN — non-blocking]` **Ingula storage hours inconsistent across docs.**
    Module 08 spec: "~12–15 h"; `model_data_sources.md` Section 3.3: "21 h";
    `custom_powerplants.csv`: 20.69 h (27,400 MWh / 1,324 MW). Three different
    values — CSV is authoritative.

14. `[OPEN — non-blocking]` **`other_re` intentionally dropped but Module 06
    spec never updated.** Module 06 spec says `other_re` is attached as 50.58 MW
    Generator; Module 12 decision removed it. `scripts/apply_za_local_carriers.py`
    comment documents this. Spec violation is intentional but spec is stale.

15. `[OPEN — non-blocking]` **STOCK config mixes 2023 RE capacity with 2030
    costs.** `za_2023_stock_baseline.yaml` sets
    `estimate_renewable_capacities.year: 2023` with IRENA scaling but costs year
    remains 2030. Module 13b and run-scenarios do not flag this.

16. `[OPEN — non-blocking]` **OCGT cap 5.5 TWh is 5% above Eskom 2023 actuals
    (5.243 TWh).** Model returns exactly 5.500 TWh (binds at cap). Calibration
    by construction, not by physics. Should be stated explicitly in limitations.

17. `[OPEN — blocking]` **Advanced CSP topology over-creates internal CSP buses.**
    Direct inspection of
    `results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H.nc`
    shows 68 total PyPSA `Bus` rows: 34 `AC` electrical planning/load buses and
    34 `csp` carrier buses. The advanced CSP representation is physically
    defensible because PyPSA models CSP as `Generator -> csp Bus/Store -> Link
    -> AC Bus`, preserving thermal-storage dispatch structure. Demand is not
    assigned to CSP buses: the solved network has 34 `Load` rows, all attached
    to `AC` buses; annual `Load.p_set` on CSP buses is 0 MWh. However, the
    current topology creates CSP internal buses for every clustered region even
    though `custom_powerplants.csv` has commissioned CSP only at Kalahari
    (100 MW), Kimberley (200 MW), and Namaqualand (200 MW). The other 31 CSP
    buses/links/stores/generators are zero-capacity placeholders. This is
    probably inert for fixed 2023 dispatch, but it confuses component counts and
    creates an unclear candidate set for Module 14 expansion. Preferred policy:
    keep advanced CSP, but create CSP internal buses only where CSP exists in
    the fixed baseline and only where CSP is explicitly eligible in expansion
    runs. CSP expansion must not inherit an all-34-region candidate set unless
    that siting assumption is explicitly defended.

---

## model_data_sources.md

### Issues / Questions

#### Section 1 - Config Delta

1. `[QUESTION]` **Stock PyPSA-Earth defaults not yet ported or reviewed.**
   Are there stock PyPSA-Earth defaults that we have not touched but that could
   improve calibration or model defensibility?

   Sub-questions:
   - Do we use the Natura raster in this model? It is supposed to avoid building
     powerplants in unauthorized/protected areas.
   - Do we use or override PyPSA-Earth uncertainty settings? If not, should this
     remain out of scope for the fixed validation baseline?
   - Was the discount rate changed? Whether changed or not, does it only affect
     expansion/capex annualization, or does it also affect fixed dispatch?
   - Could/should we copy PyPSA-RSA emission prices into the ZA overlay?

   Answer: `[RESOLVED]` Stock uncertainty is inactive, discount rate is inherited
   and mainly affects annualized capex, and emission prices only apply with `Ep`
   options not used in the ZA run. Natura is present for stock renewable
   exclusions, but fixed 2023 capacities are not expansion-sited. Do not port
   PyPSA-RSA emission prices into fixed validation; defer to policy/expansion
   scenarios.

2. `[QUESTION]` **CRS and spatial geometry choices.**
   Are our CRS, clustering, and custom-shape choices defensible relative to
   PyPSA-RSA and stock PyPSA-Earth?

   Sub-questions:
   - Do we use PyPSA-RSA's CRS? PyPSA-RSA uses
     `distance_crs: EPSG:2049`, which may be more accurate for South Africa.
     I do not think we modified or overrode the PyPSA-Earth distance CRS.
   - Why not use `alternative_clustering` with GADM shapes?
   - Why not use something like `gadm_layer_id: 2`?
   - Could/should we use the `subregion` block with `path_custom_shapes` for
     Eskom local areas instead of the current custom busmap path?

   Answer: `[OPEN — non-blocking]` The ZA overlay does not port PyPSA-RSA
   `EPSG:2049`; it inherits PyPSA-Earth `EPSG:3857`. This is defensible for
   fixed validation because the key spatial choice is the 34-region Eskom custom
   busmap. Review `EPSG:2049` before Module 14 expansion/siting.

3. `[QUESTION]` **Demand year and demand spatial allocation.**
   Are the demand year and load-disaggregation assumptions correct?

   Sub-questions:
   - Why do we use `load_options.prediction_year: 2030` even though we calibrate
     the model to 2023 first?
   - Where does `prediction_year: 2030` affect the current model?
   - PyPSA-RSA uses `load_disaggregation: "GVA_2016"` to disaggregate load
     according to supply region. What is `GVA_2016`?
   - Should any PyPSA-RSA load-disaggregation method be ported, or is the
     current PyPSA-Earth-style GDP/population allocation sufficient?

   Answer: `[RESOLVED]` `prediction_year: 2030` is mainly a path key for the
   GEGIS-compatible demand slot; actual demand is Eskom 2023. PyPSA-RSA
   `GVA_2016` means 2016 gross-value-added load weighting. V1 uses
   PyPSA-Earth-style `0.6*gdp + 0.4*pop`, with RSA GVA/POP diagnostic only.

4. `[QUESTION]` **VoLL / CoLS / load-shedding cost policy.**
   Is the current separation between solver load-shedding penalty and policy
   CoLS values correct?

   Sub-questions:
   - Do we use the `za_cols_policy` block in our runs?
   - If not, how do we activate it?
   - Is `za_cols_policy` supposed to override the solver VoLL / load-shedding
     penalty?
   - PyPSA-RSA has `voll_share: false # share of VoLL in demand`. What does this
     feature do, and is it relevant for us?

   Answer: `[OPEN — blocking]` `za_cols_policy` is reporting-only and should not
   override solver VoLL. Current YAML sets `solving.options.load_shedding: true`,
   which becomes only `1000 EUR/MWh` in `solve_network.py`. That is likely below
   the intended upstream safety-valve value and needs fixing/decision.

5. `[QUESTION]` **Transmission voltage and line-parameter configuration.**
   Are voltage and line-capacity assumptions correctly ported from PyPSA-RSA?

   Sub-questions:
   - Why do we not simply override `electricity.base_voltage` and
     `electricity.voltages`?
   - PyPSA-RSA uses a 400 kV base voltage. I see no equivalent override in the
     ZA config overlay. Is this an issue?
   - How does `za_grid_spatial` override or interact with the `lines` block of
     the main PyPSA-Earth config file?
   - How were the unmatched 275/400 kV corridors identified?
   - Why do we add those unmatched 275/400 kV corridors?

   Answer: `[RESOLVED]` The model intentionally does not override
   `electricity.base_voltage` / `voltages`. Instead, `za_grid_spatial` ports
   PyPSA-RSA voltage-specific thermal/SIL/St Clair assumptions and custom lines
   add missing 275/400 kV corridors. Those corridors avoid missing material
   interregional transfer paths.

6. `[QUESTION]` **Operational reserves and reserve margins.**
   Should PyPSA-RSA reserve logic be ported?

   Sub-questions:
   - I see no override of the `operational_reserve` block from
     `config.default.yaml`.
   - PyPSA-RSA has `operating_reserve_carriers`.
   - PyPSA-RSA also has `reserve_margins.xlsx`.
   - Should any of these be used in the fixed validation baseline or deferred to
     expansion/reliability scenarios?

   Answer: `[RESOLVED]` Do not port PyPSA-RSA reserve logic into fixed
   validation. PyPSA-Earth operational reserves are inactive, and RSA reserve
   margins are capacity adequacy/expansion constraints, not 2023 dispatch
   calibration inputs. Keep for later expansion/reliability review.

7. `[QUESTION]` **Availability / outage modeling and EAF year behavior.**
   How should PyPSA-RSA availability logic map into this PyPSA-Earth baseline?

   Sub-questions:
   - If I change the year for the EAF constraints, will the model use EAF
     constraints from another year, or is it fixed to 2023/BASE rows?
   - PyPSA-RSA uses `share_partial_outages: coal: 0.5`. What does this do?
   - PyPSA-RSA uses `implement_availability: True`. What does this do?
   - PyPSA-RSA uses:
     `adjust_by_p_max_pu: coal: [ramp_limit_up, ramp_limit_down]; nuclear:
     [ramp_limit_up, ramp_limit_down]`. What does this do?
   - PyPSA-RSA uses `clean_pu_profiles: true`. What does this do?
   - PyPSA-RSA uses `min_ramp_limit_threshold: 0.05`. What does this do?
   - Should any of these availability/ramping features be implemented here?

   Answer: `[RESOLVED]` The EAF overlay is fixed to PyPSA-RSA
   `plant_availability.xlsx`, `BASE`, mapped onto 2023 snapshots. Changing model
   year alone will not select another EAF year. Broader RSA availability/ramping
   logic is not ported; only coal `p_max_pu` is implemented.

8. `[QUESTION]` **Unit commitment and CCGT representation.**
   Should PyPSA-RSA unit-commitment or CCGT-specific logic be ported?

   Sub-questions:
   - Do we use `linearised_unit_committment: ["coal"]` from PyPSA-RSA?
   - Do we use `ccgt_st_to_gt_ratio: 0.427` from PyPSA-RSA?
   - PyPSA-RSA notes that CCGTs are modeled as an OCGT plus auxiliary steam
     turbine. What does this mean?
   - Is any of this relevant given the current 2023 fleet and carrier set?

   Answer: `[RESOLVED]` Do not port RSA unit commitment or CCGT steam-turbine
   logic for the current 2023 fixed fleet. The ZA carrier set excludes
   CCGT/`ccgt_steam`, and coal UC is not enabled. It is not relevant unless the
   carrier set changes.

9. `[QUESTION]` **PyPSA-RSA renewable-generator configuration.**
   Should any part of PyPSA-RSA's `renewable_generators:` block be ported?

   Sub-questions:
   - What does `renewable_generators.apply_grouping` do?
   - What do the `resource_profiles.datasets` choices mean?
   - What are `single_node_profiles` used for?
   - What do the degradation-adjusted capacity factor settings do?
   - Which, if any, of these should be ported for Module 14 or later?

   Answer: `[OPEN — non-blocking]` Do not port PyPSA-RSA `renewable_generators`
   wholesale for fixed validation. Current model uses atlite/ERA5 profiles and
   custom fixed capacities. For Module 14, review selectively if replacing atlite
   bias with WASA/SARAH/Eskom profiles or adding degradation-adjusted CFs.



---

## Pipeline diagram (model_data_sources.graph.svg)

### Issues / Questions

*(fill during manual review)*

---

## run-scenarios.md

### Issues / Questions

*(fill during manual review — pre-audit findings above cover known gaps)*

---

## za_implementation_log.md

### Issues / Questions

*(fill during manual review)*

---

## Module-by-module gate audit (01–13)

Pre-audit gate assessment (Opus, 2026-05-15):

| Module | Title | Gate status | Notes |
|---|---|---|---|
| 01 | Repo bootstrap and config | partial | preflight CSV exists; dry-run gate not recorded as CSV |
| 02 | Eskom validation data pipeline | PASS | targets CSV tolerances pass |
| 03 | Weather cutout and profiles | partial | Gate A: PASS. Gate B (RSA profile comparison) status unclear |
| 04 | Source data audits | PASS | 22 audit CSVs + 3 GeoJSONs present |
| 05 | System boundary and carrier taxonomy | partial | taxonomy CSV exists; smoke-test assertions not run as separate gate |
| 06 | Demand, import/export model inputs | FAIL | `other_re` gate violated by intentional Module 12 removal; spec not updated |
| 07 | Costs, fuels, efficiencies, and CoUE | PASS | cost rows, fx, CoLS values verified |
| 08 | Fleet reconciliation and custom powerplants | partial | onwind capacity delta −2.02% (tol 2%) borderline FAIL; Sasol removal not in CSV |
| 09 | Grid spatial and transmission model | partial | busmap OK; MTS hosting limits application not auditable from CSVs |
| 10 | Earth–RSA baseline diagnostic | FAIL | `za_grid_reconciliation.csv` per-voltage back-fill missing |
| 11 | Fixed capacity network build | partial | extendable gate PASS; anchor-delta gate unverifiable (column blank) |
| 12 | Dispatch calibration and availability | partial | calibration CSVs exist; interim calibration report location uncertain |
| 12b | Availability provenance | PASS | EAF audit + provenance markdown present |
| 13 | Validation reporting and acceptance | PASS-with-limitations | all 12 manifest artefacts present; 6/11 carrier rows fail tolerance via documented limitations |

### Issues / Questions

*(fill during manual review)*

---

## Cross-cutting checks

Config flags, data files, and inter-module contradictions found after reviewing
all individual sections.

### Issues / Questions

1. `[OPEN — blocking]` **CSP topology and expansion candidate-set policy.**
   See pre-audit finding 17. Before Module 14, decide whether CSP expansion is:
   existing-site only, resource/siting-filtered candidate regions, or all-region
   unconstrained. The audit recommendation is resource/siting-filtered candidate
   regions for expansion, while the fixed 2023 baseline should retain only the
   three commissioned CSP internal buses.

---

## Green-light decision

- [ ] All blocking issues resolved
- [ ] Gate table complete (no `—` entries)
- [ ] `run-scenarios.md` verified reproducible
- [ ] `model_data_sources.md` fully consistent with implementation
- [ ] Pipeline diagram matches narrative

**Decision:** *(pending)*
