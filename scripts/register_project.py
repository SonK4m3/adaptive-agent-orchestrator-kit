#!/usr/bin/env python3
"""Append installed-skill routing to one explicitly selected project AGENTS.md.

No rewrites or deletion: existing bytes remain an exact prefix. A changed/malformed
managed block requires human inspection, never automatic replacement.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import sys
from urllib.parse import quote

from manage import SKILLS, assert_plain_path, codex_home

START = "<!-- adaptive-agent-orchestrator-kit: routing v1 -->"
END = "<!-- /adaptive-agent-orchestrator-kit: routing -->"


def plain_chain(path: Path) -> None:
    cursor = path
    while cursor != Path(cursor.anchor):
        if cursor.exists() or cursor.is_symlink():
            assert_plain_path(cursor)
        cursor = cursor.parent


def routing_block(home: Path, skill: str, project: Path | None = None) -> str:
    names = SKILLS if skill == "both" else (skill,)
    if any(name not in SKILLS for name in names):
        raise RuntimeError("Unknown skill selection")
    links = []
    for name in names:
        source = (project / ".agents" if project else home) / "skills" / name / "SKILL.md"
        plain_chain(source)
        if not source.is_file():
            raise RuntimeError(f"Selected installed skill is missing: {name}")
        link = source.relative_to(project).as_posix() if project else source.as_posix()
        links.append(f"[{name}]({quote(link, safe='/:')})")
    selected = " or ".join(links)
    return "\n".join((START, "## Installed adaptive orchestration skill", "",
        f"Consider {selected} when delegation is requested or independent outputs, context load or verification risk justify coordination. Read the linked SKILL.md before using it; " + ("these paths refer to project-local installed skills." if project else "these paths refer to the installed skills, not this project."), "",
        "The two entrypoint names share one policy: select one, never load both by default. Skill selection does not require subagents. Keep small or tightly coupled tasks root-only; no graph, contract file or separate report is mandatory. Still state changes, actual checks and material limitations briefly.", "",
        "When delegating, root explains the topology and each agent's concrete output and scope. Keep one writer per path and use independent verification where risk warrants it. Create graph records only for dependency/ownership/handoff tracking or a requested audit; read only relevant supporting resources.", "",
        "These instructions do not override project constraints or authorize external writes, configuration changes or benchmarks. Review/audit remains read-only unless implementation is requested. Survey/retro is separate and is not automatically enabled.", END))


def decode_existing(raw: bytes) -> tuple[str, str]:
    if raw.startswith(b"\xff\xfe"):
        return raw[2:].decode("utf-16-le"), "utf-16-le"
    if raw.startswith(b"\xfe\xff"):
        return raw[2:].decode("utf-16-be"), "utf-16-be"
    text = raw.decode("utf-8-sig")
    if "\x00" in text:
        raise RuntimeError("Unsupported AGENTS.md encoding; no changes made")
    return text, "utf-8"


def register_project(project: Path, home: Path, skill: str = "both", *, project_skills: bool = False) -> dict:
    project = project.expanduser().absolute()
    plain_chain(project)
    if project == Path(project.anchor) or not project.is_dir():
        raise RuntimeError("Project must be an existing directory, not a filesystem root")
    path = project / "AGENTS.md"
    plain_chain(path)
    if path.exists() and not path.is_file():
        raise RuntimeError("AGENTS.md is not a regular file")
    block = routing_block(home, skill, project if project_skills else None)
    lock = project / ".AGENTS.md.orchestrator.lock"
    # Exclusive cooperating-installer lock; a stale lock must be inspected.
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RuntimeError("Registration lock exists; inspect it before retrying") from exc
    os.close(descriptor)
    try:
        original = path.read_bytes() if path.exists() else b""
        text, encoding = decode_existing(original)
        newline = "\r\n" if "\r\n" in text else "\n"
        expected = block.replace("\n", newline)
        if START in text or END in text or "<!-- adaptive-agent-orchestrator-kit:" in text:
            if text.count(START) != 1 or text.count(END) != 1 or text.count("<!-- adaptive-agent-orchestrator-kit:") != 1:
                raise RuntimeError("Malformed or duplicate routing markers; no changes made")
            begin, end = text.index(START), text.index(END) + len(END)
            if text[begin:end] != expected:
                raise RuntimeError("Existing routing block differs; inspect it manually. No content overwritten")
            return {"status": "unchanged", "path": str(path)}
        suffix = (newline * (2 if text and not text.endswith("\n") else 1 if text else 0)
                  + expected + newline).encode(encoding)
        # Avoid clobbering a file created/edited since the read. Never open in 'w'.
        with path.open("ab" if path.exists() else "xb") as stream:
            if path.read_bytes() != original:
                raise RuntimeError("AGENTS.md changed during registration; retry after inspection")
            stream.write(suffix)
            stream.flush()
            os.fsync(stream.fileno())
        return {"status": "appended", "path": str(path),
                "original_sha256": hashlib.sha256(original).hexdigest(),
                "original_bytes": len(original)}
    finally:
        lock.unlink()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    location = parser.add_mutually_exclusive_group()
    location.add_argument("--target", help="Installed Codex home (same as manage.py --target)")
    location.add_argument("--project-skills", action="store_true", help="Link project .agents/skills with portable relative paths; do not use Codex home")
    parser.add_argument("--skill", choices=(*SKILLS, "both"), default="both")
    args = parser.parse_args(argv)
    try:
        home = args.project.absolute() / ".codex" if args.project_skills else codex_home(args.target)
        result = register_project(args.project, home, args.skill, project_skills=args.project_skills)
        print(f"Routing {result['status']}: {result['path']} (existing content preserved)")
        return 0
    except (OSError, UnicodeError, RuntimeError) as exc:
        print(f"Registration failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
