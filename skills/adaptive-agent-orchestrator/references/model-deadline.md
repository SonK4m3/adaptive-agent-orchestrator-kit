# Resource policy

For coding execution, apply the [DeepSeek-first routing policy](deepseek-first.md) first. The Codex roles, capability examples and topology diagrams below describe planning or Codex fallback; they do not override the coding route or existing model pins.

Priority is fulfillment, then time, then cost. Deadline is optional; never invent one. Record duration versus absolute timestamp and timezone when supplied. A hard budget remains a constraint even though cost ranks third.

## Model choices are initial hypotheses

Current official guidance inspected 2026-10-01 describes Astra for demanding reasoning, Sol for complex work balancing capability/cost, and Luna for lighter bounded tasks. See the source ledger. These descriptions are not measured latency rankings on this user's codebase.

| Work | Initial capability choice | Evidence that justifies a change |
| --- | --- | --- |
| Mechanical edit, deterministic reproduction, targeted lookup | Available economical model | Repeated misunderstanding or a newly ambiguous interface |
| Multi-step feature or cross-file reasoning | Available capable workhorse | Broader coupling or a correctness failure requiring deeper reasoning |
| Ambiguous architecture, difficult root cause, high-risk design/review | Available strongest suitable reasoning model | Stable design permits subsequent bounded work on cheaper agents |
| Tests waiting on CI, network, or hardware | Existing capable executor | Faster model cannot remove external waiting; investigate bottleneck |

Available-model examples, not pins: gpt-6-luna, gpt-6.1-sol, gpt-6-astra. Verify the actual tool schema/account supports an example before using it. Older configured roles can remain valid. No global upgrade is performed by this policy.

Use a supported effort appropriate to the uncertainty. Avoid blanket max settings for lookup, formatting or test execution. More thinking can add delay and tokens; evaluate whether it reduces retries. Keep root's current model unless the user changes the session or an authorized runtime actually supports changing it.

## Three operating modes

- **Standard:** satisfy all acceptance criteria; use a capable root and bounded delegation when beneficial.
- **Deadline:** prioritize the critical dependency chain, reduce handoffs, delegate independent work, and reserve time for integration and verification. A stronger model can reduce rework, but is not assumed faster for every task.
- **Economy:** when timing is flexible, use cheaper models on clear bounded work and fewer redundant investigations. Keep the same acceptance requirements; escalate before repeated low-cost failures consume more total time or money.

Estimate completion from the longest dependent chain plus coordination, integration, and verification, not the sum of all parallel durations. Use measured comparable runs if available; otherwise label the estimate uncertain. Choose the verification reserve from actual required checks, not a universal percentage.

Checkpoint after discovery and integration, and when a material failure changes the estimate. Compare remaining work with remaining time. Remove optional polish first; if must-have work cannot fit, report the conflict immediately and ask the user to choose scope, deadline, or budget. Continue unrelated authorized work.

## Runtime constraints

Custom role files can override requested model/effort. Inspect those bindings before claiming adaptive routing. Use an unpinned role if supported to apply an authorized explicit choice. Never overwrite an existing role or global config just to make a requested topology appear successful.

Default inheritance is a legitimate fallback, but record it honestly. Close completed agents when needed to release capacity. Do not keep spawning equivalent agents after failures.
