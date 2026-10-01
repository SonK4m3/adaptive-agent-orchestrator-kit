# Layout migration — v2.2.0

| Previous source path | Current source path |
| --- | --- |
| adaptive-agent-orchestrator/ | skills/adaptive-agent-orchestrator/ |
| astra-orchestrator/ | skills/astra-orchestrator/ |
| roles/ | profiles/adaptive/codex/agents/ |
| docs/INSTALLATION.md, docs/RELEASING.md | guides/INSTALLATION.md, guides/RELEASING.md |
| docs/ORCHESTRATION-RELIABILITY.md | guides/ORCHESTRATION-POLICY.md |
| docs/ORCHESTRATION-RUN-2026-10-01.md | docs/validation/ORCHESTRATION-RUN-2026-10-01.md |
| eval/validate-kit.py | scripts/validate_package.py |
| eval/run-orchestration.py | scripts/run_orchestration.py |
| eval/fixture/ | eval/fixtures/independent/ |
| eval/acceptance.test.mjs | eval/oracles/independent.test.mjs |
| test-scenarios.md | eval/scenarios/catalog.md |
| eval/orchestration-scenarios.md | eval/scenarios/orchestration.md and eval/rubrics/orchestration.md |

Existing installed skill names, target paths and receipt schema remain unchanged. Re-run setup from the new source/package; confirm replacement for changed components. Previous content remains backed up. Named presets are optional managed additions, not replacements for base config.toml. Switching between presets does not activate either until the user starts a new CLI session with -p NAME.

Keep both self-contained skill copies aligned. Unlike upstream's per-profile skill copies, all resource profiles share these entrypoints. Canonical generation is deferred to keep this migration close to upstream and avoid changing both source and installed alias semantics at once.

The obsolete eval/test-install.ps1 referenced absent install.ps1/install-roles.ps1 scripts and has been removed. Its useful lifecycle coverage is replaced by tests/test_release.py, which builds, verifies checksum, extracts the ZIP and exercises install/doctor/uninstall/restore. Historical logs remain under ignored dist/ and are not moved or erased. The removed script can be recovered from the repository's initial commit.

distribution.json now declares package paths explicitly. CI configuration and repository-only metadata outside that list stay in the source checkout. Changing distributed files requires rebuilding release-manifest.json. Test the extracted package and both portable skills before delivery.
