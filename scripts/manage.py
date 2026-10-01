#!/usr/bin/env python3
"""Safe, standard-library-only installer for the Codex orchestrator kit."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import stat
import tempfile
import tomllib
import re
from package_layout import distribution_files
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "release-manifest.json"
STATE_DIR = ".adaptive-agent-orchestrator"
SKILLS = ("adaptive-agent-orchestrator", "astra-orchestrator")
PROFILES = ("adaptive", "adaptive-max-2-subagents")


def profile_data(name: str) -> dict:
    if name not in PROFILES:
        raise RuntimeError(f"Unknown profile: {name}")
    data = tomllib.loads((ROOT / "profiles" / name / "profile.toml").read_text(encoding="utf-8"))
    if data.get("schema") != 1 or data.get("name") != name:
        raise RuntimeError(f"Invalid profile: {name}")
    for key in ("roles", "config"):
        path = (ROOT / data[key]).resolve()
        if ROOT.resolve() not in path.parents:
            raise RuntimeError(f"Profile path escapes package: {key}")
    return data


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def assert_plain_path(path: Path) -> None:
    attrs = getattr(path.lstat(), "st_file_attributes", 0) if path.exists() or path.is_symlink() else 0
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    is_junction = getattr(path, "is_junction", lambda: False)()
    if path.is_symlink() or is_junction or (reparse and attrs & reparse):
        raise RuntimeError(f"Refusing symlink: {path}")


def safe_tree(path: Path) -> None:
    assert_plain_path(path)
    if path.is_dir():
        for item in path.iterdir():
            safe_tree(item)


def validate_release() -> None:
    if not MANIFEST.is_file():
        raise RuntimeError("release-manifest.json is missing; use a built release package")
    root = MANIFEST.parent.resolve()
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("schema") != 1 or not isinstance(data.get("files"), dict):
        raise RuntimeError("Unsupported or malformed release manifest")
    expected = set(data["files"])
    actual = {p.relative_to(root).as_posix() for p in distribution_files(root)}
    if expected != actual:
        raise RuntimeError(f"Release file set differs (missing={sorted(expected-actual)}, unlisted={sorted(actual-expected)})")
    for rel, checksum in data["files"].items():
        p = (root / rel).resolve()
        if root not in p.parents or not p.is_file() or digest(p) != checksum:
            raise RuntimeError(f"Release integrity check failed: {rel}")


def tree_hash(path: Path) -> str:
    h = hashlib.sha256()
    if path.is_file():
        return digest(path)
    for item in sorted(p for p in path.rglob("*") if p.is_file()):
        h.update(item.relative_to(path).as_posix().encode())
        h.update(bytes.fromhex(digest(item)))
    return h.hexdigest()


def codex_home(arg: str | None) -> Path:
    raw = arg or os.environ.get("CODEX_HOME") or str(Path.home() / ".codex")
    target = Path(raw).expanduser().absolute()
    if target == Path(target.anchor):
        raise RuntimeError("CODEX_HOME cannot be a filesystem root")
    cursor = target
    while cursor != Path(cursor.anchor):
        if cursor.exists() or cursor.is_symlink():
            assert_plain_path(cursor)
        cursor = cursor.parent
    return target


def ensure_safe_path(base: Path, path: Path) -> None:
    """Reject links/junctions on the path from the selected Codex home to a managed item."""
    if '..' in path.parts:
        raise RuntimeError(f"Managed path contains traversal: {path}")
    try:
        path.resolve(strict=False).relative_to(base.resolve(strict=False))
        rel = path.absolute().relative_to(base.absolute())
    except ValueError as exc:
        raise RuntimeError(f"Managed path escapes CODEX_HOME: {path}") from exc
    cursor = base
    assert_plain_path(cursor)
    for part in rel.parts:
        cursor = cursor / part
        if cursor.exists() or cursor.is_symlink():
            assert_plain_path(cursor)


def managed_path(rel_text: str) -> Path:
    if not isinstance(rel_text, str):
        raise RuntimeError('Invalid managed component path')
    rel = Path(rel_text)
    allowed = {f'skills/{name}' for name in SKILLS} | {f'{name}.config.toml' for name in PROFILES}
    normalized = rel.as_posix()
    role = re.fullmatch(r'agents/ao_[A-Za-z0-9_]+\.toml', normalized)
    if rel.is_absolute() or '..' in rel.parts or (normalized not in allowed and not role):
        raise RuntimeError(f'Unsafe managed component: {rel_text}')
    return rel


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def components(args: argparse.Namespace) -> list[tuple[Path, Path]]:
    result: list[tuple[Path, Path]] = []
    profile = profile_data(getattr(args, "profile", "adaptive"))
    if args.parts in ("all", "skills"):
        names = SKILLS if args.skill == "both" else (args.skill,)
        result.extend((ROOT / "skills" / name, Path("skills") / name) for name in names)
    if args.parts in ("all", "roles"):
        result.extend((p, Path("agents") / p.name) for p in sorted((ROOT / profile["roles"]).glob("ao_*.toml")))
    if getattr(args, "with_profile_config", False):
        result.append((ROOT / profile["config"], Path(f"{profile['name']}.config.toml")))
    return result


def load_state(target: Path) -> dict:
    path = target / STATE_DIR / "install.json"
    ensure_safe_path(target, path)
    if not path.is_file():
        return {"schema": 1, "components": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != 1 or not isinstance(data.get("components"), dict):
        raise RuntimeError(f"Invalid install receipt: {path}")
    for rel, checksum in data['components'].items():
        managed_path(rel)
        if not isinstance(checksum, str) or not re.fullmatch(r'[0-9a-f]{64}', checksum):
            raise RuntimeError(f'Invalid managed checksum: {rel}')
    return data


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def install(args: argparse.Namespace) -> None:
    validate_release()
    target = codex_home(args.target)
    target.mkdir(parents=True, exist_ok=True)
    items = components(args)
    if not items or len(list((ROOT / profile_data(getattr(args, "profile", "adaptive"))["roles"]).glob("ao_*.toml"))) != 8:
        raise RuntimeError("Expected two bundled skills and exactly eight ao_*.toml roles")
    state = load_state(target)
    # Preflight all conflicts before making any changes.
    for source, rel in items:
        dest = target / rel
        ensure_safe_path(target, dest)
        safe_tree(source)
        if dest.exists():
            safe_tree(dest)
            if tree_hash(source) != tree_hash(dest) and not args.replace:
                raise RuntimeError(f"Different existing component; use --replace to back it up first: {dest}")
    backup_id = f"{stamp()}-{os.urandom(4).hex()}"
    backup_root = target / ".adaptive-agent-orchestrator-backups" / backup_id
    ensure_safe_path(target, backup_root)
    backed_up: list[str] = []
    backup_ownership: dict[str, str | None] = {}
    transaction = Path(tempfile.mkdtemp(prefix=".ao-stage-", dir=target))
    moved: list[tuple[Path, Path | None, bool]] = []
    try:
        staged: list[tuple[Path, Path, str]] = []
        for source, rel in items:
            staged_path = transaction / rel
            staged_path.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, staged_path)
            else:
                shutil.copy2(source, staged_path)
            if tree_hash(source) != tree_hash(staged_path):
                raise RuntimeError(f"Staging verification failed: {rel}")
            staged.append((staged_path, target / rel, tree_hash(source)))
        for staged_path, dest, checksum in staged:
            previous = state["components"].get(dest.relative_to(target).as_posix())
            if dest.exists() and tree_hash(dest) == checksum:
                if previous is not None:
                    state["components"][dest.relative_to(target).as_posix()] = checksum
                moved.append((dest, None, False))
                continue
            old_backup: Path | None = None
            if dest.exists():
                old_backup = backup_root / dest.relative_to(target)
                old_backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(dest, old_backup) if dest.is_dir() else shutil.copy2(dest, old_backup)
                rel_text = dest.relative_to(target).as_posix()
                backed_up.append(rel_text)
                backup_ownership[rel_text] = previous
            # Register rollback before removal/rename, including rename failure.
            moved.append((dest, old_backup, True))
            if dest.exists():
                shutil.rmtree(dest) if dest.is_dir() else dest.unlink()
            dest.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged_path, dest)
            state["components"][dest.relative_to(target).as_posix()] = checksum
        if backup_root.exists():
            write_json(backup_root / "receipt.json", {"schema": 1, "id": backup_id, "components": backed_up, "managed_before": backup_ownership})
        ensure_safe_path(target, target / STATE_DIR / "install.json")
        write_json(target / STATE_DIR / "install.json", state)
        print(f"Installed {len(items)} components into {target}")
        if backup_root.exists():
            print(f"Recoverable backup: {backup_root}")
    except Exception:
        for dest, old_backup, changed in reversed(moved):
            if not changed:
                continue
            if dest.exists():
                shutil.rmtree(dest) if dest.is_dir() else dest.unlink()
            if old_backup is not None:
                restore_copy(old_backup, dest)
        raise
    finally:
        shutil.rmtree(transaction, ignore_errors=True)


def doctor(args: argparse.Namespace) -> None:
    validate_release()
    target = codex_home(args.target)
    state = load_state(target)
    problems: list[str] = []
    for rel, expected in state["components"].items():
        p = target / rel
        ensure_safe_path(target, p)
        if not p.exists():
            problems.append(f"missing: {rel}")
        elif tree_hash(p) != expected:
            problems.append(f"modified: {rel}")
    if problems:
        print("Install check failed:\n- " + "\n- ".join(problems))
        raise SystemExit(1)
    print(f"Package integrity OK; {len(state['components'])} recorded components OK at {target}")
    print("Codex runtime discovery/model execution is not tested by this offline check.")


def restore_copy(saved: Path, dest: Path) -> None:
    """Restore a fully preflighted copy without relying on rename rollback."""
    if dest.exists():
        shutil.rmtree(dest) if dest.is_dir() else dest.unlink()
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(saved, dest) if saved.is_dir() else shutil.copy2(saved, dest)


def uninstall(args: argparse.Namespace) -> None:
    target = codex_home(args.target)
    state = load_state(target)
    managed_before = dict(state["components"])
    if not managed_before:
        raise RuntimeError("No managed installation receipt found; refusing to guess what to remove")
    items = []
    mismatches = []
    for rel, expected in managed_before.items():
        p = target / managed_path(rel)
        ensure_safe_path(target, p)
        if p.exists():
            safe_tree(p)
            if tree_hash(p) != expected:
                mismatches.append(rel)
            items.append((rel, p))
    if mismatches and not args.force:
        raise RuntimeError("Modified installed components; use --force to remove after backup: " + ", ".join(mismatches))
    backup_id = f"uninstall-{stamp()}-{os.urandom(4).hex()}"
    backup_root = target / ".adaptive-agent-orchestrator-backups" / backup_id
    ensure_safe_path(target, backup_root)
    # Finish ALL backups and their receipt before deleting any component.
    for rel, p in items:
        saved = backup_root / rel
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(p, saved) if p.is_dir() else shutil.copy2(p, saved)
        if tree_hash(saved) != tree_hash(p):
            raise RuntimeError(f"Backup verification failed: {rel}")
    write_json(backup_root / "receipt.json", {"schema": 1, "id": backup_id, "components": [rel for rel, _ in items], "managed_before": managed_before})
    changed = []
    try:
        for rel, p in items:
            changed.append((rel, p))
            shutil.rmtree(p) if p.is_dir() else p.unlink()
        write_json(target / STATE_DIR / "install.json", {"schema": 1, "components": {}})
    except Exception:
        for rel, p in reversed(changed):
            restore_copy(backup_root / rel, p)
        raise
    print(f"Removed managed components. Recoverable backup: {backup_root}")
    print("Codex config.toml and unrelated skills/agents were left untouched.")


def restore(args: argparse.Namespace) -> None:
    target = codex_home(args.target)
    backup_id = args.backup_id
    if not backup_id or Path(backup_id).name != backup_id or backup_id in (".", ".."):
        raise RuntimeError("Invalid backup ID")
    backup_root = target / ".adaptive-agent-orchestrator-backups" / backup_id
    ensure_safe_path(target, backup_root)
    receipt_path = backup_root / "receipt.json"
    if not receipt_path.is_file():
        raise RuntimeError(f"Backup receipt not found: {receipt_path}")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("schema") != 1 or not isinstance(receipt.get("components"), list):
        raise RuntimeError("Invalid backup receipt")
    managed_before = receipt.get("managed_before", {})
    if not isinstance(managed_before, dict):
        raise RuntimeError("Invalid managed-state backup metadata")
    for rel_text, checksum in managed_before.items():
        managed_path(rel_text)
        if checksum is not None and (not isinstance(checksum, str) or not re.fullmatch(r'[0-9a-f]{64}', checksum)):
            raise RuntimeError("Invalid backup ownership checksum")
    state = load_state(target)
    items = []
    seen = set()
    # Validate EVERY item before staging or changing any destination.
    for rel_text in receipt["components"]:
        rel = managed_path(rel_text)
        if rel.as_posix() in seen:
            raise RuntimeError("Duplicate backup component")
        seen.add(rel.as_posix())
        saved = backup_root / rel
        ensure_safe_path(target, saved)
        if not saved.exists():
            raise RuntimeError(f"Backup component is missing: {saved}")
        safe_tree(saved)
        dest = target / rel
        ensure_safe_path(target, dest)
        if dest.exists():
            safe_tree(dest)
        items.append((rel.as_posix(), saved, dest))
    safety_id = f"pre-restore-{stamp()}-{os.urandom(4).hex()}"
    safety_root = target / ".adaptive-agent-orchestrator-backups" / safety_id
    ensure_safe_path(target, safety_root)
    transaction = Path(tempfile.mkdtemp(prefix=".ao-restore-", dir=target))
    changed = []
    staged = []
    safety_components = []
    try:
        # Stage replacements and complete current-content backups before commit.
        for rel, saved, dest in items:
            staged_path = transaction / rel
            staged_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(saved, staged_path) if saved.is_dir() else shutil.copy2(saved, staged_path)
            if tree_hash(saved) != tree_hash(staged_path):
                raise RuntimeError(f"Restore staging verification failed: {rel}")
            current_save = None
            if dest.exists():
                current_save = safety_root / rel
                current_save.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(dest, current_save) if dest.is_dir() else shutil.copy2(dest, current_save)
                if tree_hash(current_save) != tree_hash(dest):
                    raise RuntimeError(f"Safety backup verification failed: {rel}")
                safety_components.append(rel)
            staged.append((rel, staged_path, dest, current_save))
        if safety_components:
            write_json(safety_root / "receipt.json", {"schema": 1, "id": safety_id, "components": safety_components, "managed_before": {rel: state["components"].get(rel) for rel in safety_components}})
        for rel, staged_path, dest, current_save in staged:
            changed.append((dest, current_save))
            if dest.exists():
                shutil.rmtree(dest) if dest.is_dir() else dest.unlink()
            dest.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged_path, dest)
            if rel in managed_before and managed_before[rel] is None:
                state["components"].pop(rel, None)
            elif rel in managed_before:
                state["components"][rel] = managed_before[rel]
            else:
                state["components"][rel] = tree_hash(dest)
        write_json(target / STATE_DIR / "install.json", state)
    except Exception:
        for dest, current_save in reversed(changed):
            if current_save is not None:
                restore_copy(current_save, dest)
            elif dest.exists():
                shutil.rmtree(dest) if dest.is_dir() else dest.unlink()
        raise
    finally:
        shutil.rmtree(transaction, ignore_errors=True)
    print(f"Restored {len(items)} component(s) from {backup_id}")
    if safety_components:
        print(f"Previous contents preserved: {safety_root}")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("install", "doctor", "uninstall", "restore"):
        q = sub.add_parser(name)
        q.add_argument("--target", help="CODEX_HOME directory (defaults to CODEX_HOME or ~/.codex)")
        if name == "install":
            q.add_argument("--profile", choices=PROFILES, default="adaptive")
            q.add_argument("--with-profile-config", action="store_true", help="Install a separate named runtime preset; activate with codex -p NAME in a new session")
            q.add_argument("--skill", choices=("both", *SKILLS), default="both")
            q.add_argument("--parts", choices=("all", "skills", "roles"), default="all")
            q.add_argument("--replace", action="store_true", help="Back up and replace differing managed destinations")
        elif name == "uninstall":
            q.add_argument("--force", action="store_true", help="Back up then remove modified managed components")
        elif name == "restore":
            q.add_argument("backup_id", help="ID of a backup under .adaptive-agent-orchestrator-backups")
    return p


def main() -> int:
    args = parser().parse_args()
    try:
        {"install": install, "doctor": doctor, "uninstall": uninstall, "restore": restore}[args.command](args)
        return 0
    except (RuntimeError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
