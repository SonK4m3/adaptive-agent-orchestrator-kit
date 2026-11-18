# Set up DeepSeek Harness for Codex

This guide connects the kit's optional `ao_deepseek_worker` to a local DeepSeek
Harness (DSH) CLI. Codex remains the orchestrator: it defines the task and scope,
starts DSH through the wrapper, reviews the result and owns final acceptance.

## What each teammate needs

- Codex installed and signed in, with access to the target repository.
- A personal DeepSeek API key and any provider account/billing access required by
  the team's policy. Do not share the key in chat, source control, or task prompts.
- DSH Desktop on Windows/macOS, or Node.js and the DSH npm CLI on a supported
  system. The DSH CLI's published package declares Node.js `>=24.9.0`; recheck
  its engine requirement before upgrading.
- This kit's setup skill installed in Codex, plus the project-local orchestration
  skill and `ao_deepseek_worker` role/helper in each repository where it is used.

DSH is a developer-preview project and its install commands can change. Use the
official [DeepSeek Harness repository](https://github.com/deepseek-ai/deepseek-harness)
as the authority; review the [Quickstart](https://deepseekdocs.com/en/docs/getting-started/quickstart),
[CLI reference](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/cli-help.md),
[Desktop guide](https://github.com/deepseek-ai/deepseek-harness/blob/master/apps/desktop/README.md),
[CLI package and Node engine](https://github.com/deepseek-ai/deepseek-harness/blob/master/apps/cli/package.json),
and [release downloads](https://github.com/deepseek-ai/deepseek-harness/releases).

## 1. Install DSH and make `dsh` available

### Recommended for Windows and macOS: Desktop app

1. Download the current release for your OS from the official [DSH Releases](https://github.com/deepseek-ai/deepseek-harness/releases)
   page and install/launch it.
2. On first launch, configure the official DeepSeek provider and API key in the
   welcome flow or the app's Models settings. Confirm a model is selected and
   complete a short test prompt in DSH.
3. In the application menu, choose **Manage dsh Command…** and select **Install**.
   Open a new terminal so it reloads PATH.
4. Verify the CLI:

```sh
dsh --version
dsh --profile headless --help
```

The Desktop app bundles its own runtime; a separate Node.js installation is not
needed for its `dsh` command. The CLI command continues to work while the app is
closed. If you move the app, use **Repair** on macOS or **Install** again on Windows.

### CLI install for Linux or users who prefer npm

Install Node.js `>=24.9.0`, then install the published CLI globally so the kit can
find `dsh` on PATH:

```sh
node --version
npm install --global @deepseek-ai/dsh
dsh --version
dsh --profile headless --help
```

If you only want to test before installing globally, the official zero-install
form is `npx @deepseek-ai/dsh --profile headless --help`. The kit wrapper itself
expects a `dsh` executable discoverable on PATH.

## 2. Configure the DeepSeek credential

The easiest path is DSH's Models page: save a key for the official DeepSeek
provider, select the model, and verify it with a short DSH prompt. DSH stores
credentials in its user-level Harness home by default (`~/.dsh`); consult DSH's
[Credential Management](https://deepseekdocs.com/en/docs/user-guide/credentials)
and [Data & Privacy](https://deepseekdocs.com/en/docs/user-guide/privacy) guides
for current storage and rotation behavior. The official GitHub repository remains
the source of truth if preview documentation and a release differ.

The wrapper passes `DEEPSEEK_API_KEY` when explicitly present in the launching
environment, and otherwise lets DSH use its own saved user credential. It does
not forward arbitrary environment variables, proxy settings, or custom
certificate variables. The standard DSH home is expected; custom `DSH_HOME`
values are not forwarded by this kit version. Do not put API keys in the target
repository's `.env` for this workflow.

## 3. Run a one-shot DSH smoke test

This sends a real request to DeepSeek and may consume API quota. Run it yourself
after configuring your credential:

```sh
dsh --profile headless --json "Reply exactly DSH_OK"
```

Expect a successful process exit and a final response containing `DSH_OK`. If
authentication fails, fix the DSH credential before configuring Codex. If the
command is not found, reopen the terminal and inspect `where dsh` (Windows) or
`command -v dsh` (macOS/Linux). Do not proceed until `dsh --version` works in
the same environment where Codex will run.

## 4. Install the kit in a target repository

Install the setup skill into Codex:

```sh
npx skills add https://github.com/SonK4m3/adaptive-agent-orchestrator-kit --skill adaptive-orchestrator-setup
```

Open the existing target repository in Codex and ask it to prepare project-local
orchestration. Include the DeepSeek role explicitly in the setup request:

```text
$adaptive-orchestrator-setup
Prepare this repository for adaptive orchestration. Start with a read-only preview.
Install the adaptive-agent-orchestrator skill and the optional ao_deepseek_worker
role plus its helper scripts. Keep setup project-local, preserve existing files
and Codex settings, leave Jev disabled, and show conflicts before applying anything.
```

Review the preview. The setup skill installs the role and helper under the
project's `.codex/` directory and registers skill routing in `AGENTS.md`; it does
not install DSH itself or change the user's root model/effort. Start a **new Codex
chat** in that repository after setup so it can discover the new skill/role.

## 5. Verify Codex-to-DSH handoff

In the new chat, ask for one bounded, read-only task and explicitly invoke the
orchestrator, for example:

```text
$adaptive-agent-orchestrator
Use ao_deepseek_worker for a read-only summary of the repository's top-level
modules. Do not edit files. Return the DSH session ID and wrapper status.
```

The wrapper starts `dsh --profile headless --json -` in the repository's current
directory. Confirm Codex reports a completed wrapper run and a final answer; then
have Codex check any claims against repository evidence. This proves the handoff
for that session, not that every future task will be delegated or that a particular
DeepSeek model was served.

### Optional asynchronous MCP mode

For tasks likely to outlive one Codex tool call, install the optional worker role and
its helper scripts, then register `deepseek_mcp.py` as a project MCP server using the
manual configuration example in [Installation details](INSTALLATION.md#optional-asynchronous-deepseek-mcp-bridge).
The bridge returns a durable task ID immediately; Codex can check status, wait in
short bounded intervals, and retrieve a result plus patch after completion. It
stores job state and artifacts under `<CODEX_HOME>/deepseek-worker/jobs` and resumes
only an explicitly requested DSH session. It does not apply changes to the source
checkout. Root reviews and applies the patch, then verifies the integrated diff.

Choose only relevant repository-relative input paths. The bridge omits common secret,
Codex settings, dependency and build paths, but its task workspace is not an OS-level
security sandbox. DSH's requested permission mode is not proof of effective DSH or
filesystem permissions. If MCP is not installed/configured, use the synchronous
wrapper flow above.

### Long tasks, checkpoints and resume

Split work that may exceed the wrapper's timeout into bounded checkpoints, each
with a concrete output and acceptance check. Have Codex review each checkpoint's
evidence and partial diff before allowing the next write slice. Keep dependent
steps sequential and give each active path one writer.

On wrapper timeout, use the JSON report's `session_id`, `failure_layer`, and
`cleanup_errors` to decide the next step. The wrapper does not retry automatically.
After the child process tree has stopped, cleanup is clean, and Codex has inspected
partial changes, Codex may resume the persisted DSH session with `--session-id` and
a narrow prompt describing only the unfinished checkpoint. Do not replay the
original task or duplicate side effects. A reported ID is correlation evidence;
DSH may no longer have that session persisted. If the report is absent, the parent
Codex runtime may have interrupted the wrapper before it could report; treat that
as an outer-runtime interruption unless logs show otherwise.

The wrapper requests `read-only`, but reports effective DSH permissions as
unverified. DSH's permission preset and the Codex agent's filesystem sandbox are
separate controls; do not use a write task as a permission test. See the official
[DSH permissions guide](https://deepseekdocs.com/en/docs/user-guide/permissions)
and this kit's [wrapper evidence limits](INSTALLATION.md#deepseek-worker-limits-and-evidence).

## Data and troubleshooting

DSH receives the task and any repository content it reads. Do not delegate secrets,
credentials, private keys, or unrelated proprietary data. The wrapper filters the
child environment but does not sandbox DSH's access to files or services. A failed
handoff is not an implementation pass; use the reported status, exit code, and
classified error to diagnose it, and keep the work with Codex if DSH is unavailable.

| Symptom | Check |
| --- | --- |
| `dsh` not found | Open a new terminal; confirm Desktop's command registration or npm global PATH. |
| Authentication error | Configure the official DeepSeek API key in DSH Models settings; test a short DSH prompt. |
| DSH works in terminal but Codex cannot find it | Restart Codex, confirm it uses the same user/PATH, then start a new chat in the target repo. |
| Role not listed | Run the kit's `python scripts/manage.py doctor --target <project>/.codex` and confirm the role files are in that exact target. Start a new Codex chat. |
| Timeout/output limit | Split remaining work into checkpoints, inspect partial changes and cleanup, then consider an explicit session resume; otherwise use an authorized Codex fallback. The wrapper does not retry automatically. |
| `read-only` appears in the report | This is the requested mode only. Effective permissions remain unverified in the wrapper report. |

For kit installation details, conflict handling, updates, and rollback, see
[Installation details](INSTALLATION.md). For the current behavior of DSH, prefer
its linked official CLI and release references over copied command syntax.

## Shared HTTP dashboard pilot

For shared task IDs between Codex and a second MCP client, install the optional HTTP helper and dashboard described in [Installation details](INSTALLATION.md#shared-http-server-and-dashboard-pilot). Both clients must connect to one running Streamable HTTP server. The current version binds to loopback, pins one workspace, and has no authentication. It is not available to ChatGPT's remote MCP service; do not expose it through a tunnel. ChatGPT connection and actual dashboard rendering still require a separately secured HTTPS deployment and remain unverified here.
