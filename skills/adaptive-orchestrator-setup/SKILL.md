---
name: adaptive-orchestrator-setup
description: Prepare the Adaptive Agent Orchestrator for Codex in an existing target repository, with a read-only setup preview, project-local installation and conflict checks. Use for installing or updating this kit, not ordinary coding tasks.
---

# Adaptive orchestrator setup

Prepare a target repository so the user can invoke `$adaptive-agent-orchestrator` or `$astra-orchestrator`. These entrypoints share one adaptive L0-L3 policy, not a fixed Astra/Luna tree. Priorities remain correctness and completeness, then deadline, then cost. Small tasks remain root-only without mandatory graph/report files. JEV is optional; all levels remain available without it.

Use this project's source: https://github.com/SonK4m3/adaptive-agent-orchestrator-kit. The upstream donvito repository is a reference, not the installation source. This skill may be shared alone; it does not bundle the kit's installer or profiles.

## Scope and safety

- Resolve an existing target repository, distinct from the source checkout. Never infer the target from the kit directory. Ask if the target is missing or ambiguous.
- Default to project-local skills in `.agents/skills/`, roles in `.codex/agents/`, and routing appended to the target's `AGENTS.md`. Do not alter global Codex home, global agents/instructions, shell aliases, credentials, providers, approvals or sandbox settings.
- Start with a read-only preview. Show source revision, profile, model/effort bindings, each destination, conflicts and proposed diffs before target writes; wait for the user's approval unless that exact preview was already approved. Do not run the interactive wrappers: they default to Codex-home installation.
- Preserve unrelated edits and incompatible files. Identical files are no-ops; different files require an explicit keep, backup-and-replace, or defer choice. Refuse symlinks/junctions/reparse points along destination paths. Never silently resolve a conflict with `--replace`.
- Setup does not authorize model calls, JEV requests, benchmarks, commits, pushes or PRs. A plan/subscription is context, not proof of model access.

## Prepare and preview

1. Inspect target Git status, `.agents/skills/`, `.codex/agents/`, `.codex/config.toml`, `AGENTS.md`, instruction files and hooks relevant to setup. Inspect applicable user config, active profiles and existing role-name bindings read-only for overrides; never print credentials or arbitrary environment values. Mark inaccessible configuration uninspected.
2. Use an explicit trusted local checkout/release, or clone the source into a temporary directory outside the target. Record the inspected commit/release and keep that revision fixed through installation. Do not regenerate its manifest to hide mismatched files. Validate the source with `python scripts/validate_package.py` and the release integrity function used by `scripts/manage.py` before using it.
3. Default to one entrypoint, `adaptive-agent-orchestrator`, and recommend `adaptive-max-2-subagents` for a first pilot; retain an explicit user choice. The other profile is `adaptive` (capacity 4). Neither requires that many agents. There are no `pro`/`plus` profiles. Show all nine bundled `ao_*` role bindings, including the external DSH bridge; preserve existing root model and effort. Ask about unavailable models only when a binding needs a decision; do not invent replacements.
4. Preview copying the chosen complete skill folder(s), the nine optional namespaced roles (including the external DeepSeek Harness bridge role), its helper script when roles are selected, installer receipt/possible backup paths, and the exact `AGENTS.md` append. Include new/untracked/ignored files in the preview, not just `git diff`. If optional roles cannot be installed, explain the built-in-agent fallback and obtain the scope choice.
5. Preview the selected profile's concurrency key in project `.codex/config.toml` only if the user wants its cap applied. This is a separate reviewed merge preserving existing keys/comments, not an overwrite. An installed role set alone does not activate a capacity preset. Check current official Codex documentation for runtime-sensitive schema/discovery details.

## Apply the approved project setup

From the pinned kit directory (Python 3.11+, standard library):

- Copy each approved entire `skills/<entrypoint>/` folder to `<TARGET>/.agents/skills/<entrypoint>/`, preserving its relative assets/references. Do not install the setup skill recursively or change unrelated skills. For an approved replacement, retain a verified backup outside the component before copying; record its location. These project skill copies are not managed by `manage.py`'s receipt/uninstall.
- Install approved roles using the existing recoverable installer, always with an explicit project target:

```sh
python scripts/manage.py install --target "<TARGET>/.codex" --profile adaptive-max-2-subagents --parts roles
python scripts/manage.py doctor --target "<TARGET>/.codex"
```

Add `--replace` only for a reviewed replacement choice. Do not add `--with-profile-config`: named Codex-home presets are not project configuration activation. Merge only the approved concurrency setting into project `.codex/config.toml`; omit the merge if declined.

- Append routing with portable project-relative skill links:

```sh
python scripts/register_project.py --project "<TARGET>" --project-skills --skill adaptive-agent-orchestrator
```

Use `--skill astra-orchestrator` or `both` only for the approved installed entrypoints. The helper preserves existing `AGENTS.md` bytes, appends one marked block, and treats identical reruns as no-ops. A changed/malformed block stops registration; show the conflict and request a specific resolution, never erase or duplicate it. The helper's refusal is not permission to rewrite instructions manually.

- Leave JEV disabled/unconfigured. Do not read/copy `.env` secrets, install a proxy or auto-enable task-retro-survey. Optional advisory and survey setup are separate user choices, not prerequisites.

## Check releases and update

On setup/update invocation, unless the user requested offline operation, run `python scripts/update.py --check --json` from the trusted kit source. It compares that source's `VERSION` with GitHub's latest stable release, not installed project versions. Report the tag and release-notes link. Check failures are warnings for ordinary setup; continue the pinned local source. For an explicit update/check request, report failure, not "up to date". `--offline` skips the network without claiming freshness. Never check on every coding task or install a background monitor.

If a newer stable release exists, offer an explicit choice to keep local source or download the newer release. After approval, use `python scripts/update.py --stage-dir "<NEW_TEMP_SOURCE_PATH>"` and answer its download prompt only for that approved release. The path must not exist and its parent must exist. This validates a bounded generated ZIP archive, matching VERSION and manifest; it never runs the downloaded installer. If the release changed between check and stage, obtain approval for the new tag before answering. Review the staged source and its setup skill, then repeat the target preview/conflict checks above before applying it project-locally. A download approval is not replacement approval. Do not invoke `update.py` without `--stage-dir` from this workflow: its interactive handoff runs the Codex-home installer, not this project-local procedure.

Record staged-source location/version and remove the temporary source after the reviewed setup finishes. Scratch downloads are cleaned automatically; caller-owned staged source persists for review. Leave the old checkout and global configuration untouched. A current source version does not prove target files are current: compare selected installed components against the pinned source. Do not turn a failed download into an unannounced local install.

## Verify and hand off

Parse resulting role/config TOML with Python `tomllib`; validate each skill's frontmatter/name and relative links. Check role IDs, model IDs/efforts against the pinned source and available runtime information; unknown account availability stays unknown, not "validated". Compare copied skill files to the source, confirm the original `AGENTS.md` bytes remain a prefix, run the role doctor, and review target Git status plus `git diff --check`. A clean diff alone cannot validate new or ignored files.

Report source revision, installed/skipped/conflicting components, actual profile cap status, root settings preserved, backups, checks and unresolved gaps. Distinguish role receipt ownership from manually copied skills and append-only routing. Suggest a small commit; do not stage/commit automatically.

Give the next-session prompt: `$adaptive-agent-orchestrator <task and acceptance criteria>` (or the selected alias). A new Codex chat in the trusted target is needed to confirm runtime discovery and actual role/model use; offline checks do not prove dispatch. Do not run that paid smoke task without authorization. No-JEV operation must remain usable, with root deciding topology and verification.

## Contribution mode

Only when explicitly requested, inspect the selected contribution repository's README, tests and contribution rules. Make a scoped local branch/change and run the affected checks. Report a paste-ready PR title/body and evidence. Do not push or open a PR without explicit authorization, and do not confuse contributing to this kit with installing it into a consumer repository.
