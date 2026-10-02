# Release updater validation — 2026-10-02

Scope: fixed-repository stable-release checking, guarded installer handoff, safe ZIP
staging, wrapper argument forwarding, and Codex setup-skill project-local update guidance.
No models, JEV, remote writes, release publication or global configuration edits were run.

## Evidence

- `python -m unittest discover -s tests -p test_update.py -v`: 30 tests passed on
  this Windows host. Includes source-versus-release comparison, numeric stable version
  ordering, invalid/missing versions, offline/check-only/EOF paths, failed check fallback,
  declined handoff, network size bounds/no auth header, URL/redirect refusal, ZIP paths,
  link/special types, collisions, expanded size bounds, manifest/layout/version mismatch,
  cleanup on failure/decline, staged-source preservation/no overwrite and recursion guard.
- Fixture-based handoff runs the **actual downloaded child installer** from a locally
  generated source ZIP with mocked network transport. It installs the selected skill
  and eight roles into an isolated Codex home with spaces, preserves existing config,
  returns the child status and suppresses recursive checking. This is not a live GitHub
  release installation or evidence of Codex runtime discovery/model serving.
- PowerShell 7 wrapper check-only/offline and setup cancellation tests passed. Windows
  PowerShell wrapper check-only/offline passed. No installation occurs in those wrapper tests.
- Git Bash `bash -n setup.sh update.sh` passed; `bash ./update.sh --check --offline`
  returned success and explicitly reported skipped. Linux/macOS/dash and ShellCheck
  are unrun; Git Bash evidence does not prove those platforms.
- `python scripts/update.py --check --json` against the fixed public GitHub API
  returned exit 1 / HTTP 404. This could mean no accessible published stable release
  or repository visibility/access limitations; this check cannot distinguish them.
  No archive was downloaded/executed in the live check. No claim of "up to date".
- Skill frontmatter quick validation, package validation and `git diff --check` passed.
  The package lifecycle suite exercises the extracted ZIP and project-local role/routing
  setup. Full-suite results are reported in the task handoff.

## Boundaries

Only ZIP source archives are supported, not TAR. Manifest checks detect mismatch but
are not signatures. Temporary scratch is removed on normal completion, declined execution
and caught exceptions; forced OS termination may leave scratch. AI-mode staged source
persists intentionally until explicit cleanup. Version checks describe the source copy,
not each project's installed version. Global/default installer and project-local AI
setup remain distinct workflows. Users must obtain these scripts once; matching VERSION
and a committed freshly built manifest are prerequisites for publishing a usable release.

No independent agent review, live stable-release handoff or cross-platform release
installation was performed in this task. The upstream validation list supplied by the
user is not evidence for this implementation.
