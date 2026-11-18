"""Durable, prompt-free task metadata for the Codex-to-DSH bridge."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import tempfile
import threading
import uuid

SCHEMA = 1
STATUSES = frozenset({"queued", "running", "completed", "failed", "timed_out", "cancelled", "unknown"})
TERMINAL = frozenset({"completed", "failed", "timed_out", "cancelled", "unknown"})
PERMISSIONS = frozenset({"read-only", "workspace-write"})
FAILURE_LAYERS = frozenset({"wrapper", "protocol", "dsh", "wrapper_cleanup", "mcp", "unknown"})
MAX_JOBS = 1000
MAX_INPUT_PATHS = 256
MAX_PATH_LENGTH = 512
MAX_PROGRESS_LABEL = 80
MAX_PROGRESS_FILE_BYTES = 1024 * 1024
TASK_ID_RE = re.compile(r"[0-9a-f]{32}")
LABEL_RE = re.compile(r"[A-Za-z0-9_.:-]{1,80}")
SESSION_RE = re.compile(r"[A-Za-z0-9_.:-]{1,128}")


class JobStoreError(ValueError):
    """Invalid, missing or corrupt job metadata."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def default_job_root(environ: dict[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    codex_home = Path(env["CODEX_HOME"]).expanduser() if env.get("CODEX_HOME") else Path.home() / ".codex"
    return codex_home / "deepseek-worker" / "jobs"


def _relative_input(value: str) -> str:
    if (not isinstance(value, str) or not value or len(value) > MAX_PATH_LENGTH
            or "\x00" in value or "\\" in value):
        raise JobStoreError("input paths must be bounded repository-relative paths using '/'")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if posix.is_absolute() or windows.is_absolute() or windows.drive or any(part in {"", ".", ".."} for part in posix.parts):
        raise JobStoreError("input path escapes or does not name a repository-relative file")
    return posix.as_posix()


def read_progress_file(path: str | Path) -> list[dict]:
    """Read only the wrapper's sanitized event schema; ignore a partial tail."""
    progress_path = Path(path)
    if progress_path.is_symlink():
        raise JobStoreError("progress file symlink rejected")
    try:
        if progress_path.stat().st_size > MAX_PROGRESS_FILE_BYTES:
            raise JobStoreError("progress file exceeds limit")
        raw = progress_path.read_bytes()
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise JobStoreError("progress file cannot be read") from exc
    if not raw.endswith(b"\n"):
        raw = raw[:raw.rfind(b"\n") + 1] if b"\n" in raw else b""
    rows = []
    for line in raw.splitlines()[:MAX_JOBS]:
        if len(line) > 1024:
            continue
        try:
            record = json.loads(line.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(record, dict) or not isinstance(record.get("event_type"), str):
            continue
        if record["event_type"] not in {"session", "status", "thinking", "text", "delta",
                                        "tool_call", "tool_result", "final", "error"}:
            continue
        clean = {"event_type": record["event_type"]}
        phase = record.get("phase")
        if isinstance(phase, str) and LABEL_RE.fullmatch(phase):
            clean["phase"] = phase
        session_id = record.get("session_id")
        if isinstance(session_id, str) and SESSION_RE.fullmatch(session_id):
            clean["session_id"] = session_id
        final_reason = record.get("final_reason")
        if isinstance(final_reason, str) and LABEL_RE.fullmatch(final_reason):
            clean["final_reason"] = final_reason
        observed_at = record.get("observed_at")
        if isinstance(observed_at, str) and len(observed_at) <= 32:
            clean["observed_at"] = observed_at
        rows.append(clean)
    return rows


class JobStore:
    """Atomic JSON records with no prompt, credential, transcript or raw-log fields."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self._lock = threading.RLock()
        self.root.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            self.root.chmod(0o700)

    def _path(self, task_id: str) -> Path:
        if not isinstance(task_id, str) or not TASK_ID_RE.fullmatch(task_id):
            raise JobStoreError("invalid task ID")
        return self.root / f"{task_id}.json"

    def _atomic_write(self, path: Path, record: dict) -> None:
        payload = (json.dumps(record, ensure_ascii=True, allow_nan=False, sort_keys=True) + "\n").encode("utf-8")
        fd, temporary = tempfile.mkstemp(prefix=".job-", suffix=".tmp", dir=self.root)
        try:
            if os.name != "nt":
                os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def create(self, workspace: str | Path, input_paths: list[str],
               permission_mode: str = "read-only") -> dict:
        if permission_mode not in PERMISSIONS:
            raise JobStoreError("unsupported requested permission mode")
        if not isinstance(input_paths, list) or len(input_paths) > MAX_INPUT_PATHS:
            raise JobStoreError("input path list exceeds limit")
        normalized = [_relative_input(path) for path in input_paths]
        if len(set(normalized)) != len(normalized):
            raise JobStoreError("duplicate input path")
        source = Path(workspace).expanduser().resolve(strict=True)
        if not source.is_dir():
            raise JobStoreError("workspace must be an existing directory")
        if len(list(self.root.glob("*.json"))) >= MAX_JOBS:
            raise JobStoreError("job store capacity reached; archive old jobs first")
        now = utc_now()
        task_id = uuid.uuid4().hex
        record = {
            "schema": SCHEMA,
            "task_id": task_id,
            "status": "queued",
            "created_at": now,
            "updated_at": now,
            "source_workspace": str(source),
            "input_paths": normalized,
            "requested_permission_mode": permission_mode,
            "attempt": 0,
            "session_id": None,
            "process_id": None,
            "last_progress": None,
            "checkpoint_id": None,
            "failure_layer": None,
            "final_reason": None,
            "exit_code": None,
            "result_path": None,
            "patch_path": None,
            "history": [],
        }
        self._atomic_write(self._path(task_id), record)
        return record

    def get(self, task_id: str) -> dict:
        with self._lock:
            path = self._path(task_id)
            if path.is_symlink():
                raise JobStoreError("job record symlink rejected")
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except FileNotFoundError as exc:
                raise JobStoreError("job not found") from exc
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                quarantine = path.with_name(f"{path.stem}.corrupt-{uuid.uuid4().hex}.json")
                try:
                    os.replace(path, quarantine)
                except OSError:
                    pass
                raise JobStoreError("job record is corrupt and was not treated as success") from exc
            self._validate_record(task_id, record)
            return record

    @staticmethod
    def _validate_record(task_id: str, record: object) -> None:
        required = {"schema", "task_id", "status", "created_at", "updated_at", "source_workspace",
                    "input_paths", "requested_permission_mode", "attempt", "session_id", "process_id",
                    "last_progress", "checkpoint_id", "failure_layer", "final_reason", "exit_code",
                    "result_path", "patch_path", "history"}
        if not isinstance(record, dict) or set(record) != required:
            raise JobStoreError("job record has an unsupported shape")
        if (record["schema"] != SCHEMA or record["task_id"] != task_id
                or not isinstance(record["status"], str) or record["status"] not in STATUSES
                or not isinstance(record["requested_permission_mode"], str)
                or record["requested_permission_mode"] not in PERMISSIONS
                or not isinstance(record["attempt"], int) or record["attempt"] < 0
                or not isinstance(record["input_paths"], list) or len(record["input_paths"]) > MAX_INPUT_PATHS
                or not isinstance(record["history"], list) or len(record["history"]) > 100):
            raise JobStoreError("job record contains invalid fields")
        if record["session_id"] is not None and (not isinstance(record["session_id"], str)
                                                  or not SESSION_RE.fullmatch(record["session_id"])):
            raise JobStoreError("job record session ID is invalid")
        if record["failure_layer"] is not None and record["failure_layer"] not in FAILURE_LAYERS:
            raise JobStoreError("job record failure layer is invalid")
        for path in record["input_paths"]:
            if _relative_input(path) != path:
                raise JobStoreError("job record input path is not normalized")

    def update(self, task_id: str, **changes) -> dict:
        with self._lock:
            return self._update_locked(task_id, **changes)

    def _update_locked(self, task_id: str, **changes) -> dict:
        allowed = {"status", "session_id", "process_id", "last_progress", "checkpoint_id",
                   "failure_layer", "final_reason", "exit_code", "result_path", "patch_path",
                   "attempt", "history"}
        if not changes or set(changes) - allowed:
            raise JobStoreError("unsupported or empty job update")
        record = self.get(task_id)
        current = record["status"]
        target = changes.get("status", current)
        allowed_next = {
            "queued": {"queued", "running", "cancelled", "failed"},
            "running": {"running", "completed", "failed", "timed_out", "cancelled", "unknown"},
            "completed": {"completed", "running"}, "failed": {"failed", "running"},
            "timed_out": {"timed_out", "unknown", "running"},
            "cancelled": {"cancelled", "unknown"}, "unknown": {"unknown", "queued", "running", "failed", "cancelled"},
        }
        if target not in allowed_next[current]:
            raise JobStoreError(f"invalid job transition: {current} -> {target}")
        if "session_id" in changes and changes["session_id"] is not None:
            if not isinstance(changes["session_id"], str) or not SESSION_RE.fullmatch(changes["session_id"]):
                raise JobStoreError("session ID is invalid")
        if "process_id" in changes and changes["process_id"] is not None:
            if not isinstance(changes["process_id"], int) or changes["process_id"] <= 0:
                raise JobStoreError("process ID is invalid")
        for field in ("last_progress", "checkpoint_id", "final_reason"):
            if field in changes and changes[field] is not None:
                if not isinstance(changes[field], str) or not LABEL_RE.fullmatch(changes[field][:MAX_PROGRESS_LABEL]):
                    raise JobStoreError(f"{field} must be a bounded label")
                changes[field] = changes[field][:MAX_PROGRESS_LABEL]
        if changes.get("failure_layer") is not None and changes["failure_layer"] not in FAILURE_LAYERS:
            raise JobStoreError("failure layer is invalid")
        for field in ("result_path", "patch_path"):
            if field in changes and changes[field] is not None:
                value = Path(changes[field]).resolve(strict=False)
                if self.root not in value.parents:
                    raise JobStoreError(f"{field} must be inside the job store")
                changes[field] = str(value)
        if "exit_code" in changes and changes["exit_code"] is not None and not isinstance(changes["exit_code"], int):
            raise JobStoreError("exit code must be an integer or null")
        record.update(changes)
        record["updated_at"] = utc_now()
        self._validate_record(task_id, record)
        self._atomic_write(self._path(task_id), record)
        return record

    def begin_attempt(self, task_id: str, *, session_id: str | None = None,
                      process_id: int | None = None, checkpoint_id: str | None = None) -> dict:
        record = self.get(task_id)
        if record["status"] not in {"queued", "timed_out", "unknown", "failed", "completed"}:
            raise JobStoreError("job still owns an active attempt or cannot be resumed")
        history = list(record["history"])
        if record["attempt"]:
            history.append({"attempt": record["attempt"], "status": record["status"],
                            "session_id": record["session_id"], "failure_layer": record["failure_layer"],
                            "final_reason": record["final_reason"], "exit_code": record["exit_code"],
                            "updated_at": record["updated_at"]})
        if len(history) > 100:
            raise JobStoreError("attempt history limit reached")
        return self.update(task_id, status="running", session_id=session_id or record["session_id"],
                           process_id=process_id, checkpoint_id=checkpoint_id, attempt=record["attempt"] + 1,
                           history=history, failure_layer=None, final_reason=None, exit_code=None,
                           result_path=None, patch_path=None)

    def ingest_progress(self, task_id: str, events: list[dict]) -> dict:
        record = self.get(task_id)
        changes = {}
        for event in events:
            if event.get("session_id"):
                changes["session_id"] = event["session_id"]
            if event.get("final_reason"):
                changes["final_reason"] = event["final_reason"]
            progress = event.get("phase") or event.get("event_type")
            if isinstance(progress, str) and LABEL_RE.fullmatch(progress):
                changes["last_progress"] = progress[:MAX_PROGRESS_LABEL]
        return self.update(task_id, **changes) if changes else record

    def list(self, limit: int = 100) -> list[dict]:
        if not isinstance(limit, int) or not 1 <= limit <= MAX_JOBS:
            raise JobStoreError(f"list limit must be between 1 and {MAX_JOBS}")
        records = []
        for path in sorted(self.root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]:
            if path.is_symlink():
                continue
            task_id = path.stem
            if TASK_ID_RE.fullmatch(task_id):
                records.append(self.get(task_id))
        return records
