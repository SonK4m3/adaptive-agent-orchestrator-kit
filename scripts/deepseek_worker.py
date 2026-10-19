"""Run one bounded DeepSeek Harness task and return only its final answer.

This wrapper is intended for a Codex subagent. It keeps DSH's verbose NDJSON
events and reasoning diagnostics out of the parent context, defaults to a
read-only DSH permission mode, and contains the child process tree on timeout.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time
import threading

from process_guard import spawn_process

MAX_STDOUT = 1024 * 1024
MAX_STDERR = 256 * 1024
MAX_EVENT = 64 * 1024
MAX_EVENTS = 4096
# No wildcard DSH_*, provider keys, shell startup or runtime injection variables.
ENV_ALLOWLIST = frozenset({
    "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "SYSTEMDRIVE",
    "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR",
    "LANG", "LC_ALL", "LC_CTYPE", "XDG_CONFIG_HOME", "XDG_DATA_HOME",
    "XDG_CACHE_HOME", "DEEPSEEK_API_KEY",
})
EVENT_TYPES = frozenset({"session", "status", "thinking", "text", "delta",
                         "tool_call", "tool_result", "final", "error"})


def child_environment(source, permission):
    environment = {(key.upper() if os.name == "nt" else key): value
                   for key, value in source.items()
                   if (key.upper() if os.name == "nt" else key) in ENV_ALLOWLIST}
    environment["DSH_PERMISSION_MODE"] = permission
    return environment


def emit(report):
    # ASCII JSON survives legacy Windows stdout encodings; json.loads restores Unicode.
    print(json.dumps(report, ensure_ascii=True, allow_nan=False))


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError("nonfinite JSON")

ERROR_SIGNALS = {
    "authentication": ("unauthorized", "401", "invalid api key"),
    "access_policy": ("permission denied", "approval required", "blocked by policy", "sandbox"),
    "rate_limit": ("rate limit", "429", "quota exceeded"),
    "network": ("connection refused", "network error", "econnreset", "enotfound"),
    "timeout": ("timed out", "timeout"),
    "configuration": ("unknown profile", "invalid config", "profile is required"),
}


def final_text(event: dict) -> str | None:
    """Extract the user-facing answer from known final-event representations."""
    for key in ("text", "message", "answer", "final"):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    content = event.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        chunks = [item.get("text", "") for item in content
                  if isinstance(item, dict) and isinstance(item.get("text"), str)]
        value = "\n".join(chunk for chunk in chunks if chunk.strip()).strip()
        if value:
            return value
    return None


def read_result(stdout: bytes) -> dict:
    """Fail closed on malformed, conflicting or oversized NDJSON; never echo bad input."""
    answer = session_id = None
    event_types = []
    errors = 0
    job_failed = False
    lines = stdout.splitlines()
    if len(lines) > MAX_EVENTS:
        errors += 1
    for raw_line in lines[:MAX_EVENTS]:
        if not raw_line.strip():
            continue
        try:
            if len(raw_line) > MAX_EVENT:
                raise ValueError("event too large")
            event = json.loads(raw_line.decode("utf-8", errors="strict"),
                               object_pairs_hook=unique_object, parse_constant=reject_constant)
        except (ValueError, RecursionError):
            errors += 1
            continue
        if not isinstance(event, dict):
            errors += 1
            continue
        kind = event.get("type")
        if not isinstance(kind, str) or not re.fullmatch(r"[a-z_]{1,64}", kind):
            errors += 1
            continue
        event_types.append(kind if kind in EVENT_TYPES else "other")
        if kind == "session":
            candidate = event.get("session_id", event.get("sessionId", event.get("id")))
            if not isinstance(candidate, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", candidate):
                errors += 1
            elif session_id is not None and session_id != candidate:
                errors += 1
            else:
                session_id = candidate
        elif kind == "final":
            candidate = final_text(event)
            if answer is not None or candidate is None:
                errors += 1
            else:
                answer = candidate
        elif kind == "error":
            job_failed = True
    return {"answer": answer, "session_id": session_id, "event_types": event_types,
            "protocol_errors": errors, "job_failed": job_failed}


def capture(proc, guard, task, timeout, stdout_limit, stderr_limit):
    """Drain both pipes concurrently with fixed memory caps, including blocked stdin."""
    buffers = [bytearray(), bytearray()]
    counts = [0, 0]
    overflow = threading.Event()
    io_failed = threading.Event()
    limits = (stdout_limit, stderr_limit)

    def drain(pipe, index):
        try:
            while chunk := pipe.read1(4096):
                counts[index] += len(chunk)
                remaining = limits[index] - len(buffers[index])
                buffers[index].extend(chunk[:max(0, remaining)])
                if counts[index] > limits[index]:
                    overflow.set()
                    break
        except (OSError, ValueError):
            io_failed.set()
        finally:
            pipe.close()

    def send():
        try:
            proc.stdin.write(task)
            proc.stdin.flush()
        except BrokenPipeError:
            pass  # Child exit and final-event validation determine success.
        except (OSError, ValueError):
            io_failed.set()
        finally:
            try:
                proc.stdin.close()
            except OSError:
                pass

    threads = [threading.Thread(target=drain, args=(proc.stdout, 0), daemon=True),
               threading.Thread(target=drain, args=(proc.stderr, 1), daemon=True),
               threading.Thread(target=send, daemon=True)]
    deadline = time.monotonic() + timeout
    for thread in threads:
        thread.start()
    reason = None
    cleanup_errors = []
    try:
        while True:
            if overflow.is_set():
                reason = "output_limit"
                break
            if io_failed.is_set():
                reason = "io_error"
                break
            if proc.poll() is not None and not any(t.is_alive() for t in threads):
                break
            if time.monotonic() >= deadline:
                reason = "timeout"
                break
            time.sleep(0.01)
    finally:
        # Close the entire tree before joining pipe readers (descendants may hold pipes).
        try:
            guard.close()
        except OSError:
            cleanup_errors.append("guard_close_failed")
        if proc.poll() is None:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            except OSError:
                cleanup_errors.append("kill_failed")
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            # One bounded retry; never report completion while cleanup is unresolved.
            try:
                proc.kill()
                proc.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                cleanup_errors.append("reap_timeout")
        for thread in threads:
            thread.join(timeout=0.5)
        if any(t.is_alive() for t in threads):
            cleanup_errors.append("pipe_thread_alive")
    return bytes(buffers[0]), bytes(buffers[1]), counts, reason, cleanup_errors


def classify_stderr(stderr: bytes) -> list[str]:
    """Return coarse allowlisted signals without forwarding raw diagnostics."""
    text = stderr.decode("utf-8", errors="replace").lower()
    return [category for category, markers in ERROR_SIGNALS.items()
            if any(marker in text for marker in markers)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--permission-mode", choices=("read-only", "workspace-write"),
                        default="read-only", help="DSH permission preset; read-only by default")
    parser.add_argument("--timeout-seconds", type=int, default=600,
                        help="maximum run time (1-600 seconds; default: 600)")
    parser.add_argument("--max-stdout-bytes", type=int, default=MAX_STDOUT)
    parser.add_argument("--max-stderr-bytes", type=int, default=MAX_STDERR)
    args = parser.parse_args(argv)
    if not 1 <= args.timeout_seconds <= 600:
        parser.error("--timeout-seconds must be between 1 and 600")
    if not 1 <= args.max_stdout_bytes <= MAX_STDOUT or not 1 <= args.max_stderr_bytes <= MAX_STDERR:
        parser.error("output limits must be positive and no larger than the defaults")

    try:
        task = (sys.stdin.buffer.read(MAX_STDOUT + 1).decode("utf-8")
                if hasattr(sys.stdin, "buffer") else sys.stdin.read(MAX_STDOUT + 1))
    except UnicodeDecodeError:
        print("error: task must be UTF-8", file=sys.stderr)
        return 2
    if len(task.encode("utf-8")) > MAX_STDOUT:
        print("error: task exceeds input limit", file=sys.stderr)
        return 2
    if not task.strip():
        print("error: provide the delegated task on stdin", file=sys.stderr)
        return 2
    executable = shutil.which("dsh")
    if executable is None:
        print("error: dsh CLI not found on PATH", file=sys.stderr)
        return 127

    environment = child_environment(os.environ, args.permission_mode)
    command: str | list[str] = [executable, "--profile", "headless", "--json", "-"]
    shell = False
    if os.name == "nt" and Path(executable).suffix.lower() in {".cmd", ".bat"}:
        # Windows batch launchers require cmd.exe; delegated task content stays on stdin.
        command = subprocess.list2cmdline(command)
        shell = True
    started = time.monotonic()
    proc = guard = None
    permissions = {"requested_permission_mode": args.permission_mode,
                   "effective_permission_mode": None,
                   "permission_verification": "unverified"}
    try:
        proc, guard = spawn_process(command, cwd=Path.cwd(), env=environment,
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, shell=shell)
        stdout, stderr, counts, reason, cleanup_errors = capture(
            proc, guard, task.encode("utf-8"), args.timeout_seconds,
            args.max_stdout_bytes, args.max_stderr_bytes)
        guard = None  # capture owns cleanup, including failure paths.
        elapsed_ms = round((time.monotonic() - started) * 1000)
        parsed = read_result(stdout)
        success = not reason and not cleanup_errors and proc.returncode == 0 and parsed["answer"] and not (
            parsed["protocol_errors"] or parsed["job_failed"])
        report = {"status": reason or ("cleanup_error" if cleanup_errors else
                                       "completed" if success else "failed"),
                  "exit_code": proc.returncode, "elapsed_ms": elapsed_ms,
                  **permissions,
                  "session_id": parsed["session_id"], "event_types": parsed["event_types"],
                  "session_evidence": "reported" if parsed["session_id"] else "missing",
                  "cleanup_errors": cleanup_errors,
                  "protocol_errors": parsed["protocol_errors"],
                  "job_failed": parsed["job_failed"],
                  "stdout_bytes_observed": counts[0],
                  "stderr_bytes_suppressed": counts[1],
                  "output_capture_complete": reason is None and not cleanup_errors,
                  "stderr_signals": classify_stderr(stderr)}
        if success:
            report["answer"] = parsed["answer"]
        emit(report)
        return 0 if success else (124 if reason == "timeout" else 1)
    except OSError as exc:
        elapsed_ms = round((time.monotonic() - started) * 1000)
        emit({"status": "failed", "error_type": type(exc).__name__,
              "elapsed_ms": elapsed_ms, **permissions})
        return 1
    finally:
        if guard is not None:
            try:
                guard.close()
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
