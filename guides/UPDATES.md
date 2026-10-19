# Stable release checks and update handoff

The fixed repository is `SonK4m3/adaptive-agent-orchestrator-kit`. Checks use GitHub's
public latest-release API without credentials. They do not scan project installations,
infer receipt versions, query models or enable JEV. Version ordering is numeric, accepts
`vMAJOR.MINOR.PATCH` and `MAJOR.MINOR.PATCH`, and excludes draft/prerelease metadata.
GitHub's selected latest stable release is used, not a scan for the numerically greatest
tag across history. Ordinary unpublished tags are not releases.

## Scripts

`setup.sh` / `setup.ps1` call the same Python setup. A best-effort release check occurs
before installer prompts. Offline/API/rate-limit/version-check failures warn and continue
the local installer. `--offline` / `-Offline` skips network access. If a newer version is
available, choosing it does not authorize downloading, executing, or overwriting existing
components: those prompts remain separate and default No. Declining the initial newer
release offer continues local setup; declining a later download/execution exits the handoff
without installing. Failed handoffs do not silently fall back to local setup.

`update.sh` / `update.ps1` are explicit check/update commands; failures return nonzero.
`--check` / `-CheckOnly` never downloads. `--offline` / `-Offline` reports skipped, not
up to date. Python `--check --json` is the AI-readable interface. No noninteractive
auto-accept switch is provided.

The default update command runs a validated downloaded `scripts/setup.py` with the
hidden `--skip-release-check` flag, suppressing recursion in the child. It still asks for
Codex home, profile, components and optional project routing; it does not become a
project-local installer. It preserves existing config.toml and overwrite confirmations.
The child process's exit code is returned. Temporary downloads are removed after return,
failure, declined execution or interruption handled by Python's temporary-directory scope.
As with other processes, a forced OS kill may leave scratch files requiring inspection.

## Codex setup skill

The [setup skill](../skills/adaptive-orchestrator-setup/SKILL.md) uses check-only first,
then `python scripts/update.py --stage-dir NEW_PATH` for an approved release. NEW_PATH
must not exist and its parent must exist. This mode never executes downloaded code.
It retains the validated source for review; scratch downloads are removed. The AI reviews
the target diff and conflicts again before project-local setup. The original source checkout
is untouched. Staged source cleanup is explicit after setup; it is not automatically deleted
before the AI can inspect it. Download approval is not authorization to replace components.

## Archive safety and publishing

Only generated ZIP source archives from the fixed repository's `codeload.github.com`
tag URL are downloaded. TAR files are not supported. API and archive redirects are refused.
Requests use a 10-second socket timeout, a 60-second read-loop deadline, no retries,
1 MiB API metadata limit and 32 MiB compressed archive limit. ZIPs are bounded to 4096
entries, 16 MiB per file and 128 MiB expanded total. The updater preflights member names,
duplicate/case-colliding paths, file/directory collisions, traversal, Windows-invalid names,
links, reparse points, encryption and unsupported entry types before member extraction.
It checks source layout, nine role files, matching VERSION/tag/manifest version and exact
distribution-file hashes before execution. It does not use `extractall` or import downloaded
Python for validation. Source-layout/manifest validation follows safe extraction, not before
download. These are integrity checks, not a signature or independent proof that release code
is trustworthy; release metadata/tag contents can change and archive hashes are recorded,
not compared with an independently trusted publisher signature.

Before publishing a stable release, set VERSION to its numeric tag version, build and
commit the matching release-manifest.json with `python scripts/build_release.py`, and
publish that exact commit. Generated GitHub source ZIPs must include this manifest and
the full source layout; no extra release asset is required. Do not regenerate the manifest
on a consumer machine to bypass a mismatch. There is no release-publishing workflow added
by this change. Existing users must obtain these scripts once before using the updater.
