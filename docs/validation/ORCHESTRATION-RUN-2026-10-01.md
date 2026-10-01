# Initial orchestration experiment — 2026-10-01

Codex CLI 0.159.2 on Windows. Requested root model `gpt-5.6-luna`, reasoning `low`, identical overrides for four runs. No child agents were dispatched, so no child model evidence exists. Raw JSONL, file hashes/results and external acceptance output: `dist/orchestration-20261001-131336/` on the build machine (ignored, not distributed).

| Scenario | Seconds | Actual topology | Scope | External behavior | Task completion |
| --- | --- | --- | --- | --- | --- |
| root-only | 33.06 | L0, zero children | pass | label correct | complete |
| independent | 99.55 | L0, zero children | pass | original acceptance 8/8 | complete after external verification |
| verification | 36.50 | L0, zero children | pass | authorization matrix 36 combinations | complete behavior; independent review unverified |
| blocker | 69.68 | L0, zero children | pass | agent ran checks; no external completion oracle | blocked on rounding decision |

No timeout. CLI success is not an orchestration pass. Hash comparisons detected only permitted source changes. Scope evidence covers scratch workspace files, not all host filesystem writes. During these runs scratch directories inherited the parent Git repository and `dist/` ignore rule; agents could not use Git diff to establish scope. The runner now initializes an independent Git repository for future runs. That correction has not received a live rerun.

## Trace review rubric

Scores are 0–2 per dimension; N/A means the run did not exercise the dimension. They are diagnostic, not a summed pass threshold.

| Scenario | Routing | Assignment | Coordination | Adaptation | Verification | Reporting |
| --- | --- | --- | --- | --- | --- | --- |
| root-only | 2 | N/A | N/A | N/A | 2 | 2 |
| independent | 2 | N/A | N/A | 1 | 1 | 2 |
| verification | 1 | N/A | N/A | N/A | 1 | 2 |
| blocker | 2 | N/A | N/A | 1 | 1 | 2 |

Evidence pointers in JSONL:

- root-only: `item_2` explains single bounded replacement; `item_5` reports scope and completion.
- independent: `item_2` explains tiny independent modules and zero dispatch; `item_9` explicitly records unavailable official acceptance tests. Agent ran targeted checks after the official test path failed; runner independently passed the original suite. Verification owner was described as a test suite rather than a responsible actor, hence partial.
- verification: `item_2` uses single-file size and coupling to justify L0; `item_6` reports ten executed checks. No independent reviewer or explicit assessment of review benefit is evidenced. External matrix checks passed, but reviewer selection remains unverified.
- blocker: `item_3` identifies missing rounding policy and proceeds with exact-cent work; `item_10` explicitly requests a rounding decision. Agent introduced a temporary rejection behavior and disclosed it; that is not an accepted final rounding policy. No agent reassignment/reuse was exercised.

No observed hard scope or false-success failure within these artifacts. The four runs do not establish multi-agent routing, useful delegation outputs, ownership handoffs, reviewer independence or agent reuse. The independent and authorization tasks were too small to reliably elicit those behaviors; next evaluation should use substantive independent workstreams and a material authorization boundary rather than forcing a prescribed topology.

## Infrastructure attempt

An earlier attempt in `dist/orchestration-20261001-131251/` was interrupted after shell reads were rejected by the managed execution policy. It is excluded from behavioral scoring, not counted as a successful run. Authorized scratch runs then used unrestricted shell execution with approvals disabled and local execpolicy rules ignored. Raw CLI logs also contain rollout-flush warnings; tool execution and terminal turn events were captured.

One run per scenario is initial evidence only. Root model serving was not independently attested beyond requested CLI settings. No repeated-run reliability estimate, production integration, token savings or model comparison is claimed.
