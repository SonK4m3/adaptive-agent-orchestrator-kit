# Agent graph implementation — 2026-10-01

Environment: Windows, Python stdlib tooling, Codex CLI 0.159.2. Work follows [the approved implementation plan](../plans/AGENT-GRAPH-IMPROVEMENT.md). This record will distinguish implementation, offline checks and live evidence; no reliability rate or savings claim follows from the pilot.

## Phase 1–2

Navigation now names the package-root role-install command and evaluator catalog location. Installed skills have no links outside their own bundles. Regression tests reject the obsolete installer/catalog references and external local links.

Graph schema 1 records workstreams separately from runtime assignees, dependency versus verification edges, actor owners versus check methods, criterion evidence/status and revisions. Exact-file ownership is checked conservatively across case/separators; unsupported absolute/traversal/glob/device/trailing-dot paths are rejected. Read scopes may overlap. This is structural validation, not filesystem isolation or lifecycle attestation.

Twenty-one focused graph tests (including both portable skill examples) and four navigation tests pass. Integration checkpoint: 70 tests passed on Windows, including extracted-ZIP lifecycle, standalone skills, 30 mocked harness tests and one live local Windows process-tree test. No model was invoked by these tests. Earlier transient integration failures from concurrent source edits/stale manifest were resolved by rebuilding the stable source tree; they are not hidden as passes.

Independent read-only review found transfer bypasses through completed new writers, removed reservations, unrelated historical completion and unchanged obsolete nodes. These were corrected with exact transition regressions. Malformed nested JSON now returns errors; nonportable Windows aliases are rejected. The final narrow re-review passed four related checks with no remaining material finding in that reviewed scope.

Reviewer configured: ao_reviewer / gpt-6-astra / low; actual ID 01a0f829-3b73-7030-8d51-cb097d822c0c. Effective serving remains unconfirmed. Worker implements only runtime harness/fixtures/tests; root owns graph schema, policy and integration. This implementation delegation is not one of the six experimental runs.

## Runtime and behavioral gates

The CLI bundled model catalog exposes gpt-6.1-sol with medium effort support; requested root settings were fixed to that configuration. Named roles retain their pins. App tool metadata exposes ao_* roles, but that alone does not prove temporary CLI profile resolution or serving.

| Phase | Outcome |
| --- | --- |
| P1 navigation | Implemented; installer/catalog drift and installed-skill link regressions checked |
| P2 graph/contract | Implemented; four example shapes, revision/ownership guards and independent correction review |
| P3 dispatch | Harness implemented; first worker probe failed required artifact check; gate blocked |
| P4 routing/adaptation | Four fixtures, external oracles and checkpoint/resume harness implemented; live runs unrun behind P3 |
| P5 economy | Deferred behind behavioral gate; no role pin/default change or resource pilot |

See [dispatch attempt](AGENT-DISPATCH-2026-10-01.md). Exactly one experimental model run was attempted (78.478 seconds); the reviewer probe and four behavioral runs were not attempted. No automatic retry. Actual task artifact did not change. CLI candidate reported policy-denied reads and missing IDs/close tools; the captured public trace has one completed wait with no receiver IDs, no observed spawn/close records, and no graph. This cannot attest named dispatch or lifecycle. Do not infer zero actual children from an incomplete trace.

The probe was run before subsequent containment/oracle hardening; its historical raw evidence is preserved, not retroactively regenerated. Final runner uses an owned Windows Job Object with suspended-start assignment, unconditional job/group closure and fallback parent kill/reap. A local non-model test verified that closing the Windows job kills a live descendant after normal parent exit. Remote/shared sessions outside the owned OS tree remain unverified; live POSIX pilot execution is disabled because detached descendants are not contained by a process group alone.

Independent harness review corrected inherited oracle credentials, unrestricted output persistence, incomplete timeout cleanup and duplicate graph revisions. Oracle execution now requires a credential-free ephemeral home and explicit filesystem/network sandbox profile, suppresses candidate stdout/stderr, checks exit/criterion coverage, and rejects unsafe fixture imports/IO/introspection before loading any candidate. The bounded AST subset rejects aliased self-imports too; unsupported candidate constructs are unrun, not behavioral passes. This guard is not universal Python isolation or a production-code oracle. Sandbox enforcement itself remains unverified: the non-model local oracle attempt produced no result, so the helper failed closed without an unrestricted fallback. The final narrow source review confirmed the exact reported alias forgery is rejected; it did not claim universal sandbox safety.

One non-inference preflight attempted --strict-config with codex features; this subcommand rejects that flag. A concurrent package build/install also caught the worker's changing source file set. Neither is counted as a model run or a role/schema failure; installation must use a stable rebuilt package.

Official sources inspected: [custom subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents) and [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference). Runtime probes must separately establish local recognition and actual dispatch.

## Measurement boundary

Read-only account usage snapshot near implementation start: primary 10% used / 300-minute window, reset epoch 1790885827; secondary 56% used / 10080-minute window. Source: Codex app usage tool. This was captured after the first implementation agent was dispatched.

Later snapshot at 2026-10-01 16:20:19 UTC: primary 65% / 300 minutes, same reset epoch; secondary 65% / 10080 minutes, reset epoch 1791131493 unchanged. Comparable account deltas: +55 percentage points primary, +9 secondary. These include this chat/implementation agents and any other account activity; no task/agent billing attribution is established. They are not tokens, purchased credits or API dollars and are not evidence of savings.

The single CLI turn reported input 259547, cached input 233216, output 914 and reasoning output 75. These are raw turn counters with child inclusion unknown; cached input is not added to input, and reasoning output is not added to output. Do not aggregate them with account percentages or claim all-agent totals. Model/effort are requested/configured, not independently served-model attestation.

No global settings edits, publication, commit or push. Resource comparison/promoting lower effort is outside the approved pilot until its separate budget/decision is supplied.

## Next decision

Resolve the CLI read/verification/tool-visibility blocker on an explicitly chosen runtime and authorize the next bounded attempt; do not silently rerun or relax global security policy. A Desktop implementation-role trace may be useful supplemental evidence, but cannot substitute for temporary CLI profile activation. Until then keep P3/P4 live outcomes and P5 improvements deferred. Source/package integrity passes do not mean the whole plan is complete.
