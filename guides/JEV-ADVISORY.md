# JEV workflow advisory (v1)

JEV recommends the next bounded workstream; root owns the graph and final decision.
This is not a model-routing proxy. No helper dispatches, stops, hands off or changes
the models of coding agents. Small tasks remain root-only; advisory is optional,
not another mandatory per-turn call.

The flow is:

```text
root state + candidate contracts
  -> deterministic scope / ownership / runtime / budget filter
  -> 0 candidates: report blocked; 1 candidate: skip JEV
  -> 2+ candidates: optional Choice advisory
  -> validate response and state fingerprint
  -> root accepts / overrides / falls back
  -> root dispatches separately, verifies acceptance and records actual evidence
```

## Offline use

From a source checkout or extracted kit, use the package-level helper:

```sh
python scripts/jev_advisory.py prepare --state eval/fixtures/jev-advisory/state.json --output dist/jev-request.json
python scripts/jev_advisory.py record --state eval/fixtures/jev-advisory/state.json --root-decision eval/fixtures/jev-advisory/root-decision.json --output dist/jev-record.json
```

Create the output parent first. Existing output files are never overwritten.
`record` without `--response` records a root fallback; with a normalized response
it checks candidate IDs, probabilities, policy version and the exact state hash.
The request dossier is the kit's own contract, not a TypeSafe HTTP request.

The [state fixture](../eval/fixtures/jev-advisory/state.json) is the complete v1
schema. Unknown fields are rejected. Text fields are bounded to 1000 characters,
lists to 32 entries and CLI inputs to 64 KiB. Paths are exact workspace-relative
files, normalized case-insensitively for portable ownership checks. `active_agents`
excludes root and counts read-only agents too. `owners` includes writers still
pending, running or blocked; remove them only after observed completion/stop or
confirmed handoff. Conflicting current ownership must be reconciled before advice.
These declarations are root-supplied facts, not OS-enforced locks or discovered
runtime capabilities.

Candidate actions are `root`, `reuse`, `spawn`, `revise` and `stop`; roles are
`worker`, `explorer`, `researcher`, `architect` and `verifier`. New agents require
an available role, capacity and a declared independent output. Only workers can
declare writes. Review-mode candidates cannot write. Contract revisions and stops
are root-owned, read-only advice. At a hard stop or zero remaining time only stop
is eligible. There is no `done` candidate and scores cannot waive acceptance gaps.
Role labels do not create new TOML agents: root maps a verifier to an available
tester/reviewer as appropriate, or records a capability gap.

Normalized response fields:

```text
schema_version: 1
policy: workflow-advisory-v1
state_fingerprint: hash from prepare
choice: an eligible candidate ID
confidence: finite number from 0 to 1
probabilities: every eligible ID, finite values from 0 to 1 summing to 1
```

Root decision fields are `choice`, `reason`, `evidence` (a list of pointers).
`record` stores accepted/overridden/fallback, UTC timestamp and `executed:false`.
Imported responses have unverified provenance. Evidence pointers and acceptance
gaps are not independently validated. No runtime outcome is inferred.

## Explicit live smoke

The separate helper makes at most one paid evaluation request, timeout 20 seconds,
zero automatic retries, to the fixed TypeSafe endpoint. It refuses redirects.
It reads `TYPESAFE_API_KEY` from the process environment or an explicitly named
dotenv file, without logging the credential. It does not load global Codex config.

```sh
python scripts/jev_live_smoke.py --state eval/fixtures/jev-advisory/state.json --root-decision eval/fixtures/jev-advisory/root-decision.json --output-dir dist/jev-live-new --env-file .env --allow-live-send-state
```

Review/redact the state before consent: summaries and file names can still contain
private information. The helper sends only summary, trigger, mode, acceptance gaps,
remaining time and eligible candidate contracts. It never reads source code or chat
logs. The flag is an explicit send gate, not an automatic authorization for later
tasks. `.env` and generated `dist/` evidence are ignored by Git. Protect artifact
storage separately if using private state. Keep the root decision independent of
classifier scores; this smoke takes it before the request and compares afterward.

It writes request, decision record and sanitized API evidence in a new directory.
Evidence includes returned model, token usage, elapsed wall time, attempts and error
category; API errors do not log response bodies or headers. A failed request records
fallback, not successful inference. No retry is implied. `cost_usd` stays unknown
unless billing evidence is obtained; API tokens are not Codex subscription credits.

The transport follows [TypeSafe's HTTP API](https://docs.typesafe.ai/api), pinning
`jev-1.13.0` rather than a moving alias. It uses one Choice question for the next
workstream, not a cross-product of topology/model/effort decisions. Multi-question
diagnostics, caching across sessions and automatic graph dispatch are not included.
For small or deterministic decisions, skip classification entirely. Reuse only
while the exact state and candidate contracts remain unchanged; reassess at blockers,
scope changes, ownership changes or failed verification, not every tool call.

## Evidence boundary

The live smoke validates transport -> typed answer -> root decision on a synthetic
state. It does **not** execute the graph, prove root skill compliance in another
session, establish classifier accuracy or demonstrate savings. Before adopting
automatic routing, compare matched real tasks with and without advisory, keeping
coding models/efforts fixed and measuring complete acceptance, scope breaches,
root overrides, all retries, elapsed time and total costs separately.
