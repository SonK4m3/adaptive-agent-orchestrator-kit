# Repository workflow

Preserve adaptive routing, both skill entrypoints, task-specific contracts, risk-based verification and recoverable installation. See guides/UPSTREAM-COMPARISON.md for the upstream/local boundaries.

## Skill routing

Consider orchestration automatically when independent outputs, context load or verification risk justify coordination; do not spawn agents merely because a task touches many files. Read [adaptive-agent-orchestrator](skills/adaptive-agent-orchestrator/SKILL.md), or [astra-orchestrator](skills/astra-orchestrator/SKILL.md) when explicitly selected. They expose the same policy: load one entrypoint, not both. Coding delegation follows the selected entrypoint's DeepSeek-first policy; small or tightly coupled Codex fallback tasks can stay root-only, without mandatory graph, contract files or separate reports; still report changes, checks and material limits briefly.

Root owns architecture, dependencies and integration; use one writer per path. Profile capacity never requires an agent count. Review/audit requests are read-only. Graph records are for coordination/ownership/handoff tracking or requested audits, not a default task artifact. Read supporting skill resources only when the selected workflow needs them.

For requested tracking, usage statistics or retrospective work, use task-retro-survey separately if available. Do not automatically activate survey/retro alongside orchestration; findings are proposals, not authorization to implement fixes.

Source layout: profiles/ holds resource presets and namespaced roles; skills/ holds portable self-contained entrypoints; guides/ holds user/maintainer instructions; scripts/ holds tooling; tests/ holds tooling tests; eval/ holds behavioral scenarios, rubrics, fixtures and external oracles; docs/validation/ holds reviewed evidence. Raw runs and builds belong in ignored dist/.

After changing distributed files, run python scripts/build_release.py to refresh the manifest. Run python scripts/validate_package.py and python -m unittest discover -s tests -v. Installer/package changes require an extracted ZIP lifecycle check. Do not claim runtime dispatch or cross-platform success from structural tests. Keep unrelated user edits. Commit/push only when requested.
