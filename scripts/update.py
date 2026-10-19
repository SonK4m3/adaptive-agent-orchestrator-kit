#!/usr/bin/env python3
"""Opt-in stable-release handoff; never edits the source checkout or user config."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile

from package_layout import distribution_files

ROOT = Path(__file__).resolve().parents[1]
REPO = "SonK4m3/adaptive-agent-orchestrator-kit"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
GUARD = "--skip-release-check"
MAX_DOWNLOAD = 32 * 1024 * 1024
MAX_EXPANDED = 128 * 1024 * 1024
MAX_FILE = 16 * 1024 * 1024


def version(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not re.fullmatch(r"v?(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})", value):
        raise ValueError("Expected stable MAJOR.MINOR.PATCH or vMAJOR.MINOR.PATCH")
    return tuple(int(part) for part in value.removeprefix("v").split("."))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected release-service redirect refused")


def fetch(url: str, limit: int) -> bytes:
    # URLs are derived locally from REPO and a validated numeric tag, never API URLs.
    allowed = (API, f"https://codeload.github.com/{REPO}/zip/refs/tags/")
    if url != allowed[0] and not url.startswith(allowed[1]):
        raise ValueError("Untrusted download URL")
    request = urllib.request.Request(url, headers={"User-Agent": "adaptive-orchestrator-release-check", "Accept": "application/vnd.github+json"})
    deadline = time.monotonic() + 60
    chunks = []
    size = 0
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=10) as response:
        if response.status != 200:
            raise ValueError("Unexpected release-service status")
        while True:
            if time.monotonic() > deadline:
                raise ValueError("Release-service download deadline exceeded")
            chunk = response.read(min(65536, limit + 1 - size))
            if not chunk:
                return b"".join(chunks)
            size += len(chunk)
            if size > limit:
                raise ValueError("Release-service response exceeds size limit")
            chunks.append(chunk)


def check(root: Path = ROOT) -> dict:
    current = (root / "VERSION").read_text(encoding="utf-8").strip()
    current_tuple = version(current)
    data = json.loads(fetch(API, 1024 * 1024))
    if not isinstance(data, dict) or data.get("draft") is not False or data.get("prerelease") is not False:
        raise ValueError("Release metadata is not a published stable release")
    tag = data.get("tag_name")
    latest = version(tag)
    return {"source_version": current, "release_tag": tag,
            "update_available": latest > current_tuple,
            "release_notes": f"https://github.com/{REPO}/releases/tag/{tag}",
            "archive_url": f"https://codeload.github.com/{REPO}/zip/refs/tags/{tag}"}


def safe_parts(name: str) -> tuple[str, ...]:
    if not name or "\\" in name or name.startswith("/"):
        raise ValueError("Unsafe archive path")
    parts = name.rstrip("/").split("/")
    for part in parts:
        if (not part or part in (".", "..") or part.endswith((".", " "))
                or any(ord(char) < 32 or char in ':<>"|?*' for char in part)
                or re.fullmatch(r"(?i)(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\..*)?", part)):
            raise ValueError("Unsafe or nonportable archive path")
    return tuple(parts)


def extract(archive: Path, destination: Path, tag: str) -> Path:
    """Preflight the entire ZIP before writing any member; ZIP-only by design."""
    version(tag)
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        if not members or len(members) > 4096:
            raise ValueError("Invalid archive entry count")
        plan = []
        seen = {}
        spelling = {}
        total = 0
        roots = set()
        for member in members:
            if member.orig_filename != member.filename:
                raise ValueError("Archive filename was normalized by ZIP parser")
            parts = safe_parts(member.filename)
            key = "/".join(parts).casefold()
            for index in range(1, len(parts) + 1):
                prefix = "/".join(parts[:index])
                if spelling.setdefault(prefix.casefold(), prefix) != prefix:
                    raise ValueError("Case-colliding archive directory spelling")
            if key in seen:
                raise ValueError("Duplicate/case-colliding archive path")
            mode = member.external_attr >> 16
            kind = stat.S_IFMT(mode)
            if (member.flag_bits & 1 or kind not in (0, stat.S_IFREG, stat.S_IFDIR)
                    or bool(member.external_attr & 0x400)  # Windows reparse-point attribute
                    or (kind == stat.S_IFDIR and not member.is_dir())
                    or (kind == stat.S_IFREG and member.is_dir())):
                raise ValueError("Unsupported archive entry type")
            if member.file_size > MAX_FILE or (member.is_dir() and member.file_size):
                raise ValueError("Invalid archive member size")
            total += member.file_size
            if total > MAX_EXPANDED:
                raise ValueError("Expanded archive exceeds size limit")
            seen[key] = member.is_dir()
            roots.add(parts[0])
            plan.append((member, parts))
        if len(roots) != 1:
            raise ValueError("Archive must contain one source root")
        for _, parts in plan:
            for index in range(1, len(parts)):
                if seen.get("/".join(parts[:index]).casefold()) is False:
                    raise ValueError("File/directory archive collision")
        destination.mkdir()
        for member, parts in plan:
            target = destination.joinpath(*parts)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(member) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)
    source = destination / next(iter(roots))
    validate_source(source, tag)
    return source


def validate_source(source: Path, tag: str) -> None:
    source = source.resolve()
    if version((source / "VERSION").read_text(encoding="utf-8").strip()) != version(tag):
        raise ValueError("Archive VERSION does not match release tag")
    required = ("setup.sh", "setup.ps1", "scripts/setup.py", "scripts/manage.py",
                "scripts/package_layout.py", "scripts/register_project.py",
                "scripts/validate_package.py", "scripts/deepseek_worker.py",
                "scripts/process_guard.py", "distribution.json",
                "skills/adaptive-agent-orchestrator/SKILL.md", "skills/astra-orchestrator/SKILL.md",
                "profiles/adaptive/profile.toml", "profiles/adaptive-max-2-subagents/profile.toml")
    if any(not (source / name).is_file() for name in required):
        raise ValueError("Incomplete source layout")
    roles = list((source / "profiles/adaptive/codex/agents").glob("ao_*.toml"))
    if len(roles) != 9:
        raise ValueError("Incomplete source roles")
    manifest = json.loads((source / "release-manifest.json").read_text(encoding="utf-8"))
    if (not isinstance(manifest, dict) or manifest.get("schema") != 1 or not isinstance(manifest.get("files"), dict)
            or version(manifest.get("version")) != version(tag)):
        raise ValueError("Invalid release manifest")
    files = {path.relative_to(source).as_posix(): path for path in distribution_files(source)}
    if set(files) != set(manifest["files"]):
        raise ValueError("Release manifest file set differs")
    for name, path in files.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["files"][name]:
            raise ValueError("Release manifest checksum mismatch")


def confirm(prompt: str) -> bool:
    try:
        return input(prompt + " [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def handoff(info: dict, stage_dir: Path | None = None) -> int:
    if not confirm("Download and validate this release's source archive?"):
        print("Update declined; no files downloaded.")
        return 0
    if stage_dir is not None and (stage_dir.exists() or stage_dir.is_symlink()):
        raise ValueError("Stage destination must not already exist")
    with tempfile.TemporaryDirectory(prefix="ao-release-") as temp:
        base = Path(temp)
        archive = base / "source.zip"
        archive.write_bytes(fetch(info["archive_url"], MAX_DOWNLOAD))
        source = extract(archive, base / "extracted", info["release_tag"])
        print(f"Validated release {info['release_tag']}; archive SHA-256 {hashlib.sha256(archive.read_bytes()).hexdigest()}")
        if stage_dir is not None:
            # Caller-owned staged source survives for AI review; scratch is still cleaned.
            from register_project import plain_chain
            stage_dir = stage_dir.expanduser().absolute()
            plain_chain(stage_dir)
            if stage_dir.exists():
                raise ValueError("Stage destination appeared during download")
            stage_dir.mkdir()  # Exclusive creation; an existing destination is never merged.
            try:
                shutil.copytree(source, stage_dir, dirs_exist_ok=True)
            except BaseException:
                # Only this newly created, explicitly selected directory is removed.
                shutil.rmtree(stage_dir)
                raise
            print(f"Staged source: {stage_dir}; not executed. Remove after the approved setup/review.")
            return 0
        if not confirm("Run the downloaded installer? It will ask again about targets and replacements."):
            print("Execution declined; temporary download will be removed.")
            return 0
        return subprocess.run([sys.executable, str(source / "scripts/setup.py"), GUARD], check=False).returncode


def describe(info: dict) -> None:
    print(f"Setup source {info['source_version']}; latest stable release {info['release_tag']}.")
    print(f"Release notes: {info['release_notes']}")
    print("Newer release available." if info["update_available"] else "No newer stable release for this setup source.")
    print("This does not track versions installed in individual projects.")


def error_kind(exc: Exception) -> str:
    # Status only: never persist response bodies, auth or arbitrary exception text.
    return f"HTTP {exc.code}" if isinstance(exc, urllib.error.HTTPError) else type(exc).__name__


def automatic(root: Path = ROOT) -> int | None:
    """Only check failures are best effort. Once handoff is chosen, fail closed."""
    try:
        info = check(root)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Warning: release check unavailable ({error_kind(exc)}); continuing local setup.", file=sys.stderr)
        return None
    describe(info)
    if not info["update_available"] or not confirm("Use the newer release instead of local setup?"):
        return None
    try:
        return handoff(info)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, RuntimeError) as exc:
        print(f"Update failed ({error_kind(exc)}); no local setup fallback after handoff.", file=sys.stderr)
        return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check only: no download or execution")
    parser.add_argument("--json", action="store_true", help="Machine-readable check result; requires --check")
    parser.add_argument("--offline", action="store_true", help="Skip the network and report a skipped check")
    parser.add_argument("--stage-dir", type=Path, help="Stage validated source for AI review without execution; must be new")
    args = parser.parse_args(argv)
    if (args.json and not args.check) or (args.check and args.stage_dir):
        parser.error("--json requires --check; --check cannot stage files")
    if args.offline:
        print(json.dumps({"status": "skipped", "reason": "offline"}) if args.json else "Release check skipped (offline); no update performed.")
        return 0
    try:
        info = check()
        if args.json:
            print(json.dumps(info))
        else:
            describe(info)
        if args.check or not info["update_available"]:
            return 0
        return handoff(info, args.stage_dir)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, RuntimeError) as exc:
        print(f"Release update/check failed ({error_kind(exc)}); no installation performed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Update cancelled.", file=sys.stderr)
        raise SystemExit(1)
