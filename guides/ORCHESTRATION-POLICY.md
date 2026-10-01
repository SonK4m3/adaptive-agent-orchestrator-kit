# Reliability policy decisions

Agreed 2026-10-01 (Asia/Saigon).

Root chooses topology based on useful independent outputs and verification risk. Neither complexity nor file count alone forces delegation. Before execution, explain the topology briefly and specify each agent's useful contribution.

Keep foundational roles stable. Specialize expertise, acceptance criteria, scope and deliverables in delegation contracts. Root owns architecture and integration. Each criterion has a verification owner. Tester executes behavior; reviewer independently assesses assumptions, regression and missing coverage. Independent verification is selected by risk.

On blockers, ownership conflict, changed requirements or failed verification, revise the graph and contracts. Prefer reuse before spawning a new agent; add only for an independent output or concrete expertise gap. Stop or reassign obsolete work and reconcile ownership before resuming writes. Unavailable roles require an explicit fallback and evidence gaps.

Use [scenarios and rubric](../eval/scenarios/orchestration.md) to assess multiple valid topologies. Mandatory omission, scope breach or unsupported success fails the run regardless of diagnostic scores. A correctly detected missing decision can pass orchestration handling while task completion remains blocked.

Use [compact graph records](../skills/adaptive-agent-orchestrator/assets/graph-record.md) for coordination checkpoints: workstreams are nodes, actors are assignees, dependency and verification edges are distinct. Save replan deltas and observed handoff confirmation before a new writer starts. The structural validator checks IDs, cycles, exact-file collisions and required evidence pointers; it does not attest their truth or enforce runtime isolation.

The first experiment is one run per scenario with a 600-second limit each, fixed requested model/effort, and raw trace review. Preserve failed infrastructure attempts separately. Do not infer reliability rates, effective child models or production readiness from four synthetic runs.

Reference: [upstream orchestration skill](https://github.com/donvito/codex-astra-luna-orchestrator/blob/main/profiles/pro/agents/skills/astra-orchestrator/SKILL.md). Adopt bounded contracts, root responsibility, one writer and dependency-aware parallelism. Retain adaptive routing rather than upstream's broad mandatory-delegation gate. Resource profiles were added in v2.2.0; model optimization remains outside this iteration. See [profile boundaries](PROFILES.md).
