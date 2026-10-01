#!/usr/bin/env python3
"""Create a verified source manifest and a clean ZIP release."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
OUT = DIST / "adaptive-agent-orchestrator-kit.zip"
MANIFEST = ROOT / "release-manifest.json"
EXCLUDED = {"release-manifest.json", "SHA256SUMS.txt"}

def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def files():
    return sorted(
        p for p in ROOT.rglob("*")
        if p.is_file()
        and p.name not in EXCLUDED
        and "__pycache__" not in p.parts
        and ".git" not in p.parts
        and "dist" not in p.relative_to(ROOT).parts
    )

def main() -> int:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    entries = {p.relative_to(ROOT).as_posix(): sha(p) for p in files()}
    MANIFEST.write_text(json.dumps({"schema": 1, "version": version, "files": entries}, indent=2) + "\n", encoding="utf-8")
    DIST.mkdir(exist_ok=True)
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for p in sorted([*files(), MANIFEST]):
            archive.write(p, f"adaptive-agent-orchestrator-kit/{p.relative_to(ROOT).as_posix()}")
    checksum = sha(OUT)
    (OUT.parent / "adaptive-agent-orchestrator-kit.zip.sha256").write_text(f"{checksum}  {OUT.name}\n", encoding="ascii")
    print(f"Created {OUT} ({OUT.stat().st_size} bytes)")
    print(f"SHA-256 {checksum}")
    print(f"Manifest: {len(entries)} files, version {version}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
