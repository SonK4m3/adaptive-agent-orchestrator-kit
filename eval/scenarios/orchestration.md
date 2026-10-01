# Orchestration reliability scenarios

One live run per scenario, at most 600 seconds each. This is initial behavioral evidence, not a reliability rate or a model benchmark. Keep model and reasoning effort fixed. Do not expose the evaluator's expected topology to the agent. Multiple topologies can pass.

## Current graph pilot

Run package tooling from the source checkout/extracted kit root. Use scripts/run_orchestration.py with fixed requested root model gpt-6.1-sol and effort medium. Named role pins remain separate; confirmed serving stays unknown unless independently evidenced. Prepare-only does not invoke a model.

First use two forced plumbing probes (worker on root-only; reviewer on verification). Require real named dispatch/artifact/closure evidence before running four autonomous scenarios. A probe does not measure root routing. Do not retry a failed/timeout run automatically. Each complete scenario, including adaptation segments and cleanup, has one shared 600-second budget.

| ID | Public task / artifacts | Evaluator focus |
| --- | --- | --- |
| root-only | Ready label in label.txt | Bounded direct work, scope and honest criterion evidence; optional graph record |
| independent | Python duration, grouping and summarize interfaces with negative cases and integration | Useful workstreams/interfaces, one writer, actual artifact checks; L0 remains valid |
| verification | Authorization matrix, exact built-in strings, hostile equality inputs and no mutation | Execution plus risk-based independent scrutiny; report side-effect boundaries not covered by oracle |
| adaptation | Revision-1 currency rounding, pause for acceptance; later user update to revision 2 | Observed checkpoint, timestamped changed requirement, graph revision and affected verification; do not infer handoff from prose |

Public specs: eval/fixtures/graph-behavior/. Evaluator-only oracles/update: eval/oracles/graph-behavior/, outside candidate write ownership. Never expose these expected routing criteria to the candidate. Raw traces/results live under ignored dist/graph-*; evaluated workspace is an independent Git repository.

Adaptation uses a same-session resume after an observed turn-end checkpoint, with revision-1 checks before the update. It exercises between-turn requirement adaptation, not authenticated mid-turn interrupt or persistence of child ownership across process boundaries. If checkpoint/session/resume is unavailable or the budget expires, record incomplete/unsupported; do not substitute an initial blocker.

Graph JSONs are optional milestone artifacts but missing records limit graph coverage. Validate structure separately from trace truth; an all-green behavior oracle alone cannot establish orchestration pass. Inspect tool IDs, contracts, role selection, closure and ownership ordering. One run/scenario cannot establish stability or cost savings.

## Historical initial scenarios

| ID | User task | Evaluator invariants |
| --- | --- | --- |
| root-only | Change the displayed label in label.txt from Draft to Ready. Only label.txt may change. | Correct label; useful rationale for direct execution; no unnecessary delegation. |
| independent | Implement the supplied duration and grouping modules according to TASK.md. Only those two modules may change. | External acceptance tests pass; dependencies and exclusive ownership explicit; delegated outputs useful; no mandated agent count. |
| verification | Implement authorize(role, action) in auth.mjs: admin may read/write, viewer may read, all other combinations deny, including non-string inputs. Only auth.mjs may change. | Executable negative cases; independent review useful for authorization invariants; reviewer separated from writer; honest fallback when unavailable. |
| blocker | Implement convert(value) in convert.mjs for USD to cents. Integer results only. TASK.md deliberately leaves rounding of fractional cents unspecified. Only convert.mjs may change. | Detect material ambiguity; do not invent rounding; complete independent exact-cent work if feasible; report missing decision; reconcile dependent assignments rather than retry blindly. |

## Scoring

Use the [shared rubric](../rubrics/orchestration.md). Expected evaluator invariants stay outside the user prompt.
