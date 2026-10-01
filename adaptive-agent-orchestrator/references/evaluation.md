# Evaluate outcomes, not agent counts

## Baselines and candidate

Compare root-only, the earlier fixed Astra/Luna organization, and this adaptive policy on the same repository revisions and task specifications. Use isolated checkouts, the same tool access and acceptance oracle, and reset generated state between runs. Counterbalance run order; record warm/cold caches and external service latency. Include multiple task families and repetitions before attributing a difference to policy.

Acceptance checks should come from the requirement contract, including negative cases, not solely from the implementation agent. Do not reveal expected routes to an agent when evaluating autonomous route selection. Forced L2 tests check plumbing only.

Include: small edits, ambiguous bug diagnosis, independent feature slices, shared-schema changes, risky auth, deadline conflicts, model unavailability, agent failure, read-only audits, and real integration tasks. Use the scenario catalog in the kit root.

## Compare in priority order

1. All must-have requirements verified, no material unresolved regression, scope respected. Record omissions and unrun checks as failures/gaps, not passes.
2. Among configurations meeting that quality bar, measure end-to-end latency including review and correction; report deadline success, median and tail latency.
3. Among sufficiently reliable and timely configurations, compare all-agent usage and cost per verified completion. Include failed runs and retries in the numerator; if none pass, the cost-per-success ratio is undefined.

Report sample size, model/effort/runtime, benchmark split, scaffold, attempts per task, hardware/tool latency, prices/date, and uncertainty. Missing tokens/cost stay unknown. A lower spawn count or a public benchmark score does not establish cheaper verified work here.

## Shipping gate

Run frontmatter validation and inspect reference links/diagrams. Exercise installation and actual runtime dispatch separately. At least one bounded coding task should pass an external acceptance test after real delegation. Report synthetic fixture tests separately from production repository acceptance. Re-test a policy after material changes; do not rerun unrelated checks merely for more output.
