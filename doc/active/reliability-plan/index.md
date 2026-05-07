# Observed-Reliability ENS Planning Source Of Truth

Status: `review-updated 2026-05-07`. Modules 00-06 have blocker fixes applied.
`07_implementation_handoff.md` is populated from repo inspection and user
answers, with freeze-only values explicitly marked `[TO BE FILLED ON FREEZE]`.

Archived source snapshot:

```text
docs/active/archive/source_snapshots/ntl_budget_constrained_ens_investment_plan.md
```

This folder is the active implementation contract after the split. The archived
snapshot is preserved for comparison only and must not be implemented from
directly.

## Modules

| Module | Responsibility |
|---|---|
| `00_overview.md` | Scope, locked V1 decisions, research framing, scenario ladder |
| `01_reliability_formulation.md` | Observation source contract, ENS targets, slack, duals, reporting interpretation |
| `02_solver_integration.md` | PyPSA/Linopy constraints, solve hook, budget, dual export, solver options |
| `03_myopic_elec_only_workflow.md` | Snakemake pathway, horizon-tagged demand/cost artifacts, custom-rule risks |
| `04_carry_forward_contract.md` | Brownfield carry-forward, component handling, transmission limits |
| `05_tests_acceptance.md` | Fixtures, dry-runs, smoke tests, acceptance gates |
| `06_reproducibility_and_scenarios.md` | Reproducibility locks, budget frontier, scenario definitions |
| `07_implementation_handoff.md` | Repo layout, version pins, external input contract, numerical defaults, concrete Snakemake stubs, day-1 bootstrap |

## Review Status

| Module | Codex status | Claude status | Open blockers | Freeze status |
|---|---|---|---|---|
| `00_overview.md` | review fixes applied | needs re-review | none | pending re-freeze after DEC-002/config-anchor review |
| `01_reliability_formulation.md` | review fixes applied | needs re-review | none | pending re-freeze after eta config/unit reconciliation review |
| `02_solver_integration.md` | agreed | agreed | none logged | frozen |
| `03_myopic_elec_only_workflow.md` | review clarification applied | agreed | none | frozen |
| `04_carry_forward_contract.md` | agreed | agreed | none logged | frozen |
| `05_tests_acceptance.md` | review clarification applied | agreed | none | frozen |
| `06_reproducibility_and_scenarios.md` | blocker resolved | needs re-review | none | pending re-freeze after configurable weather-year/budget-frontier review |
| `07_implementation_handoff.md` | repo fields populated | needs re-review | freeze commit, exact installed package versions, dual-sign fixture date | pending freeze |

## Review Protocol

Review one module at a time. If Claude or Codex finds a blocker, update only the
affected module and this status table, then re-review that module.

Implementation cannot begin until every row is:

```text
Codex status = agreed
Claude status = agreed
Freeze status = frozen
```

Recommended review order:

1. `00_overview.md`
2. `01_reliability_formulation.md`
3. `02_solver_integration.md`
4. `03_myopic_elec_only_workflow.md`
5. `04_carry_forward_contract.md`
6. `05_tests_acceptance.md`
7. `06_reproducibility_and_scenarios.md`
8. `07_implementation_handoff.md`

Generic fresh-agent review prompt:

```text
docs/active/reviews/prompts/fresh_agent_review_brief.md
```
