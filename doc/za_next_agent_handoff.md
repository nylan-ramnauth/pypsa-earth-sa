# South Africa Handoff Summary

Date: 2026-04-11

This branch is the clean handoff branch for rebuilding the South Africa work on
top of upstream PyPSA-Earth. It is meant to be the branch a new Claude or Codex
instance sees first.

## Current Git State

- Active branch: `za-clean-base`
- Branch status when this handoff was written: one commit ahead of
  `upstream/main`
- Head commit on this branch: `7526d607` (`Prepare clean South Africa rebuild branch`)
- Upstream reference remote: `upstream`
- Upstream push URL is disabled in this checkout to avoid accidental pushes to
  the PyPSA-Earth authors' repository

There is also an archive branch:

- `cleanup-sa-base`

That branch preserves the old South Africa work, class-project artifacts,
cleanup history, and audit documents. It is not the working branch for future
implementation.

## What Has Been Done

### 1. Upstream Cleanup And Branch Preparation

- The repository was compared against upstream PyPSA-Earth and rebased onto a
  recent upstream `main`.
- The active clean branch was recreated from the latest upstream state instead
  of continuing from the experimental fork.
- The authors' remote was renamed from `origin` to `upstream`.
- Pushes to `upstream` were disabled in this local checkout.

### 2. Historical Work Preservation

The previous South Africa work was preserved on the archive branch instead of
being deleted. That preserved material includes:

- South Africa experimental configs and scripts
- class-project FBE configs, scripts, notebooks, and reports
- a saved patch representing old tracked local modifications
- cleanup and difference-audit notes

This means the old work still exists if the owner wants to inspect it later,
but it is intentionally absent from `za-clean-base`.

### 3. Clean-Room Rebuild Setup

The clean branch contains only the materials needed to rebuild from scratch:

- `AGENTS.md`
- `doc/za_clean_rebuild_roadmap.md`
- `doc/za_clean_rebuild_concepts.csv`

These are the source of truth for future implementation on this branch.

## Audit Summary

The main conclusion of the audit was:

> Do not reintroduce the old South Africa work as-is. Keep only the useful
> modelling ideas and rebuild them cleanly from current upstream PyPSA-Earth.

### Concepts Identified As Most Valuable

- A minimal South Africa baseline config built from current upstream defaults
- A South Africa input-data contract for external Eskom and reference data
- Eskom demand preprocessing as a standalone step
- Eskom generation validation as a standalone step
- Installed-capacity comparison by carrier
- EAF preprocessing before any solver integration
- Scenario-local South Africa capacity and cost assumptions
- A later spatial-allocation workflow for the future reliability index

### Concepts Marked As Later Or Optional

- Historical validation configs for 2023
- EAF integration into optimization
- fixed-demand, fixed-renewable, and fixed-trade calibration switches
- hydro and pumped-storage calibration
- demand elasticity
- reliability-aware planning scenarios

### Concepts Marked As Reference-Only Or Discarded

- FBE policy logic and subsidy accounting
- class-project scenario sweeps
- old notebooks and rendered reports as active workflow assets
- wholesale replacement of global cost tables
- global default weather-year changes
- all-in-one experimental solver patches mixing unrelated ideas

## Roadmap Summary

The rebuild roadmap is split into milestones.

### Milestone 1: Clean Baseline Skeleton

Build:

- a fresh South Africa baseline config
- a South Africa data-contract document
- a short-snapshot smoke-test command

This is the first required milestone.

### Milestone 2: Demand And Validation

Build:

- Eskom demand preprocessing
- Eskom generation validation

These are required before interpreting calibration or planning results.

### Milestone 3: Capacity And Availability Realism

Build:

- installed-capacity comparison
- EAF preprocessing
- scenario-local capacity and cost handling

### Milestone 4: Historical Validation Mode

Optionally build:

- a separate historical validation config
- explicit validation switches for fixed demand, fixed renewables, fixed trade,
  and later EAF integration if justified

### Milestone 5: Reliability-Aware Planning

Only after the previous milestones are working:

- define the reliability-index data contract
- map reliability inputs to buses or demand zones
- compare reliability-neutral and reliability-aware planning scenarios

## Instructions For The Next Agent

The next agent should work only on `za-clean-base`.

### Required Reading Order

1. `AGENTS.md`
2. `doc/za_clean_rebuild_roadmap.md`
3. `doc/za_clean_rebuild_concepts.csv`

### Working Rules

- Do not inspect or reuse previous South Africa implementation branches.
- Do not start from archived code or old patches.
- Use current upstream PyPSA-Earth conventions and APIs.
- Keep South Africa-specific assumptions local, documented, and testable.
- Do not modify global upstream defaults unless the change is a small generic
  robustness fix that would be acceptable upstream.
- Prefer short-snapshot smoke tests over full-year runs during development.

### First Task

The next agent should begin by planning and then implementing Milestone 1:

- fresh `configs/za_base.yaml`
- South Africa data-contract document
- documented lightweight smoke-test command

That work should happen before any reliability-index logic, before EAF solver
integration, and before any attempt to revive old calibration mechanics.

### Suggested Opening Prompt For The Next Agent

Use something close to:

> We are on branch `za-clean-base` of a PyPSA-Earth fork. Read `AGENTS.md`,
> `doc/za_clean_rebuild_roadmap.md`, and `doc/za_clean_rebuild_concepts.csv`
> first. Do not inspect previous branches or archived old work. Start with
> Milestone 1: create a clean South Africa baseline config and a South Africa
> input-data contract using current upstream PyPSA-Earth conventions.

## Notes For Tomorrow

- If `git branch --show-current` does not say `za-clean-base`, switch back to
  it before opening a new agent.
- If a future personal fork or team remote is created, add it as a new remote;
  keep `upstream` as fetch-only reference.
- Do not work on `cleanup-sa-base` unless you intentionally want to inspect the
  historical archive.
