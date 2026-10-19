# Installation details

For AI-guided project-local installation, use [adaptive-orchestrator-setup](../skills/adaptive-orchestrator-setup/SKILL.md).
This is distinct from the existing Codex-home wrappers described below: project skills
go in `.agents/skills/`, roles in `.codex/agents/`, and any concurrency setting is an
explicit project-config merge. The setup skill does not silently invoke the global-default
wrappers or install itself with the orchestration entrypoints.

The installer requires Python 3.11+ and uses only the standard library. Run `./setup.sh` on macOS/Linux or `./setup.ps1` in Windows PowerShell for interactive setup. It asks which skill entrypoint(s), optional roles, and target Codex home to install, then runs the offline integrity check. It reads the package manifest before install and refuses missing, modified, or unlisted distributable files. distribution.json selects paths and permitted extensions; unrelated source artifacts are not installed. Use the extracted release directory as-is.

Setup also asks for a resource profile and an optional named preset, defaulting preset installation to No. Use --profile adaptive or --profile adaptive-max-2-subagents. Both reference the same role bindings and skills. --with-profile-config additionally installs <profile>.config.toml as a receipt-managed component; activate it in a new CLI session with codex -p <profile>. See [profile details](PROFILES.md). Existing base config.toml and project instructions are preserved.

`CODEX_HOME` can point at a custom Codex home; otherwise the installer uses `~/.codex`. `--target` overrides both. Components are installed into `skills/<skill-name>` and `agents/ao_*.toml`. The role files are optional and can be omitted with `--parts skills`. Selecting roles also installs the DeepSeek handoff helper and its process-tree guard under `scripts/`; `ao_deepseek_worker` uses these only when assigned a bounded task and `dsh` is available. The helper defaults to `read-only`; `workspace-write` requires an explicit flag from the delegated contract. It returns only the final response and compact run evidence, suppressing raw reasoning/event output.

To add only the DeepSeek bridge role to an existing Codex home without replacing other role files, run `python scripts/manage.py install --parts roles --role ao_deepseek_worker`. This is a Codex-home install, not a global `config.toml` change; start a new Codex session to discover the agent. The installer refuses a conflicting existing file unless `--replace` is explicitly supplied, and preserves replaced content in a recoverable backup.

On conflict, inspect the existing destination first. `--replace` makes a recoverable copy and updates only the named components. A receipt at `.adaptive-agent-orchestrator/install.json` records hashes for components managed by this kit. Uninstall acts only on receipt-listed paths; modified contents require `--force` and are backed up. Restore a backup with `python3 scripts/manage.py restore BACKUP_ID`; restoration also preserves the current contents. `config.toml`, other agent definitions, and unrelated skills are not managed.

After installation, start a new Codex session and invoke one of the skill names. If discovery fails, check the exact Codex home used by the running runtime, inspect its skill/agent search configuration, then run `doctor --target PATH`. Do not infer effective model selection just from a TOML declaration: confirm it in runtime output when that matters.

## Register skill routing in a project

Interactive setup now asks for an existing project directory. After install and
doctor succeed, it automatically appends a clearly marked routing block to that
project's `AGENTS.md` (creates the file if missing). Enter skips this step; setup
never guesses a project from the kit checkout or modifies global instructions.
The block points to the selected installed skill(s), not package-source paths.
It guides automatic consideration, small-task root-only behavior and conditional
graph/report creation. It is guidance, not proof of runtime invocation.

For another project, or after a direct `manage.py install`, run:

```sh
python scripts/register_project.py --project /path/to/project --target /path/to/codex-home --skill adaptive-agent-orchestrator
```

`--target` defaults to `CODEX_HOME` or `~/.codex`; select `--skill both` only when
both entrypoints are installed. The helper requires the selected installed files.
Existing content is preserved byte-for-byte as a prefix, including BOM and line
endings (UTF-8 or BOM-marked UTF-16). Identical reruns do nothing. Edited, duplicate
or incomplete managed blocks stop registration without rewriting anything.
Symlink/reparse targets and existing registration locks are refused. A stale
`.AGENTS.md.orchestrator.lock` after interruption must be inspected before retry;
if append was interrupted, inspect the partial block as well. Avoid concurrent
editor writes during registration: the lock coordinates installers, not editors.

Registration is intentionally outside installer receipt ownership. Uninstall and
restore do not erase project instructions; after uninstall/moving Codex home,
review/remove the marked routing section yourself. A changed registration is
never automatically replaced. Skill install may succeed even if project routing
fails: setup reports this separately and returns failure rather than claiming full
completion. Do not commit machine-specific absolute skill paths to a shared repo
without review; each teammate should register against their own installation.

For already installed project-local skills, use portable relative routing instead:

```sh
python scripts/register_project.py --project /path/to/project --project-skills --skill adaptive-agent-orchestrator
```

`--project-skills` verifies the selected entries in that project's `.agents/skills/`
and cannot be combined with `--target`. It never falls back to global skills. Changing
an existing absolute-path block to relative paths still requires manual review of the
conflicting block; the helper refuses to replace it. The same append-only encoding,
lock, symlink and rerun safeguards apply.

## DeepSeek worker limits and evidence

Send UTF-8 task text on stdin to `python scripts/deepseek_worker.py`. The JSON
response uses ASCII escapes, so Unicode answers survive legacy Windows terminal
encodings; a JSON decoder restores the original text. Raw DSH events and stderr
are not forwarded. This wrapper does not change Astra/Luna model configuration.

The wrapper caps stdout at 1 MiB and stderr at 256 KiB, drains both concurrently,
and stops the owned process tree on overflow or timeout. `--max-stdout-bytes` and
`--max-stderr-bytes` can lower those caps. Each JSON event is limited to 64 KiB,
with at most 4096 lines processed. Malformed UTF-8/JSON, duplicate JSON keys,
nonfinite numbers, conflicting session IDs, duplicate/empty finals, error events,
or a nonzero child exit cannot produce a successful answer. Unknown event types
are counted as `other`; only a successful final answer enters the parent context.
The task input itself is limited to 1 MiB. Timeout remains 1–600 seconds, followed
by bounded cleanup; descendants outside the owned process tree are not covered.

Child environment inheritance uses an explicit allowlist: OS executable paths,
Windows system directories, user/config/cache directories, temporary directories,
locale variables and `DEEPSEEK_API_KEY` for authentication. Unrelated provider keys,
`NODE_OPTIONS`, `PYTHONPATH`, arbitrary `DSH_*`, proxy and custom certificate
variables are not inherited. `DSH_PERMISSION_MODE` is set from the selected flag.
Custom deployments relying on excluded variables need an explicit, reviewed
allowlist change. This filtering does not sandbox DSH's access to files, its own
stored credentials, config or services; it never reads or copies `.env` files.

Report fields distinguish `requested_permission_mode` from
`effective_permission_mode` (currently `null`) and `permission_verification`
(`unverified`). This replaces the ambiguous `permission_mode` field. The Codex
role's `workspace-write` sandbox and DSH's requested `read-only` mode are separate
layers; neither a flag echo nor a child event proves enforcement.

`exit_code` preserves the child's observed code; the wrapper returns 0 for a valid
success, 124 for timeout and 1 for job/protocol/output/cleanup failures (2 for invalid
input, 127 for a missing CLI). Failed runs omit `answer`. A missing session is
reported as `session_id: null`, `session_evidence: missing`; an observed ID is
child-reported correlation, not independent attestation. Timeout/overflow retain
captured session evidence and mark `output_capture_complete: false`. Observed byte
counts may be lower bounds when capture stops early. `cleanup_errors` records
cleanup problems separately without replacing the primary timeout/overflow reason.

The offline integration suite uses real subprocesses and process guards with a
fake DSH protocol, including Windows `.cmd` launch, UTF-8/CP1252, blocked stdin,
output floods, failed jobs and descendant-held pipes. It spends no model credits
and does not establish live DSH compatibility or effective permission enforcement.
