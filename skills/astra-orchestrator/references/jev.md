# Jev integration boundary

The referenced [jev-codex-router](https://github.com/0xNatoshi/jev-codex-router) selects model and effort for model calls. Topology selection is a separate responsibility owned by this skill and root.

Its [support matrix](https://github.com/0xNatoshi/jev-codex-router/blob/main/docs/SUPPORT.md) supports the full installer on macOS. Portable embedded-router tests do not establish full Windows support. This kit does not install or port that stack.

Start with workflow advisory, not per-call model routing. In a source checkout or extracted kit, package helpers `scripts/jev_advisory.py` and `scripts/jev_live_smoke.py` prepare bounded state/candidates, filter hard constraints, validate a Choice response and record root's decision. They are not installed as executables inside this skill. See package guide `guides/JEV-ADVISORY.md` for the schema and commands. A skill-only installation uses this policy without claiming the package helpers are available.

Skip classification for deterministic decisions or small root-only tasks. At a useful coordination checkpoint, supply a redacted minimal summary, acceptance gaps, deadline and eligible candidate contracts. Zero candidates means blocked; one candidate needs no classifier. Never send source or chat context silently. Live smoke requires explicit send consent, uses the named TypeSafe credential, one pinned-model request, a timeout and no automatic retry. Root owns all actual graph edits, dispatch, ownership handoff and verification. The helper never spawns agents or changes coding models.

Keep observed facts separate from inferred judgments. Treat the result as advice: root reconciles it with repository evidence and hard requirements. Invalid or stale imported responses fall back to root; root may override valid advice with a reason. Keep independent review blind to classifier confidence. The initial synthetic live smoke demonstrates transport and recording only, not an executed subagent graph.

Reuse advice only while task state and candidate set remain unchanged. Re-evaluate on changed scope, errors or new dependencies. On unavailable service or invalid response, continue with prompt-based routing and record fallback. Never infer quality or authorization from classifier confidence.

Measure classification overhead plus all execution/retry costs. Compare completed verified tasks with and without the classifier before claiming savings. The opt-in advisory smoke runs on Python, including Windows; the separate proxy stack and automatic graph dispatch remain unimplemented. Token counts, API dollars and Codex subscription credits are different metrics.
