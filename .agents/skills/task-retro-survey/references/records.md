# Records and portable measurements

Each run lives at SKILL_ROOT/runs/YYYY-MM-DD_HHMMSS+OFFSET_short-name_RANDOM/. Timestamps inside files are ISO 8601 with UTC offset. The timezone label is recorded separately. The helper takes an explicit current offset, avoiding an assumption that the execution machine shares the user's timezone; for DST or timezone changes, supply the new offset in observed event timestamps and retain the original start timestamp.

## Intake

Ask missing fields in one compact message, for example in Vietnamese:

> Tên/loại task, mục tiêu và tiêu chí hoàn thành là gì? Spec đã chốt chưa? Bạn kỳ vọng mất bao lâu, có deadline hoặc giới hạn usage không? Nếu có thể, cho mình alias, công cụ/gói và usage ban đầu; mục chưa biết có thể bỏ qua.

task.json schema version 1: run_id, name, started_at, timezone, utc_offset, status, recording_mode, details. Populate details with participant_alias, repository_id, client, plan, task_type, objective, acceptance_criteria, scope, specification_state, expected_elapsed_minutes, deadline, usage_limit, models and evidence_sources. Optional comparison_contract pins task inputs, coding model/effort and acceptance IDs for paired advisory comparisons; see [usage collection](usage-collection.md). Unknown values are null, never fabricated. Models list configured/requested/confirmed values and source for root and children separately. Avoid participant emails, absolute home paths or proprietary task descriptions in files shared with the team.

task.md is the human-readable intake; task.json is canonical. Every update emits an intake_update event so corrections remain visible. Events append rather than replace earlier milestones.

## Milestones

events.jsonl fields: schema_version, run_id, sequence, recorded_at, observed_at, observation_basis, kind, phase, status, actor, note, evidence, data. Basis is live/reported/imported/unknown. observed_at is null when source time is unknown; recorded_at is always the write time. Supply --basis live only when observing an event now. Historical timestamps need a real source; recording a supplied count is not permission to invent agent lifecycle events. kind is one of phase, agent_start, agent_end, blocker, retry, scope_change, model_change, verification, usage, tool_skill, pause, resume, observation_gap, intake_update, completed, amendment. Add observed skills/tools and counts to data without logging routine calls individually. Record zero agents only when the observed interval is complete; otherwise mark unknown/partial.

## Usage evidence

Put usage objects in events of kind usage and summary usage.evidence. Each object includes metric, value, unit, source_type (tool/log/user), source_ref, measured_at, scope (task/account/session/agent/unknown), window_id/reset_at if relevant, and notes. Example: metric subscription_used_percent, value 30, unit percent, scope account, source_type user. API tokens or credits have their own metric/unit and source. Never label a user snapshot tool-confirmed.

Compare percentages only across the same identified account/window with matching units and known reset behavior. Record both snapshots even when comparable, and label differences account-level, attribution unconfirmed unless task isolation is demonstrated. A reset, unknown window or concurrent use prevents a task-cost inference. Cached input may be included in total input; reasoning may be included in output. Root CLI totals may already include children. Preserve the provider's accounting definition instead of summing blindly.

## Final report

summary.json schema version 1 contains run metadata, time_basis and report. Report fields: outcome (criteria with met/unmet/unverified/blocked plus evidence), observations (agents, skills, tools, model transitions), usage (evidence, comparable deltas only when supported, attribution/counter coverage), difficulties, retries_rework, time_breakdown, expectation_comparison, observation_gaps, retrospective (findings and inspected/uninspected categories). The helper calculates recording-interval wall time only; for a retro started after the task, full task duration stays unknown unless timestamped sources establish it. Missing counts remain null. Each finding has severity, category, evidence, impact, proposal, scope_owner, verification_plan and confidence. An empty finding list means none observed within stated coverage, not a comprehensive clean audit.

## Helper examples

Use your shell's quoting rules. Do not place secrets in command arguments. The run name should be short and non-sensitive.

```text
python <SKILL_ROOT>/scripts/survey.py start --task folder-management --timezone Asia/Saigon --utc-offset +07:00
python <SKILL_ROOT>/scripts/survey.py update --run <RUN_DIR> --input <intake.json>
python <SKILL_ROOT>/scripts/survey.py event --run <RUN_DIR> --kind phase --basis live --note "Implementation started"
python <SKILL_ROOT>/scripts/survey.py event --run <RUN_DIR> --kind usage --input <snapshot.json>
python <SKILL_ROOT>/scripts/survey.py finalize --run <RUN_DIR> --status completed --input <report.json>
python <SKILL_ROOT>/scripts/survey.py amend --run <RUN_DIR> --input <corrected-report.json>
```

--input - reads JSON from stdin. Inputs may be temporary files in this run directory, using normal authorized file tools; delete only if user asks or ordinary temporary-file cleanup is explicitly scoped. Event inputs can set phase/status/actor/evidence/data, observation_basis and observed_at. The optional Codex collector reads only explicitly selected rollout files; it does not fetch billing data or scan hidden history. Other clients can follow the Markdown instructions even without their own Skill tool; support means a portable workflow/schema, not universal automatic hooks.
