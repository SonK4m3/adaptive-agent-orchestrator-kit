---
name: adaptive-agent-orchestrator
description: Hybrid coding orchestration: default to DeepSeek-first delegation with Astra/Luna fallback. Coordinate scope, exclusive ownership and independent verification; adapt topology to the task.
---

# Adaptive coding orchestration — v3 routing policy

## Model routing and delegation

Keep the topology adaptive: L0 root only; L1 one useful worker or specialist; L2 independent workstreams; L3 staged coordination for material complexity or risk. A topology level describes workstreams, not a required number of Codex subagents. Zero children is valid.

For implementation, first check task constraints and execution capability, then task clarity, risk, and whether delegation provides a real benefit. If a task is tiny, tightly coupled, sensitive, or delegation adds overhead, root may implement directly. When implementation is clear and external sharing is authorized, DeepSeek is the default implementation worker through the existing wrapper. Root may call it directly; no Luna supervisor is required. Larger work may be split into bounded DeepSeek tasks, sequentially when they depend on each other and in parallel only when ownership and outputs are independent. See [Model Routing & Delegation Policy](references/deepseek-first.md).

Use Luna exploration or research only when resolving uncertainty can change the implementation or requires current external facts. Use Astra for material architecture or independent review risk. Specialists are optional and demand-driven. Root retains scope, integration, diff review, and final acceptance regardless of its configured model.

## Invocation and output contract

Consider this workflow without requiring an explicit invocation when coordination adds value. Skill selection is not a requirement to spawn agents. For work that stays in Codex, small or tightly coupled tasks can remain at root (L0); no graph, contract file, topology announcement or separate report is mandatory. Still give a concise outcome, actual checks and material limitations. Do not create coordination artifacts just to demonstrate skill use.

Inputs are the user's task, relevant project constraints, acceptance requirements and available runtime capabilities. When delegating, root briefly explains why the topology fits and each agent's concrete output and scope. Use graph records only to track coordination dependencies, ownership or handoffs, or when an audit is requested; a requested audit may also cover L0. Keep task status and missing evidence visible without prescribing a report file.

The adaptive-agent-orchestrator and astra-orchestrator entrypoints share this policy; load only the selected entrypoint. Survey/retro is a separate workflow: do not activate it automatically. This skill does not authorize configuration changes, external writes or inference benchmarks beyond the user's task.

## Priority contract

Optimize in this order: (1) correct and complete fulfillment of the user's requirements, (2) elapsed time and any explicit deadline, (3) total tokens and money. These are ordered priorities, not weights that let cheap output compensate for missing requirements. Honor explicit hard spending or time limits; if no feasible plan satisfies them, expose the conflict and request a scope/resource decision while continuing independent authorized work.

This skill requests real subagents when the selected topology benefits the task. Diagrams describe possible organization; they are not an executable engine.

## Understand and decompose

For nontrivial work, make a compact acceptance ledger before delegating: requirement ID, observable outcome, responsible workstream, dependencies, verification evidence, and status. Include negative cases and nonfunctional constraints that the user actually requested. Read only relevant source and project instructions. Ask only about missing decisions that materially change behavior or scope; label reversible assumptions.

Use a compact [graph record](assets/graph-record.md) when coordination needs an auditable snapshot. Nodes are workstreams with concrete outputs, not agents; root or a real agent ID is the assignee. Distinguish dependency from verification edges, implementation from verification owners, and node state from criterion result. L0 needs no synthetic child. Record milestones and replan deltas, not every tool call.

Separate complexity from independence. Inspect uncertainty, subsystem boundaries, shared mutable state, regression risk, context load, and available tools. Split by independently verifiable outcomes, not number of files or generic role names. Root owns architecture and integration. Keep tightly coupled reasoning and urgent blocking work at root; delegate useful side work that can proceed while root advances the critical path.

## Choose topology and resources

| Level | Initial organization | Selection criterion |
| --- | --- | --- |
| L0 | Root, zero agents | A bounded task or tightly coupled chain is most efficiently completed directly; complexity alone is not a spawn trigger. |
| L1 | Root + one relevant agent | One isolated implementation, discovery, or verification workstream adds value. |
| L2 | Root + two independent agents | Two workstreams have separate outputs and safe ownership. |
| L3 | Necessary agents in stages | Multiple independent slices or material risk justify staged work and independent validation; no fixed agent count. |

For straightforward L0 work, skip the pattern catalog and role bindings. Read only the matching section of [patterns](references/patterns.md) when a coordination pattern needs clarification; do not load all diagrams by default. Read [concrete roles](references/roles.md) before selecting a named agent, and [model and deadline policy](references/model-deadline.md) when choosing resources, handling a deadline or escalating. Load graph schemas and packet templates only when producing the corresponding artifacts. For unmeasured configurations, treat capability descriptions as hypotheses, not guaranteed speed or success.

Use runtime-supported models and effort settings only. Existing custom roles may pin their model and effort. Do not claim a spawn override defeats such a pin. Where supported and authorized, use an unpinned/default role with a concrete role contract for a different model. Otherwise explain the constraint and choose a feasible route. Record configured, requested, and runtime-confirmed values separately; unknown effective models stay unknown. Never claim to switch the active root by editing configuration.

## Execute bounded work

When delegating, state briefly why this topology fits the task and the concrete output each agent contributes. Multiple topologies may be valid; file count and complexity alone do not require delegation. Keep foundational roles stable and specialize expertise, scope and outputs in each work packet rather than creating a permanent role for every technology.

Assign a verification owner to each acceptance criterion. Testers establish behavior through execution; reviewers independently examine assumptions, regressions and missing coverage. Select independent verification by risk, not mechanically for every worker. If a useful required role is unavailable, record the fallback and missing evidence without inventing dispatch.

For coding implementation, follow the [Model Routing & Delegation Policy](references/deepseek-first.md) to choose root-direct work, useful exploration, direct DeepSeek implementation, or an authorized Codex fallback. DeepSeek is the preferred implementation worker when the task is clear, delegation adds value, and execution is feasible; it is not mandatory for trivial or unsuitable tasks. Root owns requirements, scope, planning, integration, diff review, and final acceptance regardless of its configured model. Root may invoke the existing wrapper directly; no Luna supervisor is required. Select any Codex fallback or specialist by its actual configured role and model pins, not by assuming a particular model is Root. Preserve the active authorized cwd, independently verify changed paths and tests, and keep repository privacy restrictions and model configuration unchanged.

Reassess on blockers, ownership conflicts, new requirements, failed verification or deadline risk. Prefer revised contracts and existing agents; add a specialist only for a new independent output or concrete expertise gap. Stop or reassign obsolete work and update ownership before writers resume. Require observed stop/completion or acknowledged handoff evidence before a new writer takes ownership: a stop request does not prove writes ceased. Retain obsolete-work disposition and revision pointers when a graph record is in use. If a failed approach yields no new evidence, change the hypothesis, contract, resources or ownership rather than repeating it.

Give every agent an objective, requirement IDs, exact write ownership or read-only scope, minimal relevant context, interfaces/dependencies, acceptance checks, and return format. Use [work packet](assets/delegation-contract.md) when useful. Do not share the whole chat by default or duplicate the delegated investigation at root.

Spawn independent work before waiting. Stay within the runtime concurrency cap; staged agents are not simultaneous agents. One writer owns a file at a time. Freeze interface contracts before parallel implementation, then root checks the assembled result. Read-only tasks remain read-only even if a diagram has an implementation node.

When tools or a requested model are unavailable, report the limitation and use an authorized root fallback where feasible. An explicit user model/resource choice is already authorization within the stated budget and tool limits; ask about missing feasibility decisions, not the same permission again. Never simulate agents or substitute newly created user chats for subagents.

## Verification gate

Map every requested requirement to evidence or an explicit unresolved item. Passing unit tests is not evidence for untested UI, service integration, long-running behavior, or deployment. Verify at the boundary actually affected: original reproduction, contract, rendered interaction, or live workflow as appropriate. Record pre-existing failures separately.

For material security, auth, migration, concurrency, or cross-subsystem regression risk, use an independent reviewer when available and useful. Give the reviewer requirements, artifacts and tests; request its own assessment before showing the implementer's confidence or optional Jev scores. A review complements executable checks.

Resolve material findings, verify fixes, then stop expanding checks once the affected acceptance criteria and required project gates pass. A deadline never turns failed or unrun checks into a pass. If completion is infeasible, report exactly what is complete, unverified, and blocked; seek an explicit scope change rather than silently dropping requirements.

## Evidence and learning

Use [task contract](assets/task-contract.md) and [run record](assets/run-record.md) when substantial coordination needs durable tracking or the user requests those artifacts; their files are not mandatory for every task. Report outcomes first, then verification and limits; include topology/model details when requested or when they explain a tradeoff.

Read [evaluation protocol](references/evaluation.md) only for requested policy comparisons or benchmarks, and [source ledger](references/evidence.md) when assessing external evidence. Do not run a benchmark merely to apply this skill. Do not claim universal optimality, benchmark parity, or cost savings without comparable measured task outcomes. API dollars, subscription credits, token counts, and elapsed time are separate metrics.

## Optional Jev

Read [Jev boundary](references/jev.md) only when requested or when a working authorized integration exists. Jev advice cannot waive requirements, review, permissions, or runtime constraints. This package does not install a model proxy or silently send source code to a classifier.
