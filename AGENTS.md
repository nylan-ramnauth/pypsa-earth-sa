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

## Working Priorities

1. Implement one active plan module at a time.
2. Start with the clean South Africa baseline config and input-data contract.
3. Keep South Africa-specific assumptions local, documented, and testable.
4. Do not modify global upstream defaults unless the change is a narrow generic
   fix that would be acceptable upstream.
5. Do not start Workstream B reliability/myopic implementation until the
   Workstream A Module 13 handoff artifacts exist.

## Verification Guidance

Full-year South Africa runs are heavy. Prefer short-snapshot smoke tests during
development. Gurobi may be used when optimization is needed.

## Git Safety

The PyPSA-Earth authors' repository should be treated as `upstream`. Do not push
to it. Future collaboration work should be pushed to a personal fork or team
remote when that remote is configured.
