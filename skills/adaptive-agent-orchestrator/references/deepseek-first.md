# Model Routing & Delegation Policy

## Purpose and ownership

Optimize for accepted correctness first, completion time second, and token/cost third. Choose topology from the task's dependencies, uncertainty, risk, verification needs, and available execution paths. Never optimize for agent count. Root owns scope, architecture decisions, integration, review of the actual diff, and final acceptance regardless of its configured model.

## Routing order

Apply these checks in order:

1. **Constraints and execution capability:** honor privacy, user and repository constraints; verify that the selected worker and workspace can perform the required operation. Requested permission is not proof of effective permission.
2. **Task clarity:** ensure the objective, owned paths, constraints, and acceptance checks are concrete enough for the next workstream. If missing context could change the solution, explore first.
3. **Risk:** decide whether architecture reasoning, specialist input, or independent review is needed before or after implementation.
4. **Delegation benefit:** compare parallel or external work with root execution, including setup, handoff, and verification overhead.

Root may implement directly when work is tiny or tightly coupled, external sharing is unsuitable, or delegation does not add value. For suitable implementation delegation, DeepSeek Harness is the default worker through the existing `scripts/deepseek_worker.py` wrapper. Root may invoke it directly; no Luna supervisor or minimum Codex subagent count is required. Do not dispatch DeepSeek merely to test a route already known to be unavailable or incompatible.

## Work topology and specialists

- **L0:** root only, including direct tool use where appropriate.
- **L1:** root plus one useful worker or specialist. A direct DeepSeek wrapper invocation is a delegated workstream even when no Codex subagent is spawned.
- **L2:** two or more independent workstreams whose separate outputs reduce time or risk.
- **L3:** staged or parallel work for material cross-system complexity, dependency chains, or high-risk verification.

Topology level describes coordinated workstreams, not Codex subagent count. No minimum number of agents is required. Split larger implementation into bounded tasks with explicit acceptance; execute dependent DeepSeek tasks sequentially, review each handoff before the next writer, and parallelize only independent work with exclusive write ownership.

Use Luna Explorer when code structure, behavior, or a reproduction is unclear and resolving it can change the implementation. Use Luna Researcher for version-sensitive external facts that need current primary sources. Use Astra for consequential architecture decisions or independent review when risk warrants it. These roles are demand-driven: do not repeat exploration already completed or add a specialist without a distinct output.

## DeepSeek execution and fallback

Before dispatch, state the task contract, exclusive write scope, cwd/worktree, requested permission, and independent acceptance checks. Send only relevant non-sensitive context. Keep the active repository or selected worktree as the wrapper cwd; the wrapper has no `--cwd` or session-resume option. Confirm the actual cwd and Git root. The DSH session or tool cwd can differ from the intended file target, so verify both.

### Existing wrapper interface

Read the selected `scripts/deepseek_worker.py --help` and implementation before building a command. Resolve the wrapper from the active checkout first, then `<CODEX_HOME>/scripts/deepseek_worker.py` (default `<USERPROFILE>/.codex/scripts/deepseek_worker.py`); resolve it to an absolute path before changing cwd. A fixture or disposable workspace uses its own cwd. Send the task as UTF-8 on stdin; never interpolate task text into shell source. The supported flags are `--permission-mode read-only|workspace-write`, `--timeout-seconds 1..600`, `--max-stdout-bytes`, and `--max-stderr-bytes`. Read-only is the default. Select workspace-write only for an explicitly authorized implementation contract with exclusive ownership.

The wrapper starts `dsh --profile headless --json -` in the caller's current directory and emits one JSON report. Record the wrapper's exit code separately from the child's `exit_code`. `status=completed` and a final answer indicate session completion, not accepted implementation. Keep requested permission separate from `effective_permission_mode=null` and `permission_verification=unverified`; the wrapper cannot prove DSH enforced its requested mode. Session IDs are correlation evidence, not proof of model identity or isolation. Do not forward raw stderr or reasoning.

Classify failures separately:

- **Provider availability:** a confirmed transient such as `server is busy` may receive at most one bounded retry when time remains, the worker has stopped, cleanup is clean, and no unsafe partial diff exists.
- **Workspace or sandbox incompatibility:** a confirmed ACL/path failure is an execution constraint, not a model-quality failure. Do not retry the same known-incompatible workspace. In particular, the observed Windows `grantWrite(...D:\Web\adaptive-agent-orchestrator-kit)` failure must route to Codex fallback or a separately selected workspace whose write capability is already evidenced; a user-profile worktree is a candidate, not automatic infrastructure. Never disable sandbox restrictions.
- **Unknown timeout, protocol failure, or runtime error:** treat as execution unavailable/unknown. Inspect partial changes and process cleanup; retry only if a bounded attempt is justified by new evidence. Do not bypass the wrapper to resume a session.
- **Acceptance failure after completed execution:** treat as implementation quality. Root reviews the diff and tests. If the same DSH session can safely accept one focused correction through the supported interface, request one; otherwise hand off to a Codex writer.

When falling back, select an available writable Codex role by its actual configured model/effort, task capability, and permissions. Do not infer model family from a role name or assume root is Astra. Keep the same acceptance bar and pass only context needed to continue; do not repeat completed exploration. Preserve all model configuration.

Before any retry or writer handoff, confirm the prior worker/process tree has stopped, `cleanup_errors` is empty, inspect partial changes, and establish exclusive ownership. If cleanup or ownership is unresolved, do not start another writer on those paths.

## Independent acceptance

Root checks the actual diff, including untracked files, confirms changed paths stay within scope, and runs the requested acceptance checks independently. A completed wrapper status or worker claim does not establish correctness. Report requested and effective permissions separately; until independently verified, retain `effective_permission_mode: null` and `permission_verification: unverified`. Record model pins separately from runtime-confirmed model identity.

## Routing contract

```json
{
  "default_implementation_worker": "deepseek",
  "routing_order": ["constraints_and_execution_capability", "task_clarity", "risk", "delegation_benefit"],
  "root_direct_when": ["tiny_or_tightly_coupled", "external_sharing_unsuitable", "delegation_has_no_net_benefit"],
  "specialists": {"exploration_or_current_research": "luna_on_demand", "architecture_or_independent_review": "astra_on_demand"},
  "minimum_codex_subagents": 0,
  "provider_availability_retries": 1,
  "retry_timeout_seconds": 60,
  "retry_known_incompatible_workspace": false,
  "handoff_requires": ["owned_processes_stopped", "cleanup_errors_empty", "diff_reviewed"],
  "verification_owner": "codex"
}
```
