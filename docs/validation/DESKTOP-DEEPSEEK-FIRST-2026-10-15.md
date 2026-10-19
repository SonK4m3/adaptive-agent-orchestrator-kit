# Historical Desktop DeepSeek-first activation — 2026-10-15

This is a historical record of the Phase C activation and probes on 2026-10-15, using
the policy that existed at that time. The repository now contains the Step 3 routing
policy, but the user chose to defer installing that revision into CODEX_HOME. This
record does not establish discovery or behavior for the current repository policy.
Real DeepSeek inference was not run during Phase C because the provider state was
reported as `server is busy`.

## Audit and installed scope

- `CODEX_HOME` was unset; the active default was the user's `.codex` directory.
- No global `AGENTS.override.md` existed. The original 2,404-byte global AGENTS.md
  was preserved byte-for-byte as the prefix; a marked 1,081-byte policy block was appended.
- The old adaptive user skill and the Astra alias had different policy revisions.
  Both now carry the same source policy; there is one discovered candidate for each name.
- The existing Hybrid Orchestrator is published as `adaptive-agent-orchestrator`;
  `astra-orchestrator` remains an equivalent explicit alias. No third name was added.
- The project root-only default was scoped to Codex fallback. Role/capability tables
  and topology diagrams now defer to the DeepSeek-first coding route.
- Generic `dsh-orchestration` and other unrelated skills were preserved; the global
  default selects one orchestration entrypoint instead of loading overlapping policies.
- The root config actually specified `gpt-6-luna` / `low`. Fallback selection inspects
  role pins instead of assuming the active root is Astra. Config and role TOMLs were
  preserved; all 30 protected model/source-helper hashes matched the pre-activation snapshot.

Installed paths at the time of this historical snapshot:

```text
<CODEX_HOME>/AGENTS.md
<CODEX_HOME>/skills/adaptive-agent-orchestrator/SKILL.md
<AGENTS_HOME>/skills/astra-orchestrator/SKILL.md
<CODEX_HOME>/scripts/deepseek_worker.py
<CODEX_HOME>/scripts/process_guard.py
```

The installed helpers previously differed from the hardened repository versions;
they were backed up and replaced with unchanged source copies using the managed
installer. Source wrapper/process guard bytes were not edited in Phase C. Installer
doctor validated all four managed components and the receipt after activation.

## Routing and tests

The default selects one DSH worker for suitable authorized coding context, preserving
the active repository/worktree cwd. Known provider-busy context skips real implementation.
The policy snapshot routed straightforward fallback work to a configured Astra role
and complex work to a configured Luna role. That rule is historical and has been
replaced in the repository by model-neutral role selection based on task fit and
actual pins. At most one known-transient retry was allowed,
bounded to 60 seconds, after worker cleanup and a clean partial-diff check. Uncertain
cleanup blocks the next writer. Root reviews actual changed paths and independently
runs acceptance tests. Details live in each skill's `references/deepseek-first.md`.

| Evidence | Result |
| --- | --- |
| Policy contract and fake DSH integration suite | 10 tests passed |
| Fake DSH against installed hardened helper | 4 tests passed |
| Full repository suite | 170 tests run, OK, 1 skipped (Windows symlink capability) |
| Package validator / source manifest / ZIP | Passed / refreshed |
| Extracted ZIP install/doctor/rollback lifecycle | Included in passing release tests |
| Rollback preview | Passed; no restore performed |

Fake tests cover successful result/Unicode/cwd, busy failure with suppressed diagnostics,
timeout with a descendant heartbeat writer, confirmed process exit before a fallback
write, and independent tests rejecting an implementation that falsely claims success.
Static routing assertions are contract checks, not evidence of model instruction following.

## Fresh Desktop session

Thread ID: `01a13d96-9f46-7073-8483-15c7175b6836`.
The new chat identified the default policy and adaptive skill path from its initial
context before inspecting filesystem copies. It confirmed discovery, absence of a
second same-name adaptive version, the installed wrapper/source hash match and CLI.
It ran the 10-test offline suite and two sequential fallback coding probes:

| Probe | Actual agent type / ID | Configured pin | Independent root result |
| --- | --- | --- | --- |
| Straightforward | `ao_worker_critical`, `/root/fallback_scenario_1` | `gpt-6-astra`, medium | Only calc.py changed; 1 test passed |
| Complex | `ao_worker`, `/root/fallback_scenario_2` | `gpt-6-luna`, high | Only two assigned modules changed; 2 tests and diff check passed |

Both fake busy calls returned wrapper exit 1, child exit 75, `cleanup_errors=[]`
and a confirmed stopped PID before dispatch. The first fallback completed before the
second was assigned; the second completed before root verification. Effective model
telemetry was not exposed, so configured pins remain distinct from confirmed models.
Requested permission was workspace-write; effective permission stayed null/unverified.

Raw evidence and full suite logs remain in local validation storage and are not part
of the release package. The repository does not contain user-specific evidence paths.

## Backup and rollback

The activation snapshot and rollback helper remain in local backup storage outside
this repository. They retain the original user-scope files and protected-file hashes.
The helper was previewed but not applied. Use the recoverable installer restore flow
for installer-managed components; review saved hashes before restoring manually managed
instructions. No rollback was performed during this repository cleanup.

## Limits

This is an instruction-driven default, subject to explicit requests and repository
restrictions. It is not a hard scheduling or filesystem isolation mechanism. The unchanged
wrapper suppresses provider error text, so generic failure cannot prove the specific
busy cause; known provider evidence must remain separate. Effective DSH permission and
per-agent runtime models remain unverified. Windows tests do not establish behavior on
other operating systems. No new MCP service, production runner or provider inference was performed.
The kit HEAD remained `e68757e` with no implementation commit, push or merge. The validation
chat did create disposable fixture baseline commits `661f141` and `c2ddd72` for Git diffs;
this exceeded the task's commit-only-after-approval constraint for fixtures. Those commits
contain only synthetic test setup and remain isolated. Future probes should use
`git add --intent-to-add`/no-index diffs without a baseline commit unless explicitly authorized.
