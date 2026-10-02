# Codex usage collector and retro import — 2026-10-02

Implemented as self-contained helpers in the separately shared
`.agents/skills/task-retro-survey/` skill. No global Codex configuration,
authentication file, source rollout or model pin was changed.

Validation:

- 26 survey/collector/comparison tests passed. Synthetic tests cover read-only
  bytes/hashes, prompt/source redaction, unknown counters, partial records,
  cumulative decreases, ID-based deduplication, possible replay without IDs,
  parent grouping, unrelated sessions, guardian retention, import/finalize,
  repeated imports, closed-run protection, copied-skill CLI portability outside
  the repository and fixed-contract comparison gates.
- Skill Creator quick validation passed. Skill-local runs are ignored by Git.
- Read the explicit real root and one known child rollout, CLI version 0.159.2.
  Metadata contains shared session_id and parent_thread_id. This does not establish
  discovery of all children or compatibility with every Codex release.
- Imported those two selected thread snapshots and the existing JEV smoke into a
  real survey run, finalized it and inspected automatic attachment in summary.json.
  Coding threads: 2. JEV evidence records: 1, with 597 input and 40 output tokens.
  No new TypeSafe request or coding-model benchmark was made.
- The summary keeps combined tokens/cost null and explicitly labels the Codex
  counters as long-lived session observations, not this implementation task's cost.

Local ignored run:
`task-retro-survey/runs/2026-10-02_104017+0700_codex-usage-collector-smoke_67e253c2/`
under the skill folder. It contains immutable usage snapshot, events and summaries.
No source messages, prompts, working-directory paths or raw JEV payload are copied.
Source basenames/IDs remain evidence; review them before sharing.

The paired-run helper checks declared input hashes, acceptance IDs, coding
model/effort bindings observed in turn context, distinct baseline/advisory arms and
evidenced acceptance outcomes. Eligible means ready for human evidence review,
not a proven benchmark or cost-saving result. All actual paired task runs,
cross-thread accounting and task-specific credit attribution remain unverified.
