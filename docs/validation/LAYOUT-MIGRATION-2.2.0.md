# Layout migration v2.2.0 — 2026-10-01 (Asia/Saigon)

## Acceptance evidence

| Requirement | Result and evidence |
| --- | --- |
| Follow upstream organization | profiles/, guides/, scripts/, tests/, root AGENTS.md/setup wrappers; see guides/MIGRATION.md and guides/UPSTREAM-COMPARISON.md |
| Preserve local differences | Adaptive topology/priority/contract/verification/adaptation/hard-failure policy preserved in both skills/ aliases; validator compares policy bodies and shared resources |
| Resource profiles do not force topology | adaptive capacity 4 and adaptive-max-2-subagents capacity 2 reference the same eight role bindings; config contains only agents settings |
| Installation remains recoverable | Explicit optional named preset, base config/unrelated skills preserved; restore accepts legacy managed skill/role paths and new named configs |
| Package source/install paths work | Release test builds, verifies SHA-256, extracts, installs, doctors, uninstalls, restores; each skill also installs alone without roles |
| Documentation/CI/tooling updated | All distributed Markdown links checked; CI builds manifest before validation/tests; runner CLI help and relocated oracle checked |

Windows/Python 3.14: package validator passed; 14 Python tests passed. Relocated independent oracle passed 8/8 against the previously implemented fixture in dist/orchestration-20261001-131336/independent. This is a path/oracle check, not a new live orchestration run. Final package checksum is emitted next to dist/adaptive-agent-orchestrator-kit.zip.

## Independent work and review

Root owns migration, profiles, installer, packaging and verification. A documentation agent independently produced the upstream comparison. A separate read-only reviewer examined installer/package risks. Agents used the default inherited configuration; effective model serving was not independently confirmed.

Initial findings: stale manifest while documentation was being edited, receipt path traversal, incomplete failure rollback and inclusion of arbitrary nested directory files. Manifest is regenerated after edits. Receipt components now have a managed-path grammar plus containment/link checks. Uninstall completes backups before deletion; restore preflights and stages all items before replacement. Failure rollback is covered by injected install-rename, uninstall-receipt and second restore-rename errors. Distribution paths have explicit allowed extensions; nested .env and private.key fixtures are excluded from the extracted ZIP.

No system can promise recovery if both the original operation and rollback fail due to continuing disk/permission failure; backups are retained for recovery. Backup content is structurally checked and copied, but it is not a cryptographically authenticated external archive.

## Limits

Local Windows verification only. CI matrix configuration is not macOS/Linux execution evidence. New named runtime preset activation, actual concurrency enforcement, desktop support and all-role serving were not live tested. Both skill aliases remain self-contained source copies with equality checks; canonical generation is deferred. No additional topology reliability rate or cost comparison is claimed. Global Codex settings and user projects were not changed. Local changes have not been committed or pushed.
