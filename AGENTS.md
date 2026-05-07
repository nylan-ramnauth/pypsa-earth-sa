# Agent Notes

## Branch Purpose

This branch is a clean South Africa rebuild baseline on top of upstream
PyPSA-Earth. It is intended for future thesis work, but it should begin from a
minimal, defensible South Africa model before adding reliability-aware planning.

## Clean-Room Rule

Do not inspect, copy, or port previous South Africa implementation branches or
archived experiment code. Use only current upstream PyPSA-Earth conventions and
the active South Africa plan documents in this branch.

The active implementation sources of truth are:

- `doc/active/calibration-plan/`
- `doc/active/reliability-plan/`

Superseded historical roadmap references:

- `doc/za_clean_rebuild_roadmap.md` [SUPERSEDED by doc/active/calibration-plan/ — kept for historical context]
- `doc/za_clean_rebuild_concepts.csv`

## Active Workstreams

Workstream A: ZA Baseline Calibration — `doc/active/calibration-plan/`
(14 modules, all frozen). This workstream builds the defensible South Africa
2023 baseline, including config overlays, data provenance, Eskom validation
inputs, fleet/grid reconciliation, fixed-capacity dispatch calibration, and the
expansion/reliability handoff artifacts.

Workstream B: Reliability/Myopic Extension — `doc/active/reliability-plan/`
(8 modules, 07 partially frozen). This workstream adds the observed-reliability
ENS planning layer and myopic electricity-only workflow after the calibrated
baseline handoff exists.

Implementation gate: Workstream B must not start until Workstream A Module 13
handoff artifacts exist and are accepted. Reliability method choices are locked
by DEC-002 in the vault decision record:
`3-wiki/decisions/2026-05-07-v1-reliability-implementation-uses-deterministic-eens-constraints.md`.
For V1, use deterministic single-shot LP with ENS caps and a slack penalty; do
not implement the full Zampara Lagrange relaxation.

## Session Start Protocol (mandatory)

At the start of every session, before writing any code:

1. Read this file (`AGENTS.md`).
2. Read `doc/za_implementation_log.md`. This is the binding record of every
   decision, deviation, and output from previous sessions. Do not start work
   without knowing what the previous session decided.
3. Read the plan module(s) you intend to implement.
4. Read `doc/active/calibration-plan/90_Comments_Questions.md` for any
   module-specific notes from the project owner that override or supplement
   the plan.

## Session End Protocol (mandatory)

Before finishing any session, append an entry to `doc/za_implementation_log.md`
using this schema:

```
## [MODULE_ID] [MODULE_NAME] — [YYYY-MM-DD HH:MM]

- **Status:** complete | partial | blocked
- **Decisions taken:** (choices not already specified in the plan)
- **Deviations from plan:** (what changed from the plan and why)
- **Source inputs used:** (file paths, commit hashes, URLs)
- **Output artifacts produced:** (file paths written or modified)
- **Open follow-ups:** (items for later modules or sessions)
```

A session with no log entry is considered incomplete.

## Implementation Log

Location: `doc/za_implementation_log.md` (this repo, root-level `doc/`).

This file is the single source of truth for implementation state across sessions.
It is append-only. Never edit or delete previous entries.
Create the file if it does not exist yet.

## Working Priorities

1. Implement one active plan module at a time.
2. Read the log before starting — do not re-implement what is already done.
3. Keep South Africa-specific assumptions local, documented, and testable.
4. Do not modify global upstream defaults unless the change is a narrow generic
   fix that would be acceptable upstream.
5. Do not start Workstream B reliability/myopic implementation until the
   Workstream A Module 13 handoff artifacts exist.

## Solver

Always use Gurobi. HiGHS is not used at any stage, including smoke tests.

Threads: `1` for parallel batches (many concurrent solves); `2` for serial runs.
License: academic named-user, version 13.0.0, expiry 2027-01-20, no WLS pool.

## Validation Notebooks

Every module that produces a validation artifact must also produce a Jupyter
notebook in `notebooks/za_validation/<module>/`. Notebooks must:
- Read from canonical CSV/netCDF outputs (no hardcoded data)
- Use PyPSA and PyPSA-Earth plotting idioms (use context7 for documentation)
- Run end-to-end without manual intervention
- Export static HTML to `doc/za_validation/figures/<module>/`

See `doc/active/calibration-plan/00_governance_and_scope.md` for the full
notebook policy and path table.

## Smoke Build Sequence

Never run the full 8760-hour solve without passing staged smokes first:
1. 7-day window (2023-07-01 → 2023-07-07) — must solve and pass gate
2. 1-month window (July 2023) — must solve and pass gate
3. Full 8760 — only after both smokes pass

## Module-Specific Notes

`doc/active/calibration-plan/90_Comments_Questions.md` contains per-module
notes and instructions from the project owner. These are binding and supplement
the plan. Read the relevant section before starting each module.

## Verification Guidance

Prefer short-snapshot smoke tests during development. Full-year runs are heavy.
Smoke test first, diagnose there, then run full year only when smoke passes.

## Git Safety

The PyPSA-Earth authors' repository should be treated as `upstream`. Do not push
to it. Future collaboration work should be pushed to a personal fork or team
remote when that remote is configured.
