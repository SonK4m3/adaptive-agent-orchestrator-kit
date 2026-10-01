# Security policy

Please report security issues privately to the repository maintainer rather than filing a public issue with exploit details. The repository maintainer should add a private reporting address or enable GitHub Security Advisories before public distribution.

The installer writes only the selected skill directories, namespaced agent TOML files, its own receipt, and backups under the chosen Codex home. It does not edit Codex configuration. Review the paths and run `doctor` before using a downloaded build. Do not install untrusted role files: agent instructions can influence tool use and code changes.
