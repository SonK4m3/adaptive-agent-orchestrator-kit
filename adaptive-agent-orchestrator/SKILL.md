---
name: adaptive-agent-orchestrator
description: Choose and adapt Codex subagent workflows for software tasks, prioritizing requirement correctness and completeness, then deadlines, then cost. Use for delegated coding, debugging, refactoring, or orchestration planning; keep bounded work root-only when appropriate.
---

# Adaptive coding orchestration — v2

## Priority contract

Optimize in this order: (1) correct and complete fulfillment of the user's requirements, (2) elapsed time and any explicit deadline, (3) total tokens and money. These are ordered priorities, not weights that let cheap output compensate for missing requirements. Honor explicit hard spending or time limits; if no feasible plan satisfies them, expose the conflict and request a scope/resource decision while continuing independent authorized work.

This skill requests real subagents when the selected topology benefits the task. Diagrams describe possible organization; they are not an executable engine.

## Understand and decompose

For nontrivial work, make a compact acceptance ledger before delegating: requirement ID, observable outcome, responsible workstream, dependencies, verification evidence, and status. Include negative cases and nonfunctional constraints that the user actually requested. Read only relevant source and project instructions. Ask only about missing decisions that materially change behavior or scope; label reversible assumptions.

Separate complexity from independence. Inspect uncertainty, subsystem boundaries, shared mutable state, regression risk, context load, and available tools. Split by independently verifiable outcomes, not number of files or generic role names. Root owns architecture and integration. Keep tightly coupled reasoning and urgent blocking work at root; delegate useful side work that can proceed while root advances the critical path.

## Choose topology and resources

| Level | Initial organization | Selection criterion |
| --- | --- | --- |
| L0 | Root, zero agents | A bounded task or tightly coupled chain is most efficiently completed directly; complexity alone is not a spawn trigger. |
| L1 | Root + one relevant agent | One isolated implementation, discovery, or verification workstream adds value. |
| L2 | Root + two independent agents | Two workstreams have separate outputs and safe ownership. |
| L3 | Necessary agents in stages | Multiple independent slices or material risk justify staged work and independent validation; no fixed agent count. |

Read [patterns](references/patterns.md) for the matching case and [concrete roles](references/roles.md) before choosing a named agent. Read [model and deadline policy](references/model-deadline.md) when choosing resources, dealing with a deadline, or escalating. For unmeasured configurations, treat capability descriptions as hypotheses, not guaranteed speed or success.

Use runtime-supported models and effort settings only. Existing custom roles may pin their model and effort. Do not claim a spawn override defeats such a pin. Where supported and authorized, use an unpinned/default role with a concrete role contract for a different model. Otherwise explain the constraint and choose a feasible route. Record configured, requested, and runtime-confirmed values separately; unknown effective models stay unknown. Never claim to switch the active root by editing configuration.

## Execute bounded work

Give every agent an objective, requirement IDs, exact write ownership or read-only scope, minimal relevant context, interfaces/dependencies, acceptance checks, and return format. Use [work packet](assets/delegation-contract.md) when useful. Do not share the whole chat by default or duplicate the delegated investigation at root.

Spawn independent work before waiting. Stay within the runtime concurrency cap; staged agents are not simultaneous agents. One writer owns a file at a time. Freeze interface contracts before parallel implementation, then root checks the assembled result. Read-only tasks remain read-only even if a diagram has an implementation node.

At an agent failure, new dependency, changed requirement, failed test, or deadline risk, reassess the graph. Reuse an agent when appropriate. Stop obsolete work and record its status using available tools. Add a specialist only for a concrete gap. If the same failed approach produces no new evidence, change the hypothesis, contract, model, or ownership rather than repeating it.

When tools or a requested model are unavailable, report the limitation and use an authorized root fallback where feasible. An explicit user model/resource choice is already authorization within the stated budget and tool limits; ask about missing feasibility decisions, not the same permission again. Never simulate agents or substitute newly created user chats for subagents.

## Verification gate

Map every requested requirement to evidence or an explicit unresolved item. Passing unit tests is not evidence for untested UI, service integration, long-running behavior, or deployment. Verify at the boundary actually affected: original reproduction, contract, rendered interaction, or live workflow as appropriate. Record pre-existing failures separately.

For material security, auth, migration, concurrency, or cross-subsystem regression risk, use an independent reviewer when available and useful. Give the reviewer requirements, artifacts and tests; request its own assessment before showing the implementer's confidence or optional Jev scores. A review complements executable checks.

Resolve material findings, verify fixes, then stop expanding checks once the affected acceptance criteria and required project gates pass. A deadline never turns failed or unrun checks into a pass. If completion is infeasible, report exactly what is complete, unverified, and blocked; seek an explicit scope change rather than silently dropping requirements.

## Evidence and learning

For substantial runs, use [task contract](assets/task-contract.md) and [run record](assets/run-record.md). Report outcomes first, then verification and limits; include topology/model details when requested or when they explain a tradeoff.

Use [evaluation protocol](references/evaluation.md) to compare policies and [source ledger](references/evidence.md) to understand external evidence. Do not claim universal optimality, benchmark parity, or cost savings without comparable measured task outcomes. API dollars, subscription credits, token counts, and elapsed time are separate metrics.

## Optional Jev

Read [Jev boundary](references/jev.md) only when requested or when a working authorized integration exists. Jev advice cannot waive requirements, review, permissions, or runtime constraints. This package does not install a model proxy or silently send source code to a classifier.
