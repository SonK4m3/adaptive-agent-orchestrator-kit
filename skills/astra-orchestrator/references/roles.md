# Concrete Codex roles

For coding execution, apply the [DeepSeek-first routing policy](deepseek-first.md) first. The Codex roles, capability examples and topology diagrams below describe planning or Codex fallback; they do not override the coding route or existing model pins.

Source inspected: upstream profiles/pro/codex/config.toml, profiles/pro/codex/agents/{explorer,worker,tester,reviewer,researcher}.toml and profiles/pro/agents/skills/astra-orchestrator/SKILL.md on 2026-10-01. See kit ATTRIBUTION.md.

Upstream files use name, description, model, model_reasoning_effort, sandbox_mode and developer_instructions. This kit follows that format. Namespaced roles avoid colliding with existing explorer/worker definitions. From the source checkout or extracted kit package root, run `python scripts/manage.py install --parts roles`; scripts/manage.py is package tooling, not part of this installed skill. Copying SKILL.md alone does not register TOML roles. Start a fresh session and inspect the exposed agent types before using them.

| Agent type | Assignment | Model / effort | Permissions and boundaries |
| --- | --- | --- | --- |
| ao_explorer | Locate files, trace data/control flow | gpt-6-luna / high | Read-only; evidence for one bounded question |
| ao_researcher | Current API/version/source facts | gpt-6-luna / high | Read-only; primary sources and date/version |
| ao_worker | Clear implementation | gpt-6-luna / high | Workspace writes; assigned files and acceptance only |
| ao_worker_complex | Multi-step feature or cross-file logic | gpt-6.1-sol / medium | Workspace writes; agreed interfaces and exclusive ownership |
| ao_worker_critical | Difficult critical-path fix | gpt-6-astra / medium | Workspace writes; explicit scope, no implied speed guarantee |
| ao_tester | Reproduce and verify | gpt-6-luna / high | Workspace writes for test artifacts; edit tests only when assigned, no production edits |
| ao_reviewer | Independent material defect review | gpt-6-astra / low | Read-only; inspect actual diff, requirements and tests |
| ao_design_advisor | Bounded architecture tradeoff | gpt-6-astra / medium | Read-only; proposals only, root decides |
| ao_deepseek_worker | One bounded external task through DeepSeek Harness (`dsh`) | gpt-6-luna / medium (Codex bridge); DSH model selected by its runtime | Defaults to DSH read-only; workspace writes require explicit file ownership and parent authorization |

`ao_deepseek_worker` is an optional Codex bridge role, not a native DeepSeek model or Codex MCP server. It synchronously invokes `dsh --profile headless --json -`, waits for completion, and returns the final answer plus exit status, elapsed time, session ID and permission mode; intermediate reasoning/events are suppressed. DSH sees the delegated prompt and any repository files it reads. Never include secrets. Its workspace-write mode is workspace-wide, not OS-enforced per-file ownership; root must inspect the diff and verify acceptance. The role is useful for bounded independent investigation or explicitly assigned implementation, not for work needing Codex-native thread controls or interactive approvals.

These are initial settings derived from official capability guidance and upstream role boundaries, not a measured ranking. Validate model availability on the actual account. TOML pins are binding for these named roles; to choose a different effort/model use an authorized unpinned/default agent with an equivalent bounded contract where supported, or deliberately edit the role between sessions. Do not claim that a conflicting spawn override wins.

## Case mapping

| Case | Starting team | Root contribution |
| --- | --- | --- |
| Small label or known one-condition bug | L0, no child | Edit and targeted check |
| Unknown cache bug | L1 ao_explorer | Reproduction and evidence reconciliation, then assign one fix owner |
| Code + external API uncertainty | L2 ao_explorer + ao_researcher | Resolve compatibility and implementation direction |
| Two feature slices | L2 two ao_worker or ao_worker_complex instances | Freeze contract, integrate, verify boundary |
| Auth/migration refactor | L3 selected explorer, workers, tester, reviewer in stages | Own invariants and final integration |
| Difficult deadline-critical fix | ao_worker_critical only if useful; independent helper as needed | Keep critical path moving, reserve verification time |
| Flexible deadline and clear task | ao_worker, escalate on evidence | Preserve same acceptance bar |

## Spawn contract example

When the current tool exposes agent_type and message, use its actual schema:

```json
{
  "agent_type": "ao_worker_complex",
  "message": "Task name: api_validation. Implement R2 in src/api/validation.ts only. Preserve the agreed schema and existing callers. Do not edit other worker files or add dependencies. Run the targeted validation tests. Return changed paths, exact results and uncovered cases. Report a new interface decision to root."
}
```

Task name in the message is descriptive; do not invent a tool name parameter. Store the returned agent ID. Spawn another agent before waiting only when its work is independent. Use the runtime's send/wait/close tools with actual IDs. A diagram is not evidence of successful spawning.

## Limits

- Profile capacity is a configured limit, not an observed concurrency guarantee. Inspect the selected runtime/profile; staged agents are not simultaneous agents. Zero children is valid.
- Per-agent write ownership, deadline checkpoints, evidence requirements and no recursive delegation are prompt contracts, not OS isolation or hard billing controls.
- sandbox_mode constrains supported shell operations; tool permissions and the parent's authority still apply. Read-only agents may need a parent/tester for commands that create caches.
- This kit does not implement per-agent token/dollar termination. Hard cost feasibility needs observable usage and an enforcement mechanism; otherwise report it unresolved.
- No child changes overall scope, grants permissions or deploys merely because its model is stronger.
