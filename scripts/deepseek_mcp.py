"""Local asynchronous MCP bridge for bounded DeepSeek Harness jobs."""
from __future__ import annotations

import difflib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import subprocess
import sys
import threading
import time
import zipfile

from deepseek_jobs import JobStore, JobStoreError, default_job_root, read_progress_file
from deepseek_worker import child_environment
from process_guard import spawn_process

MAX_TASK_BYTES = 512 * 1024
MAX_RPC_LINE_BYTES = MAX_TASK_BYTES * 4 + 64 * 1024
MAX_INPUT_FILES = 5000
MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_OUTPUT_FILES = 5000
MAX_OUTPUT_BYTES = 64 * 1024 * 1024
MAX_TEXT_DIFF_BYTES = 2 * 1024 * 1024
MAX_OUTPUT_PATH_LENGTH = 512
MAX_RETURN_PATHS = 100
MAX_CONCURRENT = 3
MAX_TIMEOUT_SECONDS = 600
MAX_WAIT_SECONDS = 30
MAX_RETURN_TEXT = 32 * 1024
IGNORED_DIRS = frozenset({".git", ".codex", "node_modules", ".venv", "venv", "__pycache__",
                          ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist", "build",
                          "coverage", ".next", "target", ".ssh", ".aws", ".azure",
                          ".gnupg", ".kube", ".npm", ".cache"})
SENSITIVE_NAMES = frozenset({".npmrc", ".netrc", ".pypirc", "credentials.json", "auth.json",
                             "id_rsa", "id_ed25519", "known_hosts"})


class BridgeError(ValueError):
    """A safe, user-actionable bridge error."""


def _is_sensitive(name: str) -> bool:
    lower = name.lower()
    return lower.startswith(".env") or lower in SENSITIVE_NAMES


def _safe_copy_inputs(source: Path, input_paths: list[str], destination: Path) -> tuple[int, int]:
    total_bytes = total_files = 0
    source = source.resolve(strict=True)
    destination.mkdir(parents=True, exist_ok=False)

    def copy_file(src: Path, rel: Path) -> None:
        nonlocal total_bytes, total_files
        if _is_sensitive(src.name) or src.is_symlink():
            return
        if not src.is_file():
            return
        size = src.stat().st_size
        if size > MAX_INPUT_BYTES or total_bytes + size > MAX_INPUT_BYTES:
            raise BridgeError("selected inputs exceed the 64 MiB limit")
        if total_files + 1 > MAX_INPUT_FILES:
            raise BridgeError("selected inputs exceed the file-count limit")
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
        total_bytes += size
        total_files += 1

    for raw in input_paths:
        rel = PurePosixPath(raw)
        if any(part in IGNORED_DIRS or _is_sensitive(part) for part in rel.parts):
            raise BridgeError("selected input includes an excluded or sensitive path")
        src = source.joinpath(*rel.parts)
        cursor = source
        has_symlink_parent = False
        for part in rel.parts:
            cursor = cursor / part
            has_symlink_parent = has_symlink_parent or cursor.is_symlink()
        if has_symlink_parent:
            raise BridgeError("selected input symlinks are not accepted")
        if src.is_symlink():
            raise BridgeError("selected input symlinks are not accepted")
        try:
            resolved = src.resolve(strict=True)
            resolved.relative_to(source)
        except (OSError, ValueError) as exc:
            raise BridgeError("selected input is missing or resolves outside the workspace") from exc
        if resolved.is_file():
            copy_file(resolved, rel)
        elif resolved.is_dir():
            for current, dirs, files in os.walk(resolved, followlinks=False):
                current_path = Path(current)
                dirs[:] = [name for name in dirs if name not in IGNORED_DIRS
                           and not (current_path / name).is_symlink()]
                for name in sorted(files):
                    file_path = current_path / name
                    if file_path.is_symlink() or _is_sensitive(name):
                        continue
                    copy_file(file_path, file_path.relative_to(source))
        else:
            raise BridgeError("selected input must be a regular file or directory")
    return total_files, total_bytes


def _tree_files(root: Path) -> dict[str, Path]:
    files = {}
    total_bytes = 0
    for current, dirs, names in os.walk(root, followlinks=False):
        current_path = Path(current)
        dirs[:] = [name for name in dirs if name not in IGNORED_DIRS
                   and not (current_path / name).is_symlink()]
        for name in names:
            path = current_path / name
            if path.is_symlink() or _is_sensitive(name):
                continue
            rel = path.relative_to(root).as_posix()
            pure = PurePosixPath(rel)
            windows = PureWindowsPath(rel)
            if ("\\" in rel or pure.is_absolute() or windows.is_absolute() or windows.drive
                    or len(rel) > MAX_OUTPUT_PATH_LENGTH
                    or any(part in {"", ".", ".."} for part in pure.parts)):
                continue
            if len(files) >= MAX_OUTPUT_FILES:
                raise BridgeError("workspace output exceeds the file-count limit")
            total_bytes += path.stat().st_size
            if total_bytes > MAX_OUTPUT_BYTES:
                raise BridgeError("workspace output exceeds the 64 MiB limit")
            files[rel] = path
    return files


def _write_artifacts(job_dir: Path, attempt: int, report: dict, wrapper_stdout: bytes) -> tuple[Path, Path, Path, list[str]]:
    baseline = job_dir / "baseline"
    workspace = job_dir / "workspace"
    before = _tree_files(baseline)
    after = _tree_files(workspace)
    changed = []
    binary = []
    diff_parts = []
    output_files = []
    changed_bytes = 0
    names = sorted(set(before) | set(after))
    output_dir = job_dir / "artifacts" / f"attempt-{attempt}"
    output_dir.mkdir(parents=True, exist_ok=False)
    file_dir = output_dir / "files"
    file_dir.mkdir()
    for name in names:
        old = before.get(name).read_bytes() if name in before else None
        new = after.get(name).read_bytes() if name in after else None
        if old == new:
            continue
        changed.append(name)
        changed_bytes += len(old or b"") + len(new or b"")
        if changed_bytes > MAX_OUTPUT_BYTES:
            raise BridgeError("changed files exceed the 64 MiB artifact limit")
        if new is not None:
            output_path = file_dir / Path(name)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(new)
            output_files.append((name, output_path))
        try:
            old_text = (old or b"").decode("utf-8")
            new_text = (new or b"").decode("utf-8")
        except UnicodeDecodeError:
            binary.append(name)
            continue
        if len(old_text.encode("utf-8")) + len(new_text.encode("utf-8")) > MAX_TEXT_DIFF_BYTES:
            binary.append(name)
            continue
        diff_parts.extend(difflib.unified_diff(
            old_text.splitlines(keepends=True), new_text.splitlines(keepends=True),
            fromfile=f"a/{name}" if old is not None else "/dev/null",
            tofile=f"b/{name}" if new is not None else "/dev/null", lineterm="\n"))
    patch_path = output_dir / "changes.patch"
    patch_path.write_text("".join(diff_parts), encoding="utf-8", newline="\n")
    outputs_zip = output_dir / "changed-files.zip"
    with zipfile.ZipFile(outputs_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, path in output_files:
            archive.write(path, name)
    result = {
        "schema": 1,
        "status": "timed_out" if report.get("status") == "timeout" else report.get("status", "unknown"),
        "failure_layer": report.get("failure_layer"),
        "exit_code": report.get("exit_code"),
        "elapsed_ms": report.get("elapsed_ms"),
        "session_id": report.get("session_id"),
        "final_reason": report.get("final_reason"),
        "cleanup_errors": report.get("cleanup_errors", []),
        "changed_paths": changed,
        "binary_paths_without_text_diff": binary,
        "answer": report.get("answer"),
        "wrapper_report_observed": bool(wrapper_stdout),
    }
    result_path = output_dir / "result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return result_path, patch_path, outputs_zip, changed


def _pid_active(pid: int | None) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.killpg(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
    import ctypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return ctypes.get_last_error() != 87
    try:
        code = ctypes.c_ulong()
        return not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259
    finally:
        kernel.CloseHandle(handle)


TOOL_DEFINITIONS = [
    {"name": "deepseek_task_start", "description": "Start a bounded DSH task asynchronously in an isolated workspace and return its task ID.",
     "inputSchema": {"type": "object", "properties": {
         "task": {"type": "string", "minLength": 1},
         "input_paths": {"type": "array", "items": {"type": "string"}, "maxItems": 256},
         "workspace": {"type": "string"},
         "permission_mode": {"type": "string", "enum": ["read-only", "workspace-write"]},
         "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": MAX_TIMEOUT_SECONDS},
         "checkpoint_id": {"type": "string"}}, "required": ["task", "input_paths"], "additionalProperties": False}},
    {"name": "deepseek_task_status", "description": "Read durable status and last sanitized progress for a DSH task.",
     "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}},
    {"name": "deepseek_task_list", "description": "List recent DSH task IDs and bounded lifecycle summaries.",
     "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}}, "additionalProperties": False}},
    {"name": "deepseek_task_wait", "description": "Wait for a task to settle, up to 30 seconds, then return its current state.",
     "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}, "wait_seconds": {"type": "integer", "minimum": 0, "maximum": MAX_WAIT_SECONDS}}, "required": ["task_id"]}},
    {"name": "deepseek_task_followup", "description": "Continue a stopped task's persisted DSH session with a new, focused prompt.",
     "inputSchema": {"type": "object", "properties": {
         "task_id": {"type": "string"}, "task": {"type": "string", "minLength": 1},
         "checkpoint_id": {"type": "string"}, "permission_mode": {"type": "string", "enum": ["read-only", "workspace-write"]},
         "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": MAX_TIMEOUT_SECONDS}},
         "required": ["task_id", "task"], "additionalProperties": False}},
    {"name": "deepseek_task_result", "description": "Read a bounded final answer and artifact paths; patches are never applied automatically.",
     "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}},
    {"name": "deepseek_task_cancel", "description": "Cancel an active bridge-owned task process tree.",
     "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}},
]


class ActiveJob:
    def __init__(self, proc, guard, done: threading.Event, cancelled: threading.Event):
        self.proc = proc
        self.guard = guard
        self.done = done
        self.cancelled = cancelled
        self.thread = None


class JobManager:
    def __init__(self, store: JobStore, worker_script: Path, max_concurrent: int = MAX_CONCURRENT):
        self.store = store
        self.worker_script = worker_script.resolve(strict=True)
        self.max_concurrent = max(1, min(MAX_CONCURRENT, max_concurrent))
        self.active: dict[str, ActiveJob] = {}
        self.lock = threading.RLock()
        self._recover_interrupted()

    def _job_dir(self, task_id: str) -> Path:
        return self.store.root / task_id

    def _progress_path(self, task_id: str, attempt: int) -> Path:
        return self._job_dir(task_id) / f"progress-{attempt}.jsonl"

    def _sync_progress(self, task_id: str) -> dict:
        record = self.store.get(task_id)
        rows = read_progress_file(self._progress_path(task_id, record["attempt"])) if record["attempt"] else []
        return self.store.ingest_progress(task_id, rows) if rows else record

    @staticmethod
    def _public(record: dict, *, process_active: bool | None = None) -> dict:
        result = {key: record.get(key) for key in (
            "task_id", "status", "created_at", "updated_at",
            "requested_permission_mode", "attempt", "session_id", "last_progress",
            "checkpoint_id", "failure_layer", "final_reason", "exit_code", "result_path", "patch_path")}
        result["input_count"] = len(record.get("input_paths", []))
        if process_active is not None:
            result["previous_process_may_be_active"] = process_active
        return result

    def _recover_interrupted(self) -> None:
        for record in self.store.list(limit=1000):
            if record["status"] == "running":
                self._sync_progress(record["task_id"])
                self.store.update(record["task_id"], status="unknown", failure_layer="mcp")

    def _active_count(self) -> int:
        return sum(not job.done.is_set() for job in self.active.values())

    def start(self, *, task: str, input_paths: list[str], workspace: str | None = None,
              permission_mode: str = "read-only", timeout_seconds: int = 600,
              checkpoint_id: str | None = None, task_id: str | None = None,
              session_id: str | None = None) -> dict:
        if not isinstance(task, str) or not task.strip() or len(task.encode("utf-8")) > MAX_TASK_BYTES:
            raise BridgeError("task must be non-empty UTF-8 text within the 512 KiB limit")
        if not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS:
            raise BridgeError("timeout_seconds must be between 1 and 600")
        if permission_mode not in {"read-only", "workspace-write"}:
            raise BridgeError("unsupported permission mode")
        source = Path(workspace or os.getcwd()).expanduser().resolve(strict=True)
        if not source.is_dir():
            raise BridgeError("workspace must be an existing directory")
        with self.lock:
            if self._active_count() >= self.max_concurrent:
                raise BridgeError("bridge concurrency limit reached")
            if task_id:
                record = self.store.get(task_id)
                pid = record.get("process_id")
                if record["status"] == "unknown" and _pid_active(pid):
                    raise BridgeError("previous process may still be active; inspect and stop it before resuming")
                if not record["session_id"]:
                    raise BridgeError("task has no persisted DSH session ID; start a new task instead")
                if Path(record["source_workspace"]).resolve() != source:
                    raise BridgeError("follow-up must use the same source workspace")
                if permission_mode != record["requested_permission_mode"]:
                    raise BridgeError("follow-up permission mode must match the original request")
                record = self.store.begin_attempt(task_id, session_id=record["session_id"],
                                                  checkpoint_id=checkpoint_id)
            else:
                record = self.store.create(source, input_paths, permission_mode)
                task_id = record["task_id"]
                job_dir = self._job_dir(task_id)
                job_dir.mkdir(mode=0o700)
                workspace_dir = job_dir / "workspace"
                try:
                    _safe_copy_inputs(source, record["input_paths"], workspace_dir)
                    shutil.copytree(workspace_dir, job_dir / "baseline")
                except BaseException:
                    shutil.rmtree(job_dir, ignore_errors=True)
                    self.store.update(task_id, status="failed", failure_layer="mcp")
                    raise
                record = self.store.begin_attempt(task_id, checkpoint_id=checkpoint_id)
            attempt = record["attempt"]
            progress_path = self._progress_path(task_id, attempt)
            cmd = [sys.executable, str(self.worker_script), "--permission-mode", permission_mode,
                   "--timeout-seconds", str(timeout_seconds), "--progress-file", str(progress_path)]
            if session_id or record.get("session_id"):
                cmd.extend(["--session-id", session_id or record["session_id"]])
            active = None
            try:
                proc, guard = spawn_process(
                    cmd, cwd=self._job_dir(task_id) / "workspace",
                    env=child_environment(os.environ, permission_mode),
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    shell=False)
                try:
                    proc.stdin.write(task.encode("utf-8"))
                    proc.stdin.close()
                except (BrokenPipeError, OSError) as exc:
                    guard.close()
                    proc.wait(timeout=5)
                    raise BridgeError("worker exited before accepting the task input") from exc
                active = ActiveJob(proc, guard, threading.Event(), threading.Event())
                self.active[task_id] = active
                self.store.update(task_id, process_id=proc.pid)
                active.thread = threading.Thread(target=self._monitor,
                    args=(task_id, attempt, timeout_seconds, active), daemon=True)
                active.thread.start()
            except (OSError, RuntimeError, BridgeError) as exc:
                if active is not None:
                    try:
                        active.guard.close()
                    except OSError:
                        pass
                self.store.update(task_id, status="failed", process_id=None, failure_layer="mcp")
                raise BridgeError("could not start the bounded worker process") from exc
            return self._public(self.store.get(task_id))

    def _monitor(self, task_id: str, attempt: int, timeout_seconds: int, active: ActiveJob) -> None:
        stdout = b""
        report = {}
        wrapper_timed_out = False
        try:
            try:
                stdout, _stderr = active.proc.communicate(timeout=timeout_seconds + 20)
            except subprocess.TimeoutExpired:
                wrapper_timed_out = True
                try:
                    active.guard.close()
                except OSError:
                    pass
                try:
                    stdout, _stderr = active.proc.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    active.proc.kill()
                    stdout, _stderr = active.proc.communicate(timeout=2)
            if stdout:
                try:
                    candidate = json.loads(stdout.decode("ascii"))
                    if isinstance(candidate, dict):
                        report = candidate
                except (UnicodeError, json.JSONDecodeError):
                    pass
            if wrapper_timed_out:
                report = {"status": "unknown", "failure_layer": "mcp", "exit_code": active.proc.returncode,
                          "cleanup_errors": ["wrapper_deadline_exceeded"]}
            try:
                active.guard.close()
            except OSError:
                report.setdefault("cleanup_errors", []).append("bridge_guard_close_failed")
            events = read_progress_file(self._progress_path(task_id, attempt))
            record = self.store.ingest_progress(task_id, events)
            session_id = report.get("session_id") or record.get("session_id")
            result_path, patch_path, outputs_zip, changed = _write_artifacts(
                self._job_dir(task_id), attempt, report, stdout)
            report["changed_paths"] = changed
            report["outputs_zip"] = str(outputs_zip)
            (result_path.parent / "result.json").write_text(
                json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
            cancelled = active.cancelled.is_set()
            raw_status = report.get("status", "failed")
            status = "timed_out" if raw_status == "timeout" else raw_status
            if cancelled:
                status = "cancelled"
            if status not in {"completed", "failed", "timed_out", "cancelled", "unknown"}:
                status = "failed"
            layer = report.get("failure_layer")
            if layer not in {"wrapper", "protocol", "dsh", "wrapper_cleanup", "mcp", "unknown", None}:
                layer = "unknown"
            changes = {"status": status, "process_id": None, "session_id": session_id,
                       "failure_layer": layer, "final_reason": report.get("final_reason"),
                       "exit_code": report.get("exit_code"), "result_path": str(result_path),
                       "patch_path": str(patch_path)}
            self.store.update(task_id, **changes)
        except Exception:
            try:
                record = self.store.get(task_id)
                if record["status"] == "running":
                    self.store.update(task_id, status="unknown", failure_layer="mcp", process_id=None)
            except Exception:
                pass
        finally:
            try:
                if not active.proc.stdin.closed:
                    active.proc.stdin.close()
            except (AttributeError, OSError):
                pass
            active.done.set()
            with self.lock:
                self.active.pop(task_id, None)

    def status(self, task_id: str) -> dict:
        record = self._sync_progress(task_id)
        active = task_id in self.active and not self.active[task_id].done.is_set()
        return self._public(record, process_active=(None if active else _pid_active(record.get("process_id"))))

    def list(self, limit: int = 50) -> list[dict]:
        return [self._public(self._sync_progress(record["task_id"]))
                for record in self.store.list(limit=limit)]

    def wait(self, task_id: str, wait_seconds: int = 0) -> dict:
        if not isinstance(wait_seconds, int) or not 0 <= wait_seconds <= MAX_WAIT_SECONDS:
            raise BridgeError("wait_seconds must be between 0 and 30")
        active = self.active.get(task_id)
        if active and wait_seconds:
            active.done.wait(wait_seconds)
        return self.status(task_id)

    def result(self, task_id: str) -> dict:
        record = self.store.get(task_id)
        if record["status"] in {"queued", "running"}:
            raise BridgeError("task is still running; call status or wait first")
        if not record["result_path"]:
            return {"task_id": task_id, "status": record["status"], "session_id": record["session_id"],
                    "failure_layer": record["failure_layer"], "result_available": False}
        path = Path(record["result_path"])
        if path.is_symlink() or self.store.root not in path.resolve().parents:
            raise BridgeError("result artifact path is unsafe")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BridgeError("result artifact is unavailable or corrupt") from exc
        answer = data.get("answer")
        truncated = isinstance(answer, str) and len(answer) > MAX_RETURN_TEXT
        changed_paths = data.get("changed_paths", [])
        if not isinstance(changed_paths, list):
            changed_paths = []
        return {"task_id": task_id, "status": record["status"], "failure_layer": record["failure_layer"],
                "session_id": record["session_id"], "final_reason": record["final_reason"],
                "answer": answer[:MAX_RETURN_TEXT] if truncated else answer,
                "answer_truncated": truncated, "changed_paths": changed_paths[:MAX_RETURN_PATHS],
                "changed_paths_count": len(changed_paths),
                "changed_paths_truncated": len(changed_paths) > MAX_RETURN_PATHS,
                "result_path": record["result_path"], "patch_path": record["patch_path"],
                "outputs_zip": data.get("outputs_zip"), "cleanup_errors": data.get("cleanup_errors", [])}

    def cancel(self, task_id: str) -> dict:
        active = self.active.get(task_id)
        if active is None:
            record = self.store.get(task_id)
            alive = _pid_active(record.get("process_id"))
            if alive:
                return {"task_id": task_id, "status": "unknown", "cancelled": False,
                        "reason": "previous process may still be active but is not owned by this MCP server"}
            return {"task_id": task_id, "status": record["status"], "cancelled": False,
                    "reason": "no active process owned by this MCP server"}
        active.cancelled.set()
        try:
            active.guard.close()
        except OSError:
            pass
        active.done.wait(5)
        return self.status(task_id)

    def close(self) -> None:
        with self.lock:
            active_jobs = list(self.active.items())
        for task_id, active in active_jobs:
            active.cancelled.set()
            try:
                active.guard.close()
            except OSError:
                pass
            active.done.wait(5)
            try:
                record = self.store.get(task_id)
                if record["status"] == "running":
                    self.store.update(task_id, status="unknown", failure_layer="mcp")
            except JobStoreError:
                pass

    def call(self, name: str, args: dict) -> dict:
        if not isinstance(args, dict):
            raise BridgeError("tool arguments must be an object")
        if name == "deepseek_task_start":
            return self.start(**args)
        if name == "deepseek_task_status":
            return self.status(args["task_id"])
        if name == "deepseek_task_list":
            return {"jobs": self.list(args.get("limit", 50))}
        if name == "deepseek_task_wait":
            return self.wait(args["task_id"], args.get("wait_seconds", 0))
        if name == "deepseek_task_followup":
            args = dict(args)
            task_id = args.pop("task_id")
            record = self.store.get(task_id)
            return self.start(task_id=task_id, task=args.pop("task"), input_paths=record["input_paths"],
                              workspace=record["source_workspace"],
                              permission_mode=args.pop("permission_mode", record["requested_permission_mode"]),
                              timeout_seconds=args.pop("timeout_seconds", MAX_TIMEOUT_SECONDS),
                              checkpoint_id=args.pop("checkpoint_id", None), session_id=record["session_id"])
        if name == "deepseek_task_result":
            return self.result(args["task_id"])
        if name == "deepseek_task_cancel":
            return self.cancel(args["task_id"])
        raise BridgeError("unknown tool")


def _tool_result(request_id, value, is_error=False):
    text = json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    return {"jsonrpc": "2.0", "id": request_id,
            "result": {"content": [{"type": "text", "text": text}],
                       "isError": is_error}}


def _rpc_error(request_id, code, message):
    return {"jsonrpc": "2.0", "id": request_id,
            "error": {"code": code, "message": message}}


def handle_rpc(manager: JobManager, message: dict) -> dict | None:
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _rpc_error(message.get("id") if isinstance(message, dict) else None, -32600, "invalid request")
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params", {})
    if not isinstance(params, dict):
        return _rpc_error(request_id, -32602, "params must be an object")
    if method == "notifications/initialized" or (isinstance(method, str) and method.startswith("notifications/")):
        return None
    if method == "initialize":
        requested_version = params.get("protocolVersion")
        supported_versions = {"2024-11-05", "2025-03-26", "2025-06-18"}
        if requested_version not in supported_versions:
            return _rpc_error(request_id, -32602, "unsupported MCP protocol version")
        return {"jsonrpc": "2.0", "id": request_id,
                "result": {"protocolVersion": requested_version, "capabilities": {"tools": {"listChanged": False}},
                           "serverInfo": {"name": "adaptive-agent-orchestrator-deepseek", "version": "1"}}}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOL_DEFINITIONS}}
    if method == "tools/call":
        try:
            value = manager.call(params.get("name"), params.get("arguments", {}))
            return _tool_result(request_id, value)
        except (BridgeError, JobStoreError, KeyError, TypeError, ValueError) as exc:
            return _tool_result(request_id, {"error": str(exc)}, is_error=True)
        except Exception:
            return _tool_result(request_id, {"error": "internal bridge error; inspect local bridge diagnostics"}, is_error=True)
    if not isinstance(request_id, (str, int)):
        return None
    return _rpc_error(request_id, -32601, "method not found")


def run_stdio(manager: JobManager) -> int:
    try:
        max_line = MAX_RPC_LINE_BYTES
        while True:
            raw = sys.stdin.buffer.readline(max_line + 1)
            if not raw:
                break
            if len(raw) > max_line:
                while raw and not raw.endswith(b"\n"):
                    raw = sys.stdin.buffer.readline(max_line + 1)
                continue
            try:
                message = json.loads(raw.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError):
                response = _rpc_error(None, -32700, "parse error")
            else:
                response = handle_rpc(manager, message)
            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=True, separators=(",", ":")) + "\n")
                sys.stdout.flush()
    finally:
        manager.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-root", type=Path, default=default_job_root())
    parser.add_argument("--worker-script", type=Path, default=Path(__file__).with_name("deepseek_worker.py"))
    parser.add_argument("--max-concurrent", type=int, default=MAX_CONCURRENT)
    args = parser.parse_args(argv)
    try:
        manager = JobManager(JobStore(args.job_root), args.worker_script, args.max_concurrent)
        return run_stdio(manager)
    except (OSError, JobStoreError, BridgeError) as exc:
        print(f"deepseek MCP bridge startup failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
