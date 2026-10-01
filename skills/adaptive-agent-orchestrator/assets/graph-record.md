# Compact graph record — schema 1

Use when coordination needs an audit trail; a short task can keep the same fields in its acceptance ledger. This is a record, not a workflow engine or permission system. Never invent agent IDs, event times or confirmation evidence.

## Snapshot fields

- schema_version: 1; task_id: stable task identifier; revision: positive integer starting at 1.
- path_case_sensitive: false by default (conservative Windows-compatible collision detection); keep this convention across revisions.
- nodes: nonempty workstream list. Each node has id, role, expertise, output, agent_id (root or actual runtime ID), requirement_ids, read_paths, write_paths, status and evidence (pointer list).
- edges: from/to workstream IDs and kind dependency or verification. Dependency direction is prerequisite to consumer. Only dependency edges must be acyclic.
- criteria: id, outcome, workstream_id, implementation_owner, verification_owner, verification_method, independent (boolean), independence_reason, status and evidence. Owners are recorded actors; a suite or command is a method, not an owner.
- change: null at revision 1. Later revisions include from_revision, to_revision, trigger, obsolete_work_disposition and handoffs. Each handoff has path, from_actor, to_actor, confirmation and evidence.

Node status: pending/running/blocked/completed/cancelled. Pending, running and blocked nodes reserve exclusive write paths; two active nodes cannot reserve the same path even for the same agent. Completed/cancelled nodes require evidence pointers. Criterion status: pending/pass/fail/unrun/blocked; pass requires actual evidence. Task completion and orchestration handling are separate conclusions.

Scope is exact workspace-relative files, not globs/directories. Normalize separators and dot segments; reject absolute paths, drive paths, traversal, glob syntax, trailing dots/spaces and Windows device names. Read paths may overlap. This does not detect symlink aliases or writes outside the workspace, and does not enforce an OS sandbox.

## Revision and handoff

Save the initial snapshot and a new snapshot at meaningful replan checkpoints, not every tool call. Capture changes to requirements, dependencies, assignments, scope and verification. Prefer reuse; add an agent only for a useful independent output or expertise gap.

Confirmation is stopped, completed or handoff_confirmed, with an observed tool/artifact pointer. stop_requested is never sufficient. Releasing ownership and starting a new writer require confirmation first; a JSON value alone does not prove temporal ordering. Preserve obsolete nodes with terminal status/evidence where applicable, and never label ongoing writes cancelled merely because a message was sent.
For a reservation released without a successor, use to_actor: unassigned and confirmation evidence, or retain the old node as completed/cancelled with observed terminal evidence. Compare previous active reservations even if the new writer is already completed; removing the old scope cannot hide an unconfirmed release.

## Small L0 example

```json
{
  "schema_version": 1,
  "task_id": "label-change",
  "revision": 1,
  "path_case_sensitive": false,
  "change": null,
  "nodes": [{"id":"label", "role":"root", "expertise":"text edit", "output":"Ready label", "agent_id":"root", "requirement_ids":["R1"], "read_paths":["label.txt"], "write_paths":["label.txt"], "status":"pending", "evidence":[]}],
  "edges": [],
  "criteria": [{"id":"R1", "outcome":"label reads Ready", "workstream_id":"label", "implementation_owner":"root", "verification_owner":"root", "verification_method":"read final file", "independent":false, "independence_reason":"bounded deterministic edit", "status":"pending", "evidence":[]}]
}
```

From the source checkout/extracted kit package (not this installed skill), run python scripts/validate_graph_record.py SNAPSHOT.json --previous PREVIOUS.json when a previous revision exists. Fixtures are under eval/fixtures/graph-record/. Missing previous snapshots limit the validator to declared structure. Evidence pointers are checked for presence, not truth or accessibility; inspect the actual trace/oracle separately.

## Survey interoperability

Graph revisions describe workstream ownership; task-retro-survey describes observations. When that optional skill is invoked, graph replan corresponds to scope_change/blocker/retry milestones; dispatch/closure to observed agent_start/agent_end; acceptance to verification. Keep the survey's recorded_at/observed_at/source basis separate. Do not fabricate lifecycle from a worker count, automatically activate the survey, duplicate its schema, or apply retrospective proposals while measuring.
