# Desktop DeepSeek-first activation

The Hybrid Orchestrator is the existing `adaptive-agent-orchestrator` skill with
DeepSeek-first routing and automatic Codex fallback. `astra-orchestrator` remains
an explicit alias with the same policy. A third skill name is unnecessary.

Use a fresh Desktop probe as evidence for the actual discovered paths. Static file checks
and the installer doctor do not prove session discovery or model behavior.

## Scope and authority

Append the block in [DEEPSEEK-FIRST-GLOBAL.md](DEEPSEEK-FIRST-GLOBAL.md) to the
active Codex home's global `AGENTS.md`, preserving unrelated bytes. Check for
`AGENTS.override.md` first: a nonempty override hides the global file. Resolve
`CODEX_HOME` from the environment, otherwise use the user's `.codex` directory.
Audit project instructions for conflicting root-only or worker-routing defaults;
repository privacy restrictions and explicit user instructions still apply.

Update the existing user skill location instead of installing a second copy with
the same name. Desktop versions may expose both `.codex/skills` and `.agents/skills`;
verify the actual discovered paths in a new session. Synchronize the explicit Astra
alias to the same source policy. The generic `dsh-orchestration` skill describes
team structure and is not a DeepSeek execution interface.

Copy the validated wrapper and `process_guard.py` unchanged to the active Codex
home's `scripts/` when the installed helpers differ. Keep config.toml and all model
role TOMLs byte-identical. Preserve any managed installation receipt when updating
managed components; use the kit's installer for its existing skill location.

## Verification

Run `python -m unittest tests.test_routing_policy tests.test_hybrid_delegation -v`.
The fixture runs real wrapper subprocesses with a fake `dsh` launcher prepended to
PATH only in the test child. It never calls a provider. It covers successful output,
busy/error redaction, independent tests rejecting a false success claim, and timeout
cleanup of a descendant writer before a fallback can edit.

The routing-contract tests check conditional DeepSeek routing, model-neutral Codex fallback,
and retry/handoff requirements.
They establish the policy contract, not model instruction following or native agent
dispatch. Validate discovery and routing again in a fresh Desktop chat, without
passing a skill name or copying the desired routing answers into its prompt.
Record actual skill paths, selected roles, reported outcomes and runtime limits.
When commits are approval-gated, use intent-to-add or no-index diffs for disposable
fixtures too; creating a fixture is not permission to commit its baseline.
Provider-busy context forbids real DSH implementation during these checks.

Global instructions and skills are model-followed policy, not an executable hook or
hard filesystem/concurrency enforcement. The unchanged wrapper suppresses the busy
error text, so record known provider evidence separately; generic wrapper failure
does not prove a specific provider cause. Independently verify code even when the
wrapper reports `completed`. See the selected skill's `references/deepseek-first.md`
for the complete execution and fallback contract.

## Backup and rollback

Before changing anything, back up the global file, affected skill trees, helpers,
managed receipt and source policy files outside skill-discovery directories. Save
hashes of config.toml, role TOMLs and the hardened source wrapper to confirm they
remain unchanged. Keep an activation manifest with each target, its original copy,
whether it existed, and its post-activation hash.

Stop active writers before rollback. For installer-managed skills, agents or helpers,
use `python scripts/manage.py restore BACKUP_ID --target <CODEX_HOME>` with the backup
created by that installation. Restore manually managed global instructions only from
the reviewed backup after comparing current and saved hashes. Preserve post-install edits
in a separate copy before restoring. Start a new Desktop chat and inspect its instruction
sources and skill paths after rollback. Repository source changes remain for review.
