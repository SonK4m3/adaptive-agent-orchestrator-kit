<!-- deepseek-first-policy:start -->
## Default coding delegation

For coding implementation, load `adaptive-agent-orchestrator` automatically and use its DeepSeek-first policy through the existing `scripts/deepseek_worker.py`. Preserve the active repository/worktree cwd, scope, privacy boundaries and exclusive write ownership. `astra-orchestrator` is an equivalent explicit alias; load one entrypoint. Other orchestration skills apply when explicitly selected or needed for a separate workflow.

When DeepSeek is unavailable, continue within the authorized task using an available Codex fallback role that fits the task and its actual configured model/effort pins. Astra or Luna roles are optional choices when their pins and capabilities fit; neither is required, and Root retains scope and acceptance regardless of its model. Treat `server is busy` as provider availability; skip real DSH implementation while it is known unavailable. Allow at most one safe, bounded availability retry. Confirm workers have stopped before transferring write ownership, then inspect the diff and run independent acceptance checks. Preserve model settings. Repository restrictions and direct user choices take precedence.
<!-- deepseek-first-policy:end -->
