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
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "release-manifest.json"
STATE_DIR = ".adaptive-agent-orchestrator"
SKILLS = ("adaptive-agent-orchestrator", "astra-orchestrator")


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
    actual = {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file()
        and p.resolve() != MANIFEST.resolve()
        and "__pycache__" not in p.parts
        and ".git" not in p.parts
        and "dist" not in p.relative_to(root).parts
    }
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
    try:
        rel = path.absolute().relative_to(base.absolute())
    except ValueError as exc:
        raise RuntimeError(f"Managed path escapes CODEX_HOME: {path}") from exc
    cursor = base
    assert_plain_path(cursor)
    for part in rel.parts:
        cursor = cursor / part
        if cursor.exists() or cursor.is_symlink():
            assert_plain_path(cursor)


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def components(args: argparse.Namespace) -> list[tuple[Path, Path]]:
    result: list[tuple[Path, Path]] = []
    if args.parts in ("all", "skills"):
        names = SKILLS if args.skill == "both" else (args.skill,)
        result.extend((ROOT / name, Path("skills") / name) for name in names)
    if args.parts in ("all", "roles"):
        result.extend((p, Path("agents") / p.name) for p in sorted((ROOT / "roles").glob("ao_*.toml")))
    return result


def load_state(target: Path) -> dict:
    path = target / STATE_DIR / "install.json"
    ensure_safe_path(target, path)
    if not path.is_file():
        return {"schema": 1, "components": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != 1 or not isinstance(data.get("components"), dict):
        raise RuntimeError(f"Invalid install receipt: {path}")
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
    if not items or len(list((ROOT / "roles").glob("ao_*.toml"))) != 8:
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
                shutil.rmtree(dest) if dest.is_dir() else dest.unlink()
            dest.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged_path, dest)
            moved.append((dest, old_backup, True))
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
                old_backup.parent.mkdir(parents=True, exist_ok=True)
                os.replace(old_backup, dest)
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


def uninstall(args: argparse.Namespace) -> None:
    target = codex_home(args.target)
    state = load_state(target)
    managed_before = dict(state["components"])
    if not state["components"]:
        raise RuntimeError("No managed installation receipt found; refusing to guess what to remove")
    mismatches = []
    for rel, expected in state["components"].items():
        p = target / rel
        ensure_safe_path(target, p)
        if p.exists() and tree_hash(p) != expected:
            mismatches.append(rel)
    if mismatches and not args.force:
        raise RuntimeError("Modified installed components; use --force to remove after backup: " + ", ".join(mismatches))
    backup_id = f"uninstall-{stamp()}-{os.urandom(4).hex()}"
    backup_root = target / ".adaptive-agent-orchestrator-backups" / backup_id
    ensure_safe_path(target, backup_root)
    ensure_safe_path(target, backup_root)
    for rel in list(state["components"]):
        p = target / rel
        if not p.exists():
            continue
        safe_tree(p)
        saved = backup_root / rel
        ensure_safe_path(target, saved)
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(p, saved) if p.is_dir() else shutil.copy2(p, saved)
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    write_json(backup_root / "receipt.json", {"schema": 1, "id": backup_id, "components": list(state["components"]), "managed_before": managed_before})
    state["components"] = {}
    write_json(target / STATE_DIR / "install.json", state)
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
    state = load_state(target)
    safety_id = f"pre-restore-{stamp()}-{os.urandom(4).hex()}"
    safety_root = target / ".adaptive-agent-orchestrator-backups" / safety_id
    ensure_safe_path(target, safety_root)
    restored: list[str] = []
    for rel_text in receipt["components"]:
        rel = Path(rel_text)
        if rel.is_absolute() or not rel.parts or ".." in rel.parts or rel.parts[0] not in ("skills", "agents"):
            raise RuntimeError(f"Unsafe component path in backup receipt: {rel_text}")
        saved = backup_root / rel
        if not saved.exists():
            raise RuntimeError(f"Backup component is missing: {saved}")
        safe_tree(saved)
        dest = target / rel
        ensure_safe_path(target, dest)
        if dest.exists():
            safe_tree(dest)
            current_save = safety_root / rel
            current_save.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(dest, current_save) if dest.is_dir() else shutil.copy2(dest, current_save)
        staged = target / f".ao-restore-{os.urandom(5).hex()}"
        shutil.copytree(saved, staged) if saved.is_dir() else shutil.copy2(saved, staged)
        if dest.exists():
            shutil.rmtree(dest) if dest.is_dir() else dest.unlink()
        dest.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged, dest)
        rel_key = rel.as_posix()
        if rel_key in managed_before and managed_before[rel_key] is None:
            state["components"].pop(rel_key, None)
        elif rel_key in managed_before:
            state["components"][rel_key] = managed_before[rel_key]
        else:
            state["components"][rel_key] = tree_hash(dest)
        restored.append(rel.as_posix())
    if safety_root.exists():
        write_json(safety_root / "receipt.json", {"schema": 1, "id": safety_id, "components": restored})
    write_json(target / STATE_DIR / "install.json", state)
    print(f"Restored {len(restored)} component(s) from {backup_id}")
    if safety_root.exists():
        print(f"Previous contents preserved: {safety_root}")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("install", "doctor", "uninstall", "restore"):
        q = sub.add_parser(name)
        q.add_argument("--target", help="CODEX_HOME directory (defaults to CODEX_HOME or ~/.codex)")
        if name == "install":
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
