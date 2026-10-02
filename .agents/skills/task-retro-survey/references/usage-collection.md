# Codex collection and paired JEV comparisons

These helpers ship inside this standalone skill. Copy the complete folder,
including scripts and .gitignore, but exclude runs and caches. Python standard
library only; no SDK, credential, network, Codex subprocess or model call.

## Collect the selected session

Identify the target root and the known spawned thread IDs from session metadata or
the task trace. Select their exact rollout files across dates if necessary. The
collector does not search unrelated history or automatically discover omitted
children. Root must be present; unrelated files and conflicting snapshots for one
thread are rejected. Identical duplicate files are counted once.

```text
python <SKILL_ROOT>/scripts/codex_usage.py --root <EXACT_ROOT_ID> --rollout <ROOT.jsonl> --rollout <CHILD.jsonl> --format md
python <SKILL_ROOT>/scripts/survey.py collect-usage --run <RUN_DIR> --root <EXACT_ROOT_ID> --rollout <ROOT.jsonl> --rollout <CHILD.jsonl> --jev-evidence <JEV_EVIDENCE.json>
```

Repeat --rollout or --jev-evidence for additional explicit files. Omit the JEV flag
for a baseline. JEV-only import is supported without root/rollout flags. Failed
requests retain unknown token usage, not zero. When collecting again, include all
sources needed for the latest snapshot: it replaces the reporting view, not the
old artifact. Imports create `usage-<UUID>.json` and an imported usage event in
the run; source logs are never modified. Closed runs refuse imports; corrections
require a reviewed amendment. Finalize/amend automatically include the latest
snapshot under `report.usage.measured_channels` without summing earlier imports.

## Counter semantics and privacy

Only metadata identifiers, CLI version, model/effort context, timestamps, usage,
window snapshots and source hashes/pointers are exported. No messages, prompts,
source, working-directory paths, instructions or raw JEV payloads are copied.
Source filenames and thread IDs remain in evidence; review them before sharing.
Collector hashes describe the bytes observed during reading; an active session
can still append afterward. These are snapshots, not a log freeze.

Per-response records are grouped by observed turn-context model/effort. Stable
response IDs allow replay deduplication. Equal timestamp/counters without an ID
are preserved and flagged as possible replay, not silently dropped. Missing
counter fields stay null. Counter decreases and mismatch between response sums
and a cumulative snapshot are flagged: inherited context, resets or missing
records need investigation. Last-cumulative fallback remains unassigned to a
model; the last model does not explain a session's entire history.

Input includes cached input; reasoning can be a subset of output. Never add those
subsets again. Root/child counter overlap and complete child discovery are not
established, so `usage_total` and combined cost stay null. Rows remain useful
diagnostics, not a billing invoice. Guardian/approval-review threads are retained
as a separate category rather than silently excluded. Model bindings come from
turn-context logs, not independent confirmation of backend serving.

JEV evidence is imported from the explicit smoke's `evidence.json`. Report
returned model, input/output usage, source hash, attempt/retry counts and measured
timestamp separately. Exact duplicate evidence bytes are imported once. Imported
files are not independently authenticated API receipts; billing cost stays unknown.
An omitted request is not proof of no request. Do not combine API usage with
Codex subscription usage. Account-window snapshots have unknown task attribution;
the collector does not calculate a 5h/7d delta or assume fixed window duration.
Time between session timestamps is not active work and may span multiple tasks.

## Prepare a fair comparison first

Use a fresh session and isolated equivalent workspace per arm, same task spec,
prompt, starting fixture, tools, permissions, root/role model and reasoning effort,
acceptance checks and hard deadline. Only advisory availability differs. State
cache conditions, concurrency, Codex version and any other differences; never
change the model pins to make one arm cheaper. Run explicit approved benchmarks
only; configuring measurement does not authorize inference. Preserve independent
verification requirements in both arms. Do not infer reliability from one pair.

Store a `comparison_contract` through the survey intake update. Use real SHA-256
hashes of the same spec, prompt and fixture, not invented placeholders:

```json
{
  "comparison_contract": {
    "spec_sha256": "<real 64-character lowercase hash>",
    "prompt_sha256": "<real 64-character lowercase hash>",
    "fixture_sha256": "<real 64-character lowercase hash>",
    "coding_models": {
      "root": {"model": "<fixed model>", "effort": "<fixed effort>"},
      "worker": {"model": "<fixed model>", "effort": "<fixed effort>"}
    },
    "acceptance_ids": ["R1", "R2"],
    "jev_enabled": false
  }
}
```

Use true in the advisory arm. Include every coding role that can be observed,
not just spawned roles in one arm. Hashes refer to original inputs, never changed
outputs. In final report, use `outcome.criteria` entries with `id`, `result`
(`met`, `unmet`, `unverified`, `blocked`) and nonempty evidence pointers.

```text
python <SKILL_ROOT>/scripts/compare_usage.py --baseline <BASELINE_SUMMARY.json> --advisory <ADVISORY_SUMMARY.json>
```

The read-only gate rejects changed hashes/models/efforts/acceptance IDs, failed or
unverified criteria, missing observed coding bindings, wrong arms and missing
successful JEV evidence in the advisory arm. A deterministic arm that skipped
all classification is not evidence of actual JEV use. Success means only
`eligible_for_review`: task evidence, correct isolation, source coverage, cache
conditions and comparable counters still require inspection. The gate does not
execute tests, attest evidence truth, calculate savings or compare account credits.
Report per-thread diagnostics and API counters separately until accounting supports
an aggregate. Prioritize complete acceptance over lower token counts.
