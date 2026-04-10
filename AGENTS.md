# Agent Notes

## Branch Purpose

This branch is a clean South Africa rebuild baseline on top of upstream
PyPSA-Earth. It is intended for future thesis work, but it should begin from a
minimal, defensible South Africa model before adding reliability-aware planning.

## Clean-Room Rule

Do not inspect, copy, or port previous South Africa implementation branches or
archived experiment code. Use only current upstream PyPSA-Earth conventions and
the clean rebuild roadmap in this branch.

The roadmap source of truth is:

- `doc/za_clean_rebuild_roadmap.md`
- `doc/za_clean_rebuild_concepts.csv`

## Working Priorities

1. Implement one roadmap milestone at a time.
2. Start with the clean South Africa baseline config and input-data contract.
3. Keep South Africa-specific assumptions local, documented, and testable.
4. Do not modify global upstream defaults unless the change is a narrow generic
   fix that would be acceptable upstream.
5. Do not start reliability-index implementation until the baseline, demand
   preprocessing, and Eskom validation workflow exist.

## Verification Guidance

Full-year South Africa runs are heavy. Prefer short-snapshot smoke tests during
development. Gurobi may be used when optimization is needed.

## Git Safety

The PyPSA-Earth authors' repository should be treated as `upstream`. Do not push
to it. Future collaboration work should be pushed to a personal fork or team
remote when that remote is configured.
