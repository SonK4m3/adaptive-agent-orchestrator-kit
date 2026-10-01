# Installation details

The installer requires Python 3.11+ and uses only the standard library. Run `./setup.sh` on macOS/Linux or `./setup.ps1` in Windows PowerShell for interactive setup. It asks which skill entrypoint(s), optional roles, and target Codex home to install, then runs the offline integrity check. It reads the package manifest before install and refuses incomplete, modified, or unlisted package files. Use the extracted release directory as-is.

`CODEX_HOME` can point at a custom Codex home; otherwise the installer uses `~/.codex`. `--target` overrides both. Components are installed into `skills/<skill-name>` and `agents/ao_*.toml`. The role files are optional and can be omitted with `--parts skills`.

On conflict, inspect the existing destination first. `--replace` makes a recoverable copy and updates only the named components. A receipt at `.adaptive-agent-orchestrator/install.json` records hashes for components managed by this kit. Uninstall acts only on receipt-listed paths; modified contents require `--force` and are backed up. Restore a backup with `python3 scripts/manage.py restore BACKUP_ID`; restoration also preserves the current contents. `config.toml`, other agent definitions, and unrelated skills are not managed.

After installation, start a new Codex session and invoke one of the skill names. If discovery fails, check the exact Codex home used by the running runtime, inspect its skill/agent search configuration, then run `doctor --target PATH`. Do not infer effective model selection just from a TOML declaration: confirm it in runtime output when that matters.
