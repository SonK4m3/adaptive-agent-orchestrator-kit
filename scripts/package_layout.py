"""Explicit distributable paths shared by source validation and release build."""
import json
from pathlib import Path


def distribution_files(root: Path) -> list[Path]:
    data = json.loads((root / 'distribution.json').read_text(encoding='utf-8'))
    if data.get('schema') != 1 or not isinstance(data.get('include'), list):
        raise RuntimeError('Malformed distribution.json')
    extensions = data.get('directory_extensions', {})
    result = set()
    for rel in data['include']:
        if (root / rel).is_symlink():
            raise RuntimeError(f'Distribution symlink rejected: {rel}')
        path = (root / rel).resolve()
        if root.resolve() not in path.parents or not path.exists():
            raise RuntimeError(f'Missing or unsafe distribution path: {rel}')
        if path.is_dir() and (rel not in extensions or not isinstance(extensions[rel], list)):
            raise RuntimeError(f'Missing directory extension allowlist: {rel}')
        candidates = path.rglob('*') if path.is_dir() else [path]
        for item in candidates:
            if item.is_symlink():
                raise RuntimeError(f'Distribution symlink rejected: {item}')
            if item.is_file() and '__pycache__' not in item.parts and item.suffix not in ('.pyc', '.pyo'):
                if path.is_dir() and item.suffix.lower() not in extensions[rel]:
                    continue
                result.add(item)
    return sorted(result)
