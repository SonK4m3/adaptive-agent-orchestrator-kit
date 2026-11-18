# DeepSeek asynchronous job lifecycle

Status: completed. Plan created 2026-11-18 (Asia/Saigon).

## Purpose / Big Picture

After this work, Codex can submit a bounded task to DeepSeek Harness (DSH), receive a durable task ID without waiting for the model to finish, inspect progress and state later, continue an interrupted DSH session with a focused follow-up, and retrieve a patch/report from a separate task workspace. Codex remains responsible for scope, review, applying changes and acceptance. The current synchronous headless wrapper remains available as a fallback.

## Progress

- [x] (2026-11-18 15:50Z) Milestone 1 — Persist task IDs, lifecycle state and bounded progress; verify reload and failure transitions.
- [x] (2026-11-18 15:55Z) Milestone 2 — Connect persisted DSH session IDs to explicit resume/follow-up and checkpoint behavior.
- [x] (2026-11-18 16:20Z) Milestone 3 — Add asynchronous MCP tools and isolated input/output workspace with a reviewable patch; integrate installer and team documentation.
- [x] (2026-11-18 16:20Z) Final gates — Build the release package, validate the package, run the complete test suite, and inspect the final diff.

## Surprises & Discoveries

- `docs/PLANS.md`, which the requested `exec-plan` skill names as its template, is absent. The repository has `docs/plans/AGENT-GRAPH-IMPROVEMENT.md`; this plan follows the skill's required sections and the repository's existing plan conventions.
- The working tree already contains uncommitted wrapper, test, role, guide, fixture and manifest changes from the preceding task. Those changes are part of the starting baseline and must be preserved; this plan does not authorize reverting or committing them.
- The current wrapper is synchronous. It has explicit `--session-id` resume and reports `session_id` only after the wrapper exits. It does not persist job state or stream progress to a supervisor.
- The optional worker installer currently copies `deepseek_worker.py` and `process_guard.py`; an MCP server and job store are not yet installed components.
- Milestone 1 added an atomic JSON metadata store under a caller-selected root (defaulting below `CODEX_HOME`) and eight offline tests. The store intentionally accepts categorical progress labels and never stores task prompts or raw logs.
- Milestone 2 adds an optional wrapper progress journal containing only event type, safe phase, session ID, final reason and timestamp. The store reader drops unknown/raw fields and ignores an incomplete final line; 28 focused tests pass across the store and wrapper.
- The MCP bridge sends task text to the existing wrapper through stdin, keeping it out of argv. It offers seven bounded tools over MCP stdio JSON-RPC, stores per-task workspaces/artifacts below the job root, and returns diffs without applying them to the source checkout.
- MCP tests use a synthetic worker and a JSON-RPC subprocess round trip; wrapper tests separately use fake DSH processes. No live DSH inference or Codex Desktop registration was performed.
- Windows lifecycle tests exposed concurrent progress/terminal-state record access. A per-store reentrant lock now serializes JSON record read-modify-write operations; the focused lifecycle suite passes.
- Codex project config supports MCP server definitions for trusted projects. The sample remains manual and machine-specific because the installer does not edit existing Codex config.

## Decision Log

- Job state is stored under `CODEX_HOME/deepseek-worker/jobs`; task IDs are UUID hex strings distinct from DSH session IDs. The store is standard-library-only, atomically replaces bounded JSON records, and quarantines corrupt records.
- A resumed attempt reuses the same task ID but appends a compact summary of its previous attempt; the original prompt remains absent from persistent metadata.
- The worker writes progress only when given a fresh absolute `--progress-file`; the existing synchronous behavior remains unchanged when this option is omitted. The journal cap is 1 MiB / 4096 events and does not include answer text, tool output, cwd or reasoning.

## Outcomes & Retrospective

Implemented durable task IDs/status/progress, explicit DSH session follow-up, async MCP stdio tools, isolated selected-input workspaces and per-attempt patch/result artifacts. The optional role installer now installs the MCP server and job-store helpers with the worker; skill aliases and team guides describe opt-in MCP with synchronous fallback. Project Codex config remains untouched.

Evidence: `python scripts/build_release.py` produced a 136-file release archive; `python scripts/validate_package.py` passed; `python -m unittest discover -s tests -v` passed 197 tests with 1 platform skip; focused MCP/job/wrapper/installer tests passed. Synthetic tests confirmed start/status/wait/result/follow-up/cancel, timeout mapping, persistence after manager restart, input filtering, patch creation and unchanged source files. No real DSH model call, runtime Codex MCP registration, or security-boundary claim was tested. The isolated task directory separates outputs; it is not an OS sandbox.

## Context and Orientation

Repository root: `D:\Web\adaptive-agent-orchestrator-kit`.

- `D:\Web\adaptive-agent-orchestrator-kit\scripts\deepseek_worker.py` invokes `dsh --profile headless --json -`, bounds output, kills its owned process tree on wrapper timeout, and returns one compact JSON report. It can pass an explicit session ID to DSH.
- `D:\Web\adaptive-agent-orchestrator-kit\scripts\process_guard.py` owns process-tree cleanup on the supported operating systems.
- `D:\Web\adaptive-agent-orchestrator-kit\profiles\adaptive\codex\agents\ao_deepseek_worker.toml` describes the optional Codex worker role and currently teaches the synchronous CLI call.
- `D:\Web\adaptive-agent-orchestrator-kit\scripts\manage.py` controls which role support scripts are installed into a Codex home. `D:\Web\adaptive-agent-orchestrator-kit\distribution.json` controls release inclusion.
- `D:\Web\adaptive-agent-orchestrator-kit\guides\DEEPSEEK-CODEX-ONBOARDING.md` and `D:\Web\adaptive-agent-orchestrator-kit\guides\INSTALLATION.md` are the user-facing setup references.
- `D:\Web\adaptive-agent-orchestrator-kit\tests\test_deepseek_worker.py`, `D:\Web\adaptive-agent-orchestrator-kit\tests\test_hybrid_delegation.py` and `D:\Web\adaptive-agent-orchestrator-kit\tests\test_manage.py` contain offline process, delegation and installer checks.

Terms used in this plan:

- **Task ID**: a bridge-generated opaque identifier for one submitted job; it is distinct from DSH's session ID.
- **Session ID**: the identifier DSH reports for its persisted conversation and accepts with `--session-id` when resuming.
- **Checkpoint**: a named, independently reviewable output boundary in the worker's instructions; it is not proof of completion until evidence is recorded.
- **MCP**: Model Context Protocol, the JSON-RPC interface Codex uses to discover and call external tools.
- **Isolated task workspace**: a persistent per-task directory populated only with explicitly selected input paths. DSH writes there; the user's source checkout is not the output destination. This is not an OS sandbox and does not prove DSH cannot access other user files.
- **Patch artifact**: a bounded diff plus a machine-readable result report saved under the bridge's job-data directory for Codex to inspect and apply explicitly.

Root owns design, implementation, integration and independent acceptance. This work is tightly coupled across process lifetime, state persistence, session resumption and MCP handoff, so it stays root-only. No model inference, paid smoke task, global Codex configuration edit, automatic patch application, commit or push is authorized by this task. MCP registration will be documented as an explicit project-local configuration step and must preserve existing user configuration.

## Plan of Work

### Milestone 1 — Durable task ledger and progress

Add a small standard-library job store used by the bridge. Each record has a generated task ID, lifecycle status, timestamps, caller workspace identity, selected input paths, requested permission mode, process state, DSH session ID when observed, checkpoint labels, bounded progress summary, completion/failure classification and artifact paths. Persist records atomically so a restarted MCP process can reload them. Do not persist API keys, environment values or the full task prompt. Tests use a temporary state root and fake processes to verify unique IDs, atomic updates, reload, invalid records, terminal states and bounded data.

**Result:** Codex can address a job by ID after the initiating tool call returns, and status is recoverable from disk without placing the full prompt or DSH transcript in the job database.

### Milestone 2 — Session resume and checkpoint follow-up

Connect live wrapper progress to the job record so the DSH session ID and status phase are persisted as soon as their events arrive, not only after process exit. Keep the existing wrapper invocation as the sole owner of DSH arguments, environment filtering, output bounds and process cleanup. A follow-up must name the prior task ID, confirm that the old process has stopped, and send a focused continuation on the same DSH session. It must not replay the original task automatically. A timeout or missing terminal report remains incomplete/unknown until inspected.

**Result:** a failed or interrupted job can be inspected and explicitly resumed when DSH retained its session; provider/runtime failure is distinguished from a Codex-side lost wait where evidence permits.

### Milestone 3 — Asynchronous MCP and isolated artifacts

Expose a minimal, documented MCP stdio server with seven tools to start a task, inspect/list jobs, wait with a bounded duration, continue a stopped task, read its result, and cancel an owned process tree. A start call returns a task ID without waiting for model completion. Progress calls return only bounded metadata, not reasoning or raw event streams. Each coding job runs from a persistent task workspace populated from caller-selected paths; credentials, `.env` files, `.git`, Codex user configuration, dependency caches and generated build directories are excluded. Collect changed and newly created files into a bounded patch/report artifact separate from the source checkout. Never apply the patch automatically. Enforce a small concurrency cap, per-call timeout and output limits, safe path resolution, and process cleanup on cancellation/shutdown.

Package and install the MCP helper only with the optional DeepSeek worker role. Document the explicit project-local `[mcp_servers]` configuration snippet and removal procedure; do not rewrite `config.toml` automatically. Update both orchestration skill aliases and the Codex role so they use asynchronous tools when configured and retain the synchronous wrapper fallback otherwise.

**Result:** Codex can start work without holding a long tool call, retrieve its status/result later, and review an isolated patch before integration.

## Concrete Steps

1. Inspect the existing wrapper API, installer component map and test conventions. Keep unrelated worktree edits intact.
2. Implement the durable job store and state-transition tests. Run `python -m unittest tests.test_deepseek_jobs -v` and require `OK`.
3. Add bounded live progress/session event reporting to the wrapper, connect it to task state, and test explicit resume, timeout, cleanup and server restart using fake DSH only. Run the focused worker/delegation tests and require `OK`.
4. Implement MCP initialize/list/call handling and seven bounded job tools. Test JSON-RPC over stdio with a subprocess client and synthetic worker, plus the wrapper's fake-DSH tests; assert the original checkout is unchanged and patch artifacts include modifications/new files while excluded secrets are absent.
5. Add the helper to optional role installation and package validation. Update role instructions, both skill aliases, onboarding and installation docs. Keep MCP server config opt-in and project-local.
6. Run `python scripts/build_release.py`, `python scripts/validate_package.py`, `python -m unittest discover -s tests -v`, and `git diff --check`. Inspect the generated ZIP with the existing extracted-package lifecycle test.
7. Review the full diff and report each acceptance result, exact commands, runtime limitations and the no-model-call boundary. Preserve all changes in the working tree; repository instructions prohibit commits unless explicitly requested.

## Validation and Acceptance

- **A1 — Durable identity:** every accepted start returns a unique task ID without waiting for worker completion; the record and result survive MCP manager restart and the job ledger does not contain the submitted prompt or secret values.
- **A2 — Observable lifecycle:** status distinguishes queued/running/completed/failed/timed-out/cancelled/unknown and includes bounded timestamps, last progress/checkpoint, DSH session ID when known, wrapper exit and failure layer.
- **A3 — Explicit recovery:** follow-up uses the recorded DSH session ID and a new focused continuation. It refuses concurrent follow-up while the previous writer is active and never replays the original prompt automatically.
- **A4 — Async MCP contract:** start returns promptly with task ID; list/status/wait/result/cancel work over MCP stdio JSON-RPC and return bounded JSON results. Malformed requests fail safely without leaking stack traces or credentials.
- **A5 — Isolated output:** synthetic worker modifications and new files appear only in the task workspace and patch artifact; the caller checkout is unchanged. `.env*`, `.git`, user Codex settings, credential directories, dependency caches and generated output are absent from copied inputs. The workspace is not claimed as an OS sandbox.
- **A6 — Resource and cleanup limits:** concurrency, input, output, event count, wait and execution duration are bounded; cancellation and server shutdown stop/reap owned process trees or report cleanup unresolved.
- **A7 — Installable package:** selecting the DeepSeek worker role installs its MCP helper dependencies; non-DeepSeek role installation does not add them. Package validation and extracted ZIP install/doctor/uninstall/restore lifecycle pass.
- **A8 — Documentation and scope:** both skill aliases state the same opt-in MCP/fallback policy; setup instructions do not silently edit global or project Codex config; no model settings, model calls, commits or pushes occur.
- **A9 — Standard repository gates:** `python scripts/build_release.py`, `python scripts/validate_package.py`, `python -m unittest discover -s tests -v`, and `git diff --check` pass. Runtime MCP loading in Codex and live DSH inference remain unverified unless explicitly exercised later.

## Idempotence and Recovery

Starting a task always creates a new task ID; retries are never implicit. Re-running the MCP server reads existing records and marks records whose process is no longer alive as interrupted/unknown rather than completed. Resume uses the same DSH session and task workspace only after prior process cleanup and diff inspection. A corrupt or partial state record is quarantined/reported and never interpreted as success. Patch artifacts are immutable per attempt; a follow-up creates a new attempt record so earlier evidence is retained. If release validation fails, fix the source and rebuild the manifest/ZIP; do not edit generated hashes by hand. Roll back only files introduced by this task, and preserve the pre-existing uncommitted changes listed above.
