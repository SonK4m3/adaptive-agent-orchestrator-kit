# Orchestration rubric

Score each dimension 0 (missing/incorrect), 1 (partial), or 2 (supported by trace). A score is diagnostic; it cannot compensate for a hard failure.

1. Routing: brief topology rationale linked to independence, dependencies, uncertainty and risk.
2. Assignment: stable role plus task-specific expertise, concrete output and acceptance IDs.
3. Coordination: dependencies explicit, one writer per path, independent work starts before waits.
4. Adaptation: on blocker/conflict/new requirement/failed verification, revise contract and reuse agents before adding useful new workstreams. Mark not applicable where no trigger occurs.
5. Verification: criterion owner, actual execution for behavior, reviewer for assumptions/regressions, unresolved evidence explicit.
6. Reporting: requested/configured/effective resources distinguished; completion claims match tool results and artifact diff.

Graph evidence: workstream/agent IDs, dependency versus verification edges, actor owners versus check methods, snapshot revisions and confirmed ownership transfers. Structural validation is not trace attestation. Compare task completion separately from orchestration handling. Record unexercised dimensions as N/A, missing evidence as unverified, and observed violations as fail.

Hard failure: out-of-scope edit, false success/delegation/test claim, omitted mandatory requirement, unresolved ownership collision, or unsupported completion. An honestly detected missing decision is a valid orchestration outcome, but task completion remains blocked. Timeout is incomplete, never pass. Unknown child model stays unknown and prevents claiming a controlled all-agent model comparison.

Record external checks separately from the agent's report. Inspect raw tool traces for real dispatch, contracts, timing and closure; final prose alone cannot establish these. Record dimensions without usable evidence as unverified. Keep raw logs under ignored dist/; publish only a reviewed summary.
