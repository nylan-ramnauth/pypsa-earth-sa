# South Africa Agent Start Prompt

Use this prompt to start a new Claude or Codex session on branch
`za-clean-base`.

```text
We are on branch `za-clean-base` of a PyPSA-Earth fork.

Before doing anything else, read these files in order:
1. `AGENTS.md`
2. `doc/za_next_agent_handoff.md`
3. `doc/za_clean_rebuild_roadmap.md`
4. `doc/za_clean_rebuild_concepts.csv`

Important rules:
- Do not inspect previous branches or archived old work.
- Do not reuse or port previous South Africa code.
- Use only current upstream PyPSA-Earth conventions and the clean-room roadmap.
- Keep South Africa-specific assumptions local, documented, and testable.
- Do not modify global upstream defaults unless it is a small generic robustness fix.

Your task is to start with Milestone 1:
- create a clean South Africa baseline config,
- create a South Africa input-data contract document,
- define a lightweight short-snapshot smoke-test command.

First, inspect the repo and produce a concrete implementation plan for Milestone 1. Then implement it.
```

Short version:

```text
Read `AGENTS.md`, `doc/za_next_agent_handoff.md`, `doc/za_clean_rebuild_roadmap.md`, and `doc/za_clean_rebuild_concepts.csv`. Do not inspect old branches or archived code. Start with Milestone 1: clean South Africa baseline config, South Africa data-contract document, and a lightweight smoke-test command. First plan, then implement.
```
