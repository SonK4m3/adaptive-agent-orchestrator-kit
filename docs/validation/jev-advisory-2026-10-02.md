# Initial JEV advisory smoke — 2026-10-02

Scope: workflow advisory, no coding-model proxy and no subagent execution. User
authorized the live API test after adding a local TypeSafe key. Only the synthetic
auth state and eligible candidate contracts were transmitted.

Flow observed:

1. Root supplied synthetic state and a predeclared next-workstream decision.
2. Deterministic filter rejected `conflicting-worker`: another actor owns its file.
3. Two candidates reached JEV: `reuse-worker` and `independent-review`.
4. One actual TypeSafe request returned `jev-1.13.0`, selecting `reuse-worker`.
5. Response schema, distribution and state fingerprint passed validation.
6. Comparison with the predeclared root choice was recorded as `accepted`.
7. Acceptance gaps remained unchanged; no worker/tester/reviewer was dispatched.

Measured UTC timestamp: `2026-10-02T02:34:06.637210+00:00` (09:34 Asia/Saigon).
Wall-clock request + normalization: 0.4451 seconds. Attempts: 1; retries: 0.
API-reported usage: 597 input tokens, 40 output tokens. Choice probability: 0.74;
other candidate: 0.26; confidence: 0.48. A single result does not calibrate accuracy
or latency. Billing cost and Codex credit effects were not measured.

Raw local artifacts are in ignored `dist/jev-live-20261002-first/`: `request.json`,
`record.json`, `evidence.json`. This distributed summary contains no credential.
The low/moderate confidence is diagnostic only; acceptance tests and independent
review are still outstanding in this synthetic state. The decision record proves
comparison/recording, not a root making a new decision in response to JEV or a real
auth implementation passing verification.

Remaining: real graph dispatch and trace compliance, repeated/matched task outcome
comparisons, advisory quality across scenarios and evidence of cost savings.

Local validation: 22 advisory tests passed, including mocked HTTP failure without
retry, explicit send gate, stale state/candidates, read-only and ownership filtering,
hard stops, invalid distributions, credential parsing and no-overwrite output.
The full suite ran 110 tests: 109 passed, 1 skipped (Windows symlink capability).
Package validation passed; both skill aliases retain identical JEV resources.
These automated tests make no additional paid API requests.
