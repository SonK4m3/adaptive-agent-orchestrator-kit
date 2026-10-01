# Evidence-backed environment retrospective

Read the specified session's primary sources; default to the tracked task/current session. Survey events summarize activity but may miss causes: use relevant original tool results, diff, test output and session trace when available. Record inaccessible logs. Do not read credentials or unrelated team histories. Findings are proposals only.

When recording a supplied historical task, establish its repository/session before inspecting environment files. The repository hosting this survey may be unrelated to that task. If the target is unknown, leave repository_id and its guardrail coverage unknown rather than borrowing current cwd's CI or treating the survey's own actions as task execution.

Inspect the repo's actual check commands (package.json, pyproject/build tool, scripts) and CI/hooks before suggesting checks. Distinguish a missing check from an existing check that is not wired or fails silently. Absence of a guardrail is a candidate finding; verify scope and existing equivalent mechanisms first, without assuming every project needs a local hook.

| Category | Evidence to inspect | Useful proposal |
| --- | --- | --- |
| Navigation | Repeated searches, wrong entrypoints, late hidden dependencies | A specific pointer to existing docs/symbols; no full repo map unless needed |
| Automated checks | Errors in trace and existing lint/type/test/CI wiring | Wire or repair the cheapest relevant deterministic check; avoid duplicating one |
| Coding standards | Reviewer misses, actual diff, standards/docs | Mechanical violation: propose a linter/check. Judgment: clarify a reviewer rule with evidence |
| Steering instructions | Relevant AGENTS.md/CLAUDE.md, including global only when accessible and relevant | Reduce always-loaded content, link detailed docs, preserve useful behavioral rules |
| Tool economy | Repeated discovery, large outputs/context, unnecessary agents/reviews | Narrow queries/context, reuse evidence, measure proposed improvements |
| No-op instructions | Steering text plus behavior observed in trace | Remove/clarify instruction that adds no behavior; absence of observed effect alone is weak evidence |
| Information access | A blocker due to missing logs/config/status | A read-only evidence source or logs capture, with access scope identified |

Implementation carries exploration/debugging context pressure; review should receive the diff AND minimum requirements/boundary context to enforce judgment standards. A diff alone may miss architecture/security constraints. Put mechanical rules into proposed deterministic guardrails, not expanded always-loaded steering text. Review-stage standards should link existing docs before creating a new CODING_STANDARDS.md. Large standards can route to focused references rather than grow without bounds.

Order findings by impact and confidence. Explain the trigger, primary evidence, outcome and proposed remedy. Distinguish confirmed problems, hypotheses and uninspected categories. Describe the verification of a proposed improvement: same acceptance bar, comparable task/setup, before/after timing/usage only when counters permit it. Never promise credit savings from fewer tools or agents alone.

If the user later approves a change, hand it off as a new task referencing this run and its baseline. This survey never applies checks/hooks/config/docs changes, installs a writing skill, sends reports externally or updates memory.
