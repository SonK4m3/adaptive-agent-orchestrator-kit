# CLI preflight and evidence — 2026-10-02 (Asia/Saigon)

Scope: add a credential-free preflight gate and evidence; no model retry, global
configuration edit or native sandbox setup. Original pilot evidence is unchanged.

## Diagnosis correction

The original `segment-1.stderr` records five `CreateProcess` rejections containing
`blocked by policy`. Their payloads are absent from JSONL but present in stderr.
This establishes process-launch rejection, not the exact enforcing policy.
The temporary profile contained only agents settings, whereas the inspected user
config had `[windows] sandbox = "elevated"`. Missing native sandbox selection is a
candidate cause, not a confirmed root cause. The original temporary home/rollout
was cleaned up; no effective-policy snapshot remains. The runner also inherited
Desktop environment; `--no-daemon` was added after that failed pilot.

## Implemented

- `--preflight-only` cannot authenticate, copy credentials or invoke inference;
  it rejects `--auth-home`. Inventory-only prepare remains separate.
- Every live pilot gates before `prepare_auth`/`execute`; missing selection,
  failed sandbox, timeout or unexpected output blocks without retries/fallback.
- Explicit `--windows-sandbox` applies only to temporary base config. Resource
  profiles and user config remain unchanged.
- Sandbox command includes managed requirements, disabled network and read-only
  roots for fixtures, installed skill and Python runtime. Child environment uses
  an OS-runtime allowlist, no inherited Desktop selectors or credentials.
- Evidence is an allowlisted config projection plus config hash, selector names,
  error classifications and timing. It is **not** an effective-policy attestation.
  Arbitrary stdout/stderr are not saved; only exact success marker accepted.

## Verification boundaries

Offline tests mock sandbox execution and cover success, error redaction, timeout
cleanup, missing selection, pilot fail-closed-before-auth and no-inference mode.
Full Windows suite: 76 tests pass, including extracted-ZIP lifecycle. Package
validator passes. Evidence-only run at 2026-10-02 00:33:56–00:33:58 Asia/Saigon
(raw timestamps are UTC) is stored at
`dist/graph-20261001T173356Z-ca88488b7aec4fe093ac89b2a2c2e392/`.
Its `result.json` reports `blocked`, zero segments, unchanged user config hash,
unchanged fixture files and missing explicit Windows sandbox selection.
No authentication was prepared and no sandbox child/model was launched.
The local evidence-only invocation intentionally omits sandbox selection: it must
block without launching the native sandbox. An explicit native sandbox execution
is unrun to avoid initiating unapproved OS-level initialization. Thus no claim
that the original blocker is resolved, or that Windows sandbox reads succeed.

A future approved check should run the explicit selection first, inspect errors,
and only then authorize one model probe. A successful sandbox helper still does
not prove the model's PowerShell tool router, dispatch, closure or serving model.

References: [native sandbox configuration](https://learn.chatgpt.com/docs/windows/windows-sandbox),
[sandbox command and approvals](https://learn.chatgpt.com/docs/agent-approvals-security).
