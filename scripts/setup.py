#!/usr/bin/env python3
"""Interactive cross-platform setup for the Adaptive Agent Orchestrator kit."""
from __future__ import annotations

import os
import argparse
from pathlib import Path
import subprocess
import sys
from manage import codex_home
from register_project import register_project

ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT / "scripts" / "manage.py"


def choose(prompt: str, options: dict[str, str], default: str) -> str:
    while True:
        answer = input(f"{prompt} [{'/'.join(options)}] (default {default}): ").strip().lower() or default.lower()
        if answer in options:
            return options[answer]
        print("Please choose one of the listed options.")


def confirm(prompt: str, default: bool) -> bool:
    hint = "Y/n" if default else "y/N"
    while True:
        answer = input(f"{prompt} [{hint}] ").strip().lower()
        if not answer:
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Please answer yes or no.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true', help='Skip the best-effort stable release check')
    parser.add_argument('--skip-release-check', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not args.offline and not args.skip_release_check:
        from update import automatic
        handoff_result = automatic(ROOT)
        if handoff_result is not None:
            return handoff_result
    print("Adaptive Agent Orchestrator — Codex setup")
    print("This installs the selected skill(s) and optional agent role definitions.\n")
    profile = choose(
        "Profile: 1) adaptive (capacity 4)  2) adaptive-max-2-subagents (capacity 2)",
        {"1": "adaptive", "2": "adaptive-max-2-subagents"}, "1",
    )
    skill = choose(
        "Skills: 1) both entrypoints  2) astra-orchestrator  3) adaptive-agent-orchestrator",
        {"1": "both", "2": "astra-orchestrator", "3": "adaptive-agent-orchestrator"},
        "1",
    )
    parts = "all" if confirm("Install the 8 optional subagent role definitions too?", True) else "skills"
    with_profile_config = confirm("Install an optional named runtime preset (activate with codex -p NAME)?", False)
    default_target = os.environ.get("CODEX_HOME") or str(Path.home() / ".codex")
    custom = input(f"Codex home [Enter for {default_target}]: ").strip()
    target = str(Path(custom).expanduser()) if custom else None
    project_input = input("Project directory for an appended AGENTS.md skill-routing block [Enter to skip]: ").strip()
    project = Path(project_input).expanduser().absolute() if project_input else None
    if project is not None and (not project.is_dir() or project == Path(project.anchor)):
        print("Project must be an existing directory, not a filesystem root. Nothing installed.", file=sys.stderr)
        return 1

    command = [sys.executable, str(MANAGER), "install", "--skill", skill, "--parts", parts, "--profile", profile]
    if with_profile_config:
        command.append("--with-profile-config")
    if target:
        command.extend(("--target", target))
    print("\nThe installer checks for conflicts and creates a recoverable backup before replacing existing files.")
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    if completed.returncode != 0 and "use --replace to back it up first" in completed.stderr:
        if confirm("A different kit component already exists. Back it up and replace it?", False):
            replace_command = [*command, "--replace"]
            completed = subprocess.run(replace_command, cwd=ROOT, text=True, capture_output=True, check=False)
            if completed.stdout:
                print(completed.stdout, end="")
            if completed.stderr:
                print(completed.stderr, end="", file=sys.stderr)
    result_code = completed.returncode
    if result_code == 0:
        if with_profile_config:
            print(f"Optional runtime preset installed. Start a new CLI session with: codex -p {profile}")
        doctor = [sys.executable, str(MANAGER), "doctor"]
        if target:
            doctor.extend(("--target", target))
        result_code = subprocess.run(doctor, cwd=ROOT, check=False).returncode
    if result_code == 0:
        if project is not None:
            try:
                registration = register_project(project, codex_home(target), skill)
                print(f"AGENTS.md routing {registration['status']}: {registration['path']}; previous content preserved.")
            except (OSError, UnicodeError, RuntimeError) as exc:
                print(f"Skills installed, but project registration failed: {exc}", file=sys.stderr)
                return 1
        else:
            print("Project registration skipped. Use scripts/register_project.py --project PATH to add routing later.")
        print("\nSetup complete. Restart Codex, then invoke $astra-orchestrator or $adaptive-agent-orchestrator in a coding task.")
    else:
        print("\nSetup did not complete; see the diagnostic above. Existing files were not replaced without confirmation.", file=sys.stderr)
    return result_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EOFError, KeyboardInterrupt):
        print("\nSetup cancelled.", file=sys.stderr)
        raise SystemExit(1)
