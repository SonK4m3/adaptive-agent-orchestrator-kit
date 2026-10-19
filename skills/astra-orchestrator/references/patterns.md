# Coding orchestration patterns — 10 diagrams

For coding execution, apply the [DeepSeek-first routing policy](deepseek-first.md) first. The Codex roles, capability examples and topology diagrams below describe planning or Codex fallback; they do not override the coding route or existing model pins.

Choose the smallest useful organization. Dashed edges are optional or advisory. Roles are assignments, not model pins. Every diagram inherits SKILL.md scope and verification rules.

These are organization examples, not live graph snapshots. For observed workstream IDs, agent assignments, ownership and replan deltas use the [graph record](../assets/graph-record.md); distinguish dependency edges from verification edges. Read only the matching case when possible.

## 1. Quality-first routing

```mermaid
flowchart TD
  A[Task and source of truth] --> B[Acceptance ledger and dependencies]
  B --> C{Independent useful work?}
  C -- None --> D[L0 root]
  C -- One --> E[L1 focused]
  C -- Two --> F[L2 parallel]
  C -- Several or staged risk --> G[L3 staged]
  D --> H[Choose supported resources for time then cost]
  E --> H
  F --> H
  G --> H
  H --> I[Execute and verify requirements]
  I --> J{All required outcomes evidenced?}
  J -- Yes --> K[Deliver]
  J -- No --> L[Repair or disclose concrete blocker]
  L --> B
```

## 2. L0 — small edit or tightly coupled reasoning

Use for three trivial CSS files just as readily as one; file count is not the criterion.

```mermaid
flowchart LR
  A[Root understands requirement] --> B[Root inspects and changes]
  B --> C[Targeted check]
  C --> D[Requirement evidence]
```

## 3. L1 — one bounded specialist

Root can advance independent work while the specialist works. A small task with no useful side work may stay L0.

```mermaid
flowchart TD
  A[Root defines question and scope] --> B[ao_explorer or ao_worker]
  A --> C[Root handles independent main work]
  B --> D[Root integrates result]
  C --> D
  D --> E[Verify acceptance]
```

## 4. L2 — parallel slices after interface agreement

Use for two independent components. Shared interface changes are agreed before workers start.

```mermaid
flowchart TD
  A[Root freezes interface and ownership] --> B[ao_worker or ao_worker_complex: slice A]
  A --> C[ao_worker or ao_worker_complex: slice B]
  B --> D[Root integrates]
  C --> D
  D --> E[Boundary and end-to-end checks]
  E --> F[Update acceptance ledger]
```

## 5. L3 — high-risk staged change

Use for auth, migrations, concurrency or broad contract changes when independent scrutiny adds value. For audits, all inspection stages stay read-only and implementation nodes are omitted.

```mermaid
flowchart TD
  A[Root defines invariants] --> B[ao_explorer: affected flows]
  A --> C[ao_researcher: unresolved external contract]
  B --> D[Root approves design and ownership]
  C --> D
  D --> E[Workers: disjoint slices]
  E --> F[Root integrates]
  F --> G[ao_tester: regression evidence]
  F --> H[ao_reviewer: independent assessment]
  G --> I[Root resolves findings]
  H --> I
  I --> J[Final boundary verification]
```

## 6. Debug — competing hypotheses, one fix owner

Use parallel exploration only when there are distinct plausible causes. Do not run competing writers against the same files.

```mermaid
flowchart TD
  A[Reproduce and minimize] --> B[Root lists testable hypotheses]
  B --> C[Explorer A tests hypothesis A]
  B --> D[Explorer B tests hypothesis B]
  C --> E[Root reconciles evidence]
  D --> E
  E --> F[One owner implements supported fix]
  F --> G[Original failure and regression checks]
```

## 7. Deadline — critical path plus verification reserve

A deadline changes scheduling and resource choice, never the definition of done.

```mermaid
flowchart TD
  A[Requirements and deadline] --> B[Estimate critical path plus checks]
  B --> C{Feasible with supported resources?}
  C -- Yes --> D[Root or ao_worker_critical on critical path]
  D --> E[Independent helpers where useful]
  E --> F[Integration and verification reserve]
  F --> G[Deliver evidenced result]
  C -- No --> H[Report conflict and request scope or time decision]
  H --> I[Continue independent authorized work]
```

## 8. Economy — bounded work with evidence-based escalation

A cheaper first attempt is appropriate only when the task is sufficiently clear.

```mermaid
flowchart TD
  A[Clear bounded task] --> B[Economical capable agent]
  B --> C[Acceptance checks]
  C -- Pass --> D[Integrate]
  C -- Fail --> E[Root diagnoses failure]
  E --> F{New evidence or contract correction?}
  F -- Yes --> G[Targeted corrected attempt]
  F -- No --> H[Change hypothesis or escalate capability]
  G --> C
  H --> C
```

## 9. Changed scope or blocker — adapt the graph

```mermaid
flowchart TD
  A[Active workstreams] --> B[New requirement or failure]
  B --> C[Root updates ledger and dependencies]
  C --> D[Stop obsolete work]
  C --> E[Reuse or add necessary specialist]
  D --> F[Reassign ownership safely]
  E --> F
  F --> G[Integrate and recheck affected requirements]
```

## 10. Optional Jev — two routing layers

This is a proposed integration boundary, not an installed proxy or live classifier.

```mermaid
flowchart TD
  A[Task facts and constraints] -. Authorized classifier .-> B[Jev advisory signals]
  A --> C[Root chooses topology and verifies]
  B -. Advice .-> C
  C --> D[Actual Codex subagents]
  D --> E[Execution and acceptance evidence]
  F[Optional upstream Jev model proxy] -. Per-call model and effort .-> D
```
