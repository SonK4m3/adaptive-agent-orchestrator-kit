# Maintainer release checklist

1. Review the change and run `python3 scripts/validate_package.py` plus `python3 -m unittest discover -s tests -v`.
2. Run the Codex smoke/acceptance scenario where feasible and update `VALIDATION.md` with environment, exact result, and gaps. Never convert model assignments or source-paper results into claims about this kit's measured savings.
3. Update `VERSION` and both READMEs if behavior or install instructions change.
4. Build from a clean checkout with Python 3.11+: `python3 scripts/build_release.py`. distribution.json declares included paths. The manifest covers every distributable source file except itself; ZIP checksum is emitted beside the ZIP. Source CI config and raw dist/ evidence are not shipped.
5. Test the extracted ZIP, not just the working tree: verify checksum, run `scripts/manage.py doctor`, install into a fresh temporary `CODEX_HOME`, run doctor, and uninstall. Confirm unrelated config/files remain.
6. Attach `adaptive-agent-orchestrator-kit.zip` and `.zip.sha256` to the GitHub release. Do not include local logs, credentials, test user data, or the parent workspace's scratch files.

CI is intended to run unit/structural checks on Windows, macOS, and Linux. A configured matrix is not evidence that every platform passed; cite the actual release workflow run.
