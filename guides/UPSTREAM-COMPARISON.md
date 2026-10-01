# Upstream comparison

This guide records deliberate differences between this kit and [donvito/codex-astra-luna-orchestrator](https://github.com/donvito/codex-astra-luna-orchestrator), preserved through the v2.2.0 layout migration.

## Short version

This kit retains upstream bounded-work discipline while changing the routing decision. Upstream's Pro skill has a broad delegation gate: multi-file work, repository exploration, separate implementation and verification context, current external facts, material review, and similar conditions require a real spawn. This kit selects the smallest useful topology from evidence. Complexity or file count alone does not mandate a spawn, and a bounded task may remain root-only.

| Concern | Observed upstream contract | Local policy / preserved difference |
| --- | --- | --- |
| Root ownership | Root understands the goal, chooses architecture and parallelism, spawns, resolves conflicts, integrates, verifies, and reports. | Preserved. Root owns architecture, integration, final diff, and completion claims. |
| Bounded delegation | Objective, scope, context, constraints, deliverable, acceptance criteria, and file ownership are explicit. | Preserved and strengthened with requirement IDs, exact read/write scope, dependencies, verification owner, blocker handling, and return format. |
| Routing gate | Broad conditions generally require delegation and a real spawn. | Adaptive: independence, dependencies, uncertainty, shared state, context load, risk, deadline, and verification value are considered together. |
| Parallelism | Independent tasks start before waiting; dependent work is serialized; workers do not share files. | Preserved. One writer owns a path; ownership and interfaces are frozen before parallel implementation. |
| Role model | Stable explorer, worker, tester, reviewer, and researcher roles are assigned by work type. | Preserved. Add task-specific expertise, scope, output, and acceptance criteria instead of permanent technology roles. |
| Verification | Tester executes; reviewer independently checks correctness, regressions, security, assumptions, and coverage. | Preserved, with criterion ownership. Independent review is selected by risk, not mechanically for every worker. |
| Adaptation | Failure, escalation, and completion gates exist, but the default gate/profile topology is prescriptive. | Reuse or revise existing work first; add a role only for a concrete expertise gap or independent output. |
| Resources | Profiles bind models, reasoning effort, and concurrency. | Profiles configure resources, not topology. A profile does not prove which roles will run; effective resources require runtime evidence. |

## Contracts retained from upstream

- Root owns overall direction and must not offload architecture to a subagent.
- Each work packet has one concrete objective, bounded scope, useful context, constraints, deliverable, acceptance checks, and file ownership where known.
- Independent work may run in parallel; dependent work is serialized; one writer owns each file or subsystem unless root coordinates otherwise.
- Subagents return evidence, paths, commands, results, risks, and blockers; they do not silently expand scope.
- Failed delegation is reported as failed or handled through an explicit, evidenced fallback; it is never silently reported as success.

These are safe-work boundaries, not a fixed team shape.

## Local adaptive routing

1. Map outcomes, dependencies, uncertainty, shared state, regression risk, context load, deadline, and verification needs.
2. Use L0 root-only when delegation adds no useful independent output.
3. Use the smallest L1/L2/L3 topology when bounded independent output materially improves the result.
4. Start independent streams before waiting, then integrate at root.
5. On a blocker or failed check, revise ownership/contracts, reuse useful work, or add only the missing capability.
6. Close every criterion with execution evidence or an explicit unrun/blocked explanation.

A diagram, role TOML, or profile is not an executable workflow and does not prove dispatch.

## Failure and verification rubric

The local evaluation scores routing, assignment, coordination, adaptation, verification, and reporting. Scores cannot offset a hard failure:

- out-of-scope edit;
- false success, delegation, or test claim;
- omitted mandatory requirement;
- unresolved ownership collision; or
- unsupported completion.

Timeout is incomplete, never pass. An honestly detected missing decision is a valid orchestration result, but task completion remains blocked. Unknown child model or effort prevents a controlled all-agent resource comparison. Behavioral runs are evidence about tested traces only, not a reliability rate, benchmark parity claim, or production-readiness claim.

Every criterion has a verification owner: the worker for a narrow static criterion, the tester for executed behavior, or an independent reviewer when assumptions, regressions, security, or missing coverage make separation useful. Record the choice and risk rationale in the contract/run record.

## Installer and recovery boundary

Upstream is observed to install a selected project profile into a target repository's .codex/, .agents/, and AGENTS.md, preserving existing AGENTS.md content and asking before overwriting component files. Its README describes profiles and target-project copying; this guide does not infer an upstream receipt, hash, or rollback contract from that description.

The local installer has a separate safety contract:

- installs one or both self-contained skill entrypoints and optionally namespaced ao_*.toml roles;
- validates the release manifest and staged tree hashes before replacement;
- records hashes only for managed components in .adaptive-agent-orchestrator/install.json;
- uses recoverable backups and receipts for replacement, uninstall, and restore;
- refuses to guess without a receipt, and refuses modified managed content without --force; and
- validates backup receipt paths, preserves current contents in a pre-restore safety backup, and restores only receipt-listed components.

These receipt and backup guarantees are local implementation claims backed by local installer/tests, not claims about upstream.

## Entrypoints, optional roles, and layout

Both local entrypoints are supported:

- $adaptive-agent-orchestrator
- $astra-orchestrator

They carry equivalent adaptive guidance. Roles are optional; either skill remains usable with default runtime subagent types when role files are absent or unavailable. Installing both aliases does not imply two topologies.

The layout is:

    profiles/
    guides/
    skills/                 # shared, self-contained aliases
    scripts/
    tests/
    eval/                   # behavioral evaluation
    profiles/adaptive/codex/agents/

Role definitions live under profiles/adaptive/codex/agents/. Both resource profiles share these bindings and the skills/ entrypoints. See [profiles](PROFILES.md) and [migration](MIGRATION.md).

## Sources inspected and limits

Local:

- guides/ORCHESTRATION-POLICY.md, the current successor to the requested docs/ORCHESTRATION-RELIABILITY.md;
- skills/adaptive-agent-orchestrator/SKILL.md and skills/astra-orchestrator/SKILL.md;
- skills/*/assets/{task-contract,delegation-contract,run-record}.md;
- skills/*/references/{patterns,evaluation,evidence,model-deadline,roles}.md;
- guides/INSTALLATION.md;
- scripts/manage.py, scripts/setup.py, tests/test_manage.py, and tests/test_setup.py;
- eval/scenarios/orchestration.md and docs/validation/ORCHESTRATION-RUN-2026-10-01.md.

Upstream:

- [Astra Pro SKILL.md](https://github.com/donvito/codex-astra-luna-orchestrator/blob/main/profiles/pro/agents/skills/astra-orchestrator/SKILL.md);
- [upstream README](https://github.com/donvito/codex-astra-luna-orchestrator/blob/main/README.md);
- [upstream setup.ps1](https://github.com/donvito/codex-astra-luna-orchestrator/blob/main/setup.ps1).

Runtime success, effective model selection and comparative reliability require direct execution evidence; source inspection alone does not establish them.

