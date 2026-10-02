# Validation record — 2026-10-01, Asia/Saigon

## Consumer project skill routing — 2026-10-02

Interactive setup now registers selected installed skills in an explicitly chosen
project AGENTS.md by appending a marked block, never rewriting original bytes.
The standalone register_project.py helper supports additional projects.
Windows suite: 88 tests, 87 passed and one symlink-creation test skipped because
this host cannot create symlinks. Tests include original-byte preservation,
UTF-8/UTF-16 BOM and CRLF handling, idempotency, edited/malformed block refusal,
setup success/failure/skip paths and extracted-ZIP registration/uninstall lifecycle.
Package validator passes; no model execution. macOS/Linux and actual automatic
skill invocation remain unverified. See [registration usage](guides/INSTALLATION.md).

## Credential-free CLI preflight — 2026-10-02

Preflight gate and filtered evidence added; 76 Windows tests pass and package
validator passes. Evidence-only local run blocked on missing explicit native
sandbox selection, before authentication/inference; global config unchanged.
Explicit sandbox execution and model retries remain unrun. See
[preflight evidence and limits](docs/validation/CLI-PREFLIGHT-2026-10-02.md).

## Agent graph / runtime pilot

Graph schema, workstream/verification ownership, revision and confirmed handoff checks are implemented in both portable skills. Offline Windows integration checkpoint: 70 tests pass, including package lifecycle, graph/navigation regressions, mocked harness and real local process-job containment. One worker CLI probe failed the artifact check and reported access-policy/tool-visibility blockers; reviewer and four autonomous runs remain unrun. No model/effort change or savings claim. See [implementation evidence](docs/validation/AGENT-GRAPH-IMPLEMENTATION-2026-10-01.md) and [dispatch attempt](docs/validation/AGENT-DISPATCH-2026-10-01.md). Later package checks are structural only; earlier evidence below is historical.

## Layout migration v2.2.0

Upstream-style profiles/guides/tooling organization now preserves the adaptive policy and both entrypoints. Windows package validator and 14 Python tests pass, including extracted-ZIP lifecycle, optional named presets, standalone aliases and injected failure rollback. The relocated oracle passes 8/8 against an earlier implemented fixture. These are migration checks, not fresh topology/model benchmarks. See [migration evidence and limits](docs/validation/LAYOUT-MIGRATION-2.2.0.md). Earlier entries below remain historical records.

## Adaptive topology experiment

Four live CLI scenario runs with a 600-second cap each completed below the cap. All stayed within scratch-file scope. Root-only and independent behavior checks passed; authorization matrix passed; rounding ambiguity was reported as unresolved. All four chose root-only, so delegation, independent reviewer dispatch and agent reuse remain unverified. See [reviewed evidence and diagnostic rubric](docs/validation/ORCHESTRATION-RUN-2026-10-01.md). Requested model/effort were fixed; effective serving was not independently confirmed. The runner's subsequent Git-isolation correction has not received a live rerun.

## Distribution packaging checks

- Windows / Python 3.14.5: package structure validator passed; five installer unit tests passed (fresh install, unrelated-file/config preservation, conflict refusal, replace backup and restore, uninstall and restore, modified-component force gate, tamper detection). Python byte-compilation passed.
- Built release ZIP v2.0.0, verified its SHA-256, extracted it to an isolated temporary directory, then installed all 10 components into a separate temporary `CODEX_HOME`; `doctor` passed and uninstall removed the tracked skill/role content while preserving its recovery backup.
- These checks were run locally on Windows only. macOS/Linux coverage is configured in GitHub Actions but has not run in a published repository. No claim of cross-platform pass is made yet.
- The offline package `doctor` does not test Codex skill discovery, model serving, or actual runtime role selection. The earlier CLI smoke evidence below is separate from this extracted-ZIP install check.

## Verified

- Both SKILL.md entrypoints passed the Codex skill-creator quick validator.
- Package validator checks local skill links, identical alias resources, 10 Mermaid source blocks per alias, and parses all eight role TOMLs with Python tomllib. This does not validate diagram rendering.
- Installer exercised in an isolated directory: fresh installation, repeat installation, obsolete-file removal from the active version, preserved old version, whole-directory rollback, source/destination and backup overlap rejection. Role installer was run twice with identical results.
- Real Codex CLI v0.159.2 coding test: installed astra-orchestrator, root reported gpt-5.6-luna / low, two actual worker spawns with disjoint duration.mjs and grouping.mjs ownership. R1–R4 acceptance suite passed 8/8, including negative inputs, safe-integer limits, nonsorted group/ID order and input immutability. Original stubs failed 8/8 before implementation. TASK.md stayed unchanged. Child effective models were not independently confirmed in the captured text trace.
- Separate fresh CLI session discovered and spawned ao_explorer. It returned parseDuration and groupByStatus correctly. Spawned agent ID: 01a0f376-e237-7aa2-a61f-f774ced5043b. This proves role discovery and successful dispatch, not a comparative model benchmark.
- Independent review found installer stale-file/overlap problems and a test-ordering blind spot; these were fixed and the affected checks passed.
- A policy exercise recognized that an 8-minute deadline cannot contain a mandatory 12-minute integration suite and kept the quality gate. It correctly identified model pin and missing cost evidence. It also described a requested model as not yet authorized; wording was clarified to preserve existing user authorization. That clarification has not received a separate behavioral rerun.

## Evidence locations on the build machine

Raw local logs: ../orchestrator-validation/coding-run.log and ../orchestrator-validation/role-smoke.log. These are intentionally outside the distribution because runtime output can include local context. The coding fixture and repeatable acceptance test are included under eval/.

CLI reported 62,101 tokens for the coding run and 29,543 for the role smoke. These are raw CLI summaries; per-agent attribution and total billing scope were not established. They are not evidence of savings. The runs loaded the machine's existing global instruction context.

## Not established

No quality-equivalent cost/latency comparison against root-only or the upstream fixed profile. No deadline SLA, automatic topology-selection accuracy estimate, full 14-scenario pass, production repository acceptance, all-role live dispatch, or automatic Jev graph dispatch. An opt-in [Jev advisory smoke](docs/validation/jev-advisory-2026-10-02.md) now validates a single real API response and root-decision recording on synthetic state; it does not execute subagents or establish routing quality. Junction rejection exists in the installer but was not exercised on a real junction. Failure during the final filesystem rename was not fault-injected. Mermaid source diagrams were checked structurally, not visually rendered.

Named models and efforts in role TOMLs are configured choices; runtime/account access and actual serving require runtime evidence. Model bindings are starting hypotheses informed by documentation, not benchmark-calibrated assignments.
