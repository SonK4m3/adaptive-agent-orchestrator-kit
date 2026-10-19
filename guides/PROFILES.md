# Resource profiles

| Profile | Concurrent capacity | Policy / roles | Root model |
| --- | --- | --- | --- |
| adaptive | 4 | Shared adaptive policy and nine optional ao_* roles, including the DSH bridge | User's existing choice |
| adaptive-max-2-subagents | 2 | Same | User's existing choice |

Neither profile prescribes an agent count or topology. Root explains useful independent outputs and verification risk before selecting workstreams. Reviewer/tester selection remains risk-based. The limited-capacity profile may stage work; it does not reduce acceptance requirements.

Source definitions live in profiles/<name>/profile.toml and codex/config.toml. Both descriptors reference the shared role source in [adaptive/codex/agents](../profiles/adaptive/codex/agents/). Portable skill entrypoints live in [skills](../skills/); there are no per-profile policy copies.

Default setup installs only selected skill/role components. To install a named CLI preset as well:

```sh
python scripts/manage.py install --profile adaptive-max-2-subagents --with-profile-config
codex -p adaptive-max-2-subagents
```

The preset is stored at <CODEX_HOME>/adaptive-max-2-subagents.config.toml. The CLI profile interface observed in Codex 0.159.2 layers this named file over user settings. Activation happens only in a new session. Runtime recognition of the agents keys and actual concurrency requires runtime evidence; package integrity alone does not prove it. Desktop profile activation is not implemented by this installer. For manual project configuration, inspect and merge desired [agents] keys from the template into a trusted project's .codex/config.toml; preserve existing settings and verify your runtime's supported schema.

Root model, approval policy, sandbox and hard billing limits are omitted from presets. Named role models/efforts retain their current bindings. Do not assume a default model overrides named role pins. Model choices are hypotheses, not benchmark results.

## Isolated runtime pilot

From the source checkout/extracted kit root, first prepare without inference:

```sh
python scripts/run_orchestration.py --model gpt-6.1-sol --effort medium --scenario root-only --probe worker --prepare-only
```

The bounded pilot fixes the requested root choice; it is not a general model benchmark. For a live worker probe remove --prepare-only and provide an existing supported auth environment, or explicitly pass --auth-home EXISTING_CODEX_HOME. The latter copies auth.json into a private ephemeral temporary home only; the CLI consumes it, cleanup removes the temporary home, and credentials are never included in dist evidence. It does not copy user config or install into that existing home. Review credential handling before adapting this harness to shared hosts.

The reviewer probe uses --scenario verification --probe reviewer. Run the four --scenario choices (root-only, independent, verification, adaptation) only after both plumbing gates have evidence. Each run defaults to a shared 600-second limit, no automatic retry; adaptation uses two turns in one session and one budget. Account usage cannot be hard-capped by this helper.

The CLI --strict-config live invocation checks template recognition. Generated protocol schemas may omit agents keys; permissive schema validation is not runtime proof. Inspect raw collab events, artifacts, exact-file hashes and reviewed rubric findings. Missing/invalid records, partial trace coverage and unknown effective models must remain explicit. See [pilot scenarios](../eval/scenarios/orchestration.md) and [implementation evidence](../docs/validation/AGENT-GRAPH-IMPLEMENTATION-2026-10-01.md).

Current live gate is blocked; do not treat those commands as verified dispatch on every runtime. The pilot requires Windows owned-process containment; POSIX prepare-only works but live runs are disabled until detached descendants can be contained. External Python verification requires a working Codex filesystem/network sandbox plus the documented fixture subset; unsupported imports/IO/introspection or missing sandbox results are unrun, never an unrestricted fallback. The subset is not a universal Python sandbox.
## Credential-free preflight before a pilot

The runner now requires a successful local sandbox preflight before authentication
or model execution. `--prepare-only` remains inventory-only. To collect fail-closed
evidence without inference or copying credentials:

```powershell
python -B scripts/run_orchestration.py --model gpt-6.1-sol --preflight-only
```

On Windows this intentionally reports blocked until `--windows-sandbox` is selected
explicitly. A separately approved native sandbox check can add
`--windows-sandbox elevated` (or another approved implementation); no fallback is
automatic. This selection affects only temporary config, not installed profiles
or global settings. The runner does not call setup commands, but the native runtime
may require sandbox initialization: do not authorize that command on a machine
where OS-level setup has not been approved. No setup was performed in this change.

`preflight.json` contains timestamps/duration in its enclosing run, a temporary
config hash, explicit settings, inherited selector **names only**, exit status and
allowlisted error classifications. Arbitrary process output, secret values and
private paths are not persisted by the preflight. Effective runtime policy remains
unconfirmed. Passing proves hash-matching Python reads inside the local sandbox,
not PowerShell/tool-router access, agent dispatch/closure, model serving, write
capability or network enforcement. The preflight environment is credential-free
and is not claimed equivalent to the later pilot environment.

