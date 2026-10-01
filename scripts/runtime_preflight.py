"""Credential-free sandbox fixture read; never invokes inference or setup commands.

Evidence is an allowlisted projection, not a dump of effective runtime config.
Passing this helper does not attest the model tool router, dispatch or billing.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from process_guard import spawn_process


def preflight(cli, home, workspace, evidence, windows_sandbox=None):
    report = {"status": "blocked", "model_invoked": False,
              "coverage": "local sandbox Python fixture reads only; tool router and agents unverified",
              "configuration": {"source": "private temporary home plus explicit command overrides",
                                "effective_runtime_policy": "unconfirmed",
                                "windows_sandbox": windows_sandbox,
                                "permission_profile": "preflight", "network": False,
                                "managed_requirements": "included; not overridden"},
              "environment": {"policy": "OS runtime allowlist; no inherited Desktop selectors or credentials"}}
    config_path = home / "config.toml"
    report["configuration"]["temporary_config_sha256"] = (
        hashlib.sha256(config_path.read_bytes()).hexdigest() if config_path.is_file() else None)
    report["environment"]["inherited_selector_names_present"] = [name for name in
        ("CODEX_PERMISSION_PROFILE", "CODEX_CI", "CODEX_INTERNAL_ORIGINATOR_OVERRIDE",
         "CODEX_SHELL", "CODEX_APP_TOOLS_PIPE_PATH", "CODEX_SESSION_ID", "CODEX_THREAD_ID")
        if name in os.environ]
    report["environment"]["pilot_environment_equivalence"] = "not attested; pilot currently inherits parent environment"
    started = time.monotonic()
    def finish(reason):
        report["reason"] = reason
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        (evidence / "preflight.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return report
    if os.name != "nt":
        return finish("Native Windows preflight only; other platforms unrun")
    if windows_sandbox not in {"elevated", "unelevated", "mxc"}:
        return finish("Explicit --windows-sandbox required; no implicit selection or fallback")
    if not cli:
        return finish("Codex CLI unavailable")
    paths = [workspace / "TASK.md", *sorted(p for p in workspace.iterdir()
             if p.suffix in {".py", ".txt"} and p.is_file()),
             home / "skills/adaptive-agent-orchestrator/SKILL.md"]
    if any(not p.is_file() or p.is_symlink() for p in paths):
        return finish("Required regular fixture/skill file missing")
    expected = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    # Do not expose file contents, credentials, environment values or private paths.
    script = ("import hashlib,pathlib; paths=" + repr([str(p) for p in paths]) +
              "; expected=" + repr(expected) +
              "; assert [hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() for p in paths]==expected; print('AO_PREFLIGHT_OK')")
    env = {k: os.environ[k] for k in ("PATH", "SystemRoot", "WINDIR", "COMSPEC", "SystemDrive") if k in os.environ}
    env.update(CODEX_HOME=str(home), HOME=str(home), USERPROFILE=str(home),
               TMP=str(home), TEMP=str(home), TMPDIR=str(home), PYTHONDONTWRITEBYTECODE="1")
    command = [cli, "sandbox", "--include-managed-config", "-C", str(workspace), "-P", "preflight",
               "-c", 'windows.sandbox=' + json.dumps(windows_sandbox),
               "-c", 'permissions.preflight.filesystem.":minimal"="read"',
               "-c", 'permissions.preflight.network.enabled=false']
    for root in (workspace, home, Path(sys.base_prefix), Path(sys.executable).parent):
        command += ["-c", "permissions.preflight.filesystem." + json.dumps(str(root.resolve())) + '="read"']
    command += ["--", sys.executable, "-I", "-c", script]
    proc = guard = None
    try:
        proc, guard = spawn_process(command, cwd=workspace, env=env, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate(timeout=20)
        report["exit_code"] = proc.returncode
        # Keep error classifications, never raw potentially secret-bearing output.
        errors = stderr.decode("utf-8", errors="replace").lower()
        report["error_signals"] = [s for s in ("blocked by policy", "access denied", "1385", "sandbox", "setup", "unknown", "unrecognized") if s in errors]
        if proc.returncode == 0 and stdout.strip() == b"AO_PREFLIGHT_OK":
            report["status"] = "pass"
            report["read_checks"] = [{"file": p.name if p.parent == workspace else "installed SKILL.md"} for p in paths]
            return finish("Exact fixture hashes read inside native sandbox")
        return finish("Sandbox read failed or unexpected output; no unrestricted fallback")
    except (OSError, subprocess.SubprocessError) as exc:
        report["error_type"] = type(exc).__name__
        return finish("Sandbox preflight unavailable; no retry")
    finally:
        if guard is not None:
            guard.close()
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
