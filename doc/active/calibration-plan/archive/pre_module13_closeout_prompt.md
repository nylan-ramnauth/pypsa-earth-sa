# Agent Task — Pre-Module 13 Closeout
# Write limitations doc, update project state, write wrap-up log

**Give this file to Codex or Opus. Enter plan mode after reading.**

---

## Context

You are working inside the `pypsa-earth` codebase at:
```
/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth
```
Vault root:
```
/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault
```

Module 12 dispatch calibration is complete. Four solved networks exist for South Africa 2023.
An investigation (Sections 2–5 of `pre_module13_investigation_plan.md`) identified root causes
for all remaining calibration errors and determined that Solve 5 is not needed. Solve 4
(`EAF-OPC-CAP`) is the Module 13 accepted candidate.

All investigation findings and limitation texts are already written in:
```
doc/active/calibration-plan/pre_module13_investigation_plan.md
```
Section 11 (Investigation Output Block) of that file is the authoritative source for all
content you need to write. Read it in full before writing anything.

---

## Your Scope

Four deliverables only. Do not implement any Module 13 validation CSVs or reports — those
are Module 13 proper.

---

### Deliverable 1 — `doc/za_model_limitations.md`

Create this file. It is a Module 13 acceptance-boundary document. Structure it as follows:

```markdown
# South Africa 2023 Baseline — Model Limitations

**Module:** 12 (dispatch calibration) / Pre-Module 13 acceptance boundary
**Accepted solve:** EAF-OPC-CAP
**Network:** results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc
**Date accepted:** 2026-05-13

## 1. PHS Dispatch (−96.6%)
[write limitation text from Section 11 of pre_module13_investigation_plan.md]
[include the Module 14 expansion warning verbatim]

## 2. Wind Generation (−37.0%)
[write limitation text, include the 1.58× scaling factor as a quantified Module 14 input]

## 3. Solar PV Generation (−29.1%)
[write limitation text, include the 1.40× scaling factor]

## 4. CSP Generation (−41.4%)
[write limitation text, include the 1.71× scaling factor]

## 5. Coal Over-dispatch (+11.3%)
[write limitation — split into 56% substitution artifact + 5% genuine EAF residual]

## 6. Hydro Annual Level and Seasonality (−29.8%)
[write limitation — ERA5 inflow underestimate + seasonal inversion structural]

## 7. Load Shedding Under-estimate (−35.9%)
[write limitation — downstream of PHS/VRE gaps; do not hard-code before fixing storage]

## 8. Scarcity Timing — Calibration Claim Boundary
[write one paragraph: weekly Pearson r ≈ 0.73, monthly ≈ 0.85 for solve 4. Model
identifies broadly similar stress periods but annual carrier mix is materially wrong.
Scarcity timing is thesis-defensible as a planning-model claim only.]

## 9. Accepted Calibration Errors — Summary Table

| Carrier | Eskom GWh | Solve 4 GWh | Δ% | Diagnosis | Module 14 fix needed? |
|---|---:|---:|---:|---|---|
[populate from Section 11]
```

The content of each section must come verbatim or paraphrased from the limitation texts
in Section 11 of `pre_module13_investigation_plan.md`. Do not invent new content.

---

### Deliverable 2 — Update `_todo.md`

File location: `../../../_todo.md` (i.e., vault root `_todo.md`).

Find the active task entry:
```
- [ ] Implement pypsa-earth P0 baseline (see DEC-001 and roadmap) [owner:: Nylan] ...
```

Add a new partial update line at the end of its sub-bullets:
```
  - partial update: Pre-Module 13 investigation complete on 2026-05-13 (PHS diagnosis
    A-III-modified: LP arbitrage unprofitable, no portable fix; VRE diagnosis B-II:
    ERA5 CF bias, scale factors 1.58×/1.40×/1.71× documented as Module 14 inputs;
    Solve 5 skipped; Solve 4 EAF-OPC-CAP accepted as Module 13 candidate;
    `doc/za_model_limitations.md` written; all 6 gates pass). Next: Module 13
    validation reporting (produce za_2023_validation_*.csv + doc/za_2023_validation_report.md).
```

Do not change any other lines.

---

### Deliverable 3 — Update `_status.md`

File location: `../../../_status.md`.

Read the current file first. Find the entry for the pypsa-earth calibration workstream
(or the most relevant active status entry). Update it to reflect:
- Module 12: FUNCTIONALLY COMPLETE, calibration accepted with limitations
- Module 13 candidate: solve 4 (EAF-OPC-CAP)
- PHS and VRE documented as Module 14 input improvements
- Module 13 validation reporting is the next active task
- Pre-module 13 investigation notebook at:
  `notebooks/za_validation/12_dispatch_calibration/pre_module13_investigation.ipynb`

If `_status.md` has no existing pypsa-earth calibration entry, add a new section.

---

### Deliverable 4 — Shared wrap-up log

Write a new file:
```
5-logs/shared/2026-05-13-HHMM-pre-module13-closeout.md
```
Replace HHMM with current time.

Use this frontmatter and structure:
```yaml
---
type: shared-log
date: '2026-05-13'
time: 'HH:MM'
created: '2026-05-13'
actors:
- Nylan RAMNAUTH
workstreams:
- pypsa-earth
---
```

Body sections:
- **What Changed**: investigation complete; limitations doc written; project state updated
- **Canonical Pages Touched**: list the 3 files you wrote/edited
- **Decisions Updated**: none
- **Blockers**: PHS dispatch (Module 14 architectural fix required); VRE ERA5 CF bias
  (Module 14 cutout rebuild or CF correction required)
- **Next Actions**: begin Module 13 validation reporting — produce
  `data/za_validation/za_2023_validation_annual.csv` and
  `doc/za_2023_validation_report.md` using solve 4 as evidence base
- **Handoff Note**: Module 13 validation reporting can now start. Solve 4
  (EAF-OPC-CAP) is the accepted candidate. All calibration limitations are
  documented in `doc/za_model_limitations.md`. Do not re-open Module 12 calibration
  unless a portable PHS or VRE fix is identified.

---

## Constraints

- Read `doc/active/calibration-plan/pre_module13_investigation_plan.md` Section 11
  before writing anything — that is the single source of truth for all content
- Do not modify any `.nc` network files
- Do not modify any scripts in `scripts/`
- Do not write any Module 13 CSVs or validation reports
- Do not commit or push anything — leave that for the user
- `doc/za_model_limitations.md` must be a clean standalone file readable by an
  external reviewer who has never seen the codebase

---

## Acceptance Gates

- [ ] `doc/za_model_limitations.md` exists with all 9 sections populated
- [ ] `_todo.md` partial update line added (no other lines changed)
- [ ] `_status.md` updated to reflect Module 13 candidate and next action
- [ ] Shared wrap-up log written in `5-logs/shared/`
- [ ] No `.nc` files modified
- [ ] No CSV files in `data/` modified
