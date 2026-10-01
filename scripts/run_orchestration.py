"""Isolated graph harness; prepare-only never invokes a model. No automatic retry.

Scopes are audited, not OS isolation. Raw evidence stays in ignored dist/.
Credential copying requires --auth-home opt-in. No global writes or rubric inference.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import tomllib
import uuid

from runtime_probe import inspect_runtime
from runtime_preflight import preflight
from process_guard import spawn_process

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "eval/fixtures/graph-behavior"
ORACLES = ROOT / "eval/oracles/graph-behavior"
SCENARIOS = ("root-only", "independent", "verification", "adaptation")
PROFILE = "adaptive"
PIN = ("gpt-6.1-sol", "medium")
LIVE_TREE_SUPPORTED = os.name == 'nt'
GRAPH_PATHS = ("graph.json", "graph-record.json", "graph-1.json", "graph-2.json")


def stamp():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def hashes(folder):
    """Hash links as links; never follow targets. Exclude Git metadata."""
    result = {}
    def visit(directory):
        for p in sorted(directory.iterdir()):
            rel = p.relative_to(folder).as_posix()
            if rel == ".git":
                continue
            if p.is_symlink() or getattr(p, "is_junction", lambda: False)():
                result[rel] = "link:" + os.readlink(p)
            elif p.is_dir():
                visit(p)
            elif p.is_file():
                result[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    visit(folder)
    return result


def config_hash(home):
    # Only user configuration; never auth.json, tokens, keychain or session files.
    path = home / "config.toml"
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def prepare_auth(home, env, capabilities, auth_home=None):
    """Select existing env auth or an explicitly opted-in private ephemeral copy.

    No file contents are read by this code. The CLI alone consumes credentials.
    Never return a credential value/path or copy credentials into dist evidence.
    Caller owns TemporaryDirectory cleanup on every exit.
    """
    for name in capabilities.get("auth_env_capabilities", []):
        if name in env:
            return {"method": "inherited runtime auth environment", "variable": name,
                    "authenticated": "unconfirmed"}
    if auth_home is None:
        raise RuntimeError("No supported auth environment present; opt-in --auth-home is required for private ephemeral auth reuse")
    source = Path(auth_home) / "auth.json"
    if not source.is_file() or source.is_symlink():
        raise RuntimeError("Opt-in auth source is missing or linked; no inference attempted")
    destination = home / "auth.json"
    shutil.copy2(source, destination)
    if os.name != "nt":
        os.chmod(destination, 0o600)
    return {"method": "opt-in private ephemeral auth copy", "authenticated": "unconfirmed",
            "cleanup": "temporary home context; never saved in evidence"}


def graph_records(workspace, evidence, label):
    """Optional agreed validator API; no schema assumptions when unavailable."""
    result = {"status": "missing", "snapshots": [], "coverage": "missing record coverage"}
    validator_path = ROOT / "scripts/validate_graph_record.py"
    validator = None
    if validator_path.is_file():
        spec = importlib.util.spec_from_file_location("graph_validator", validator_path)
        validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validator)
    snapshots = []
    for name in GRAPH_PATHS:
        path = workspace / name
        if not path.is_file() or path.is_symlink():
            continue
        target = evidence / (label + "-" + name)
        shutil.copy2(path, target)
        entry = {"source": name, "evidence": target.name}
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
            snapshots.append((data, entry))
        except ValueError:
            entry.update(validation="fail", errors=["invalid JSON"])
        result["snapshots"].append(entry)
    # Revisions are ordered only when runtime artifacts give usable revision IDs.
    ordered = sorted(snapshots, key=lambda s: s[0].get("revision", 0) if isinstance(s[0], dict)
                     and type(s[0].get("revision")) is int else 0)
    previous = None
    seen = {}
    for data, entry in ordered:
        if isinstance(data, dict) and isinstance(data.get('task_id'), str) and type(data.get('revision')) is int:
            key = (data['task_id'], data['revision'])
            if key in seen:
                if data == seen[key]:
                    entry.update(validation='duplicate-identical; compared once', revision=data['revision'])
                else:
                    entry.update(validation='fail', errors=['conflicting contents for same task/revision'])
                continue
            seen[key] = data
        if validator:
            errors = validator.validate_record(data, previous=previous)
            entry.update(validation="fail" if errors else "structure-valid; evidence not verified", errors=errors)
        else:
            entry["validation"] = "unrun; root validator unavailable"
        if isinstance(data, dict):
            entry["revision"] = data.get("revision")
            previous = data
    if result["snapshots"]:
        result.update(status="present", coverage="structural validation only; trace linkage review required")
    return result


def changed_paths(before, after):
    return sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))


def trace_summary(paths):
    """Recognize explicit collab items only. Unknown dialects never mean zero agents.

    Deduplicate started/completed notifications and resume replay. Collab model and
    reasoningEffort fields are REQUESTED per runtime protocol, not effective values.
    Usage is reported per turn; never sum potentially overlapping child/session data.
    """
    calls, sessions, usage, unknown, failures = {}, [], [], [], []
    tools = {"spawnAgent": "spawn", "spawn_agent": "spawn", "sendInput": "send",
             "send_input": "send", "sendMessage": "send", "wait": "wait",
             "closeAgent": "close", "close_agent": "close", "resumeAgent": "resume",
             "resume_agent": "resume", "interruptAgent": "interrupt"}
    for path in paths:
        for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            source = {"file": path.name, "line": line_no}
            try:
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError("not an object")
            except (ValueError, TypeError):
                unknown.append(dict(source, reason="non-JSON object"))
                continue
            if event.get("type") == "thread.started" and isinstance(event.get("thread_id"), str):
                sessions.append(event["thread_id"])
            if event.get("type") in ("turn.failed", "error"):
                failures.append(dict(source, type=event["type"]))
            if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
                usage.append(dict(source, usage=event["usage"], scope="reported turn; child inclusion unknown"))
            item = event.get("item")
            if not isinstance(item, dict) and isinstance(event.get("params"), dict):
                item = event["params"].get("item")
            if not isinstance(item, dict):
                if event.get("type") not in ("thread.started", "turn.started", "turn.completed", "turn.failed", "error"):
                    unknown.append(dict(source, reason="unrecognized envelope"))
                continue
            dialect = item.get("type")
            if dialect not in ("collabAgentToolCall", "collab_tool_call"):
                if dialect not in ("agent_message", "reasoning", "command_execution", "file_change",
                                   "mcp_tool_call", "web_search", "todo_list", "agentMessage", "reasoningSummary"):
                    unknown.append(dict(source, reason="unrecognized item type"))
                continue
            call_id, tool, status = item.get("id"), item.get("tool"), item.get("status")
            if not isinstance(call_id, str) or tool not in tools or status not in (
                    "inProgress", "in_progress", "completed", "failed", "interrupted"):
                unknown.append(dict(source, reason="unsupported collab fields"))
                continue
            sender = item.get("senderThreadId", item.get("sender_thread_id"))
            if sender is not None and not isinstance(sender, str):
                unknown.append(dict(source, reason="unsupported sender identity"))
                continue
            key = (sender, call_id)
            previous = calls.get(key)
            if previous and previous["status"] in ("completed", "failed", "interrupted"):
                continue
            calls[key] = dict(source, id=call_id, tool=tools[tool], status=status, sender=sender,
                              agent_ids=item.get("receiverThreadIds", item.get("receiver_thread_ids", [])),
                              states=item.get("agentsStates", item.get("agents_states", {})),
                              role_requested=item.get("agentType", item.get("agent_type", "unknown")),
                              model_requested=item.get("model", "unknown"),
                              effort_requested=item.get("reasoningEffort", item.get("reasoning_effort", "unknown")))
    observed = {tool: sum(c["tool"] == tool for c in calls.values())
                for tool in ("spawn", "send", "wait", "close", "resume", "interrupt")}
    completed = {tool: sum(c["tool"] == tool and c["status"] == "completed" for c in calls.values())
                 for tool in observed}
    return {"session_ids": list(dict.fromkeys(sessions)), "calls": list(calls.values()),
            "observed_call_counts": observed,
            "observed_completed_call_counts": completed,
            "actual_total_counts": "unknown; CLI trace completeness is not attested",
            "lifecycle_closure": "unknown; inspect successful close and receiver states",
            "unrecognized": unknown, "runtime_failures": failures,
            "usage_output": usage, "usage_total": None,
            "usage_note": "No aggregation: turn/session/child usage may overlap",
            "confirmed_resources": "unknown; collab model fields are requests"}


def cleanup(proc, deadline, platform=None):
    """Terminate descendants with bounded waits within the shared deadline."""
    platform = platform or os.name
    result = {"method": "taskkill /T /F" if platform == "nt" else "POSIX process group", "status": "unknown"}
    remaining = lambda: max(0.01, deadline - time.monotonic())
    try:
        if platform == "nt":
            killed = subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=remaining(), check=False)
            result["tree_kill_exit_code"] = killed.returncode
            if killed.returncode:
                proc.kill()
        else:
            os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=remaining())
        result["status"] = "termination requested; descendants not independently attested"
    except (OSError, subprocess.TimeoutExpired) as exc:
        result.update(status="incomplete", error_type=type(exc).__name__)
        try:
            proc.kill()
        except OSError:
            pass
        try:
            proc.wait(timeout=remaining())
        except (OSError, subprocess.TimeoutExpired):
            result['parent_reaped'] = False
        else:
            result['parent_reaped'] = True
    return result


def execute(command, workspace, env, evidence, index, deadline):
    stdout_path, stderr_path = evidence / f"segment-{index}.jsonl", evidence / f"segment-{index}.stderr"
    record = {"started_at": stamp(), "stdout": stdout_path.name, "stderr": stderr_path.name,
              "timeout": False, "exit_code": None}
    with stdout_path.open("w", encoding="utf-8") as out, stderr_path.open("w", encoding="utf-8") as err:
        proc, guard = spawn_process(command, cwd=workspace, env=env, stdin=subprocess.DEVNULL,
                                stdout=out, stderr=err, start_new_session=os.name != "nt",
                                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
        try:
            # Five seconds reserved for tree cleanup; no retry on failure/timeout.
            proc.wait(timeout=max(0.01, deadline - time.monotonic() - 5))
        except subprocess.TimeoutExpired:
            record["timeout"] = True
            record["cleanup"] = cleanup(proc, deadline)
        finally:
            try:
                guard.close()
                record['process_tree'] = 'owned job/group closed on exit; external daemon sessions unverified'
            except OSError:
                record['process_tree'] = 'cleanup failed'
                record['timeout'] = True
        record["exit_code"] = proc.returncode
    record["ended_at"] = stamp()
    return record


def command_for(cli, workspace, model, effort, prompt, session=None):
    base = [cli, "--no-daemon", "exec"] + (["resume"] if session else [])
    base += ["--strict-config", "--ignore-rules", "--json", "-m", model,
             "-c", f'model_reasoning_effort="{effort}"', "-c", 'approval_policy="never"',
             "-c", 'sandbox_mode="workspace-write"']
    if session:
        # resume has no --profile/--cd; use cwd and flattened temporary base config.
        base += [session, prompt]
    else:
        base += ["-p", PROFILE, "-C", str(workspace), "-s", "workspace-write", prompt]
    return base


def prepare(evidence, scenario, probe):
    workspace = evidence / "workspace"
    shutil.copytree(FIXTURES / scenario, workspace)
    spec = json.loads((ORACLES / "criteria.json").read_text(encoding="utf-8"))[scenario]
    allowed = list(spec["allowed"])
    if probe == "reviewer":
        (workspace / "auth.py").write_text("def authorize(role, action):\n    return role == 'admin' or (role == 'viewer' and action == 'read')\n", encoding="utf-8")
        allowed = ["assessment.json", *GRAPH_PATHS]
    (workspace / "AGENTS.md").write_text(
        "Read the installed adaptive-agent-orchestrator skill and follow its guidance. "
        "No external writes, network actions, package installs or recursive delegation. "
        "Do not inspect authentication files or credential environment variables. Use python -B for verification. "
        "Edit only the exact paths listed in the harness prompt. "
        "If supported, save milestone graph snapshots to graph-record.json; missing records are coverage gaps.\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(workspace)], check=True, timeout=15,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return workspace, allowed


def install_home(home, evidence):
    command = [sys.executable, "-B", str(ROOT / "scripts/manage.py"), "install", "--target", str(home),
               "--profile", PROFILE, "--with-profile-config"]
    with (evidence / "installation.stdout").open("w", encoding="utf-8") as out, \
            (evidence / "installation.stderr").open("w", encoding="utf-8") as err:
        # Manager logs are not credentials, but redact its private temporary path.
        result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
        out.write(result.stdout.replace(str(home), "<private temporary home>"))
        err.write(result.stderr.replace(str(home), "<private temporary home>"))
    if result.returncode:
        raise RuntimeError("Manager installation failed; root must refresh/validate the package manifest before runs")
    profile = home / f"{PROFILE}.config.toml"
    # ONLY temporary config; resume lacks --profile. Never copy user configuration.
    (home / "config.toml").write_bytes(profile.read_bytes())
    roles = {}
    for path in sorted((home / "agents").glob("*.toml")):
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        roles[data.get("name", path.stem)] = {k: data.get(k) for k in ("model", "model_reasoning_effort", "sandbox_mode")}
    return {"profile": PROFILE, "profile_data": tomllib.loads(profile.read_text(encoding="utf-8")),
            "roles": roles, "runtime_resolution": "unconfirmed"}


def prompt_for(scenario, probe, allowed):
    prompt = "Implement the public requirements in TASK.md. Report criterion evidence and unresolved work. "
    if probe == "worker":
        prompt = ("Forced plumbing probe, not autonomous routing: dispatch named ao_worker with TASK.md "
                  "and exclusive label.txt ownership. Wait, independently check its artifact, then close it "
                  "and report runtime IDs. Do not substitute default role as named-role success. ")
    elif probe == "reviewer":
        prompt = ("Forced plumbing probe: dispatch named ao_reviewer read-only to assess auth.py against TASK.md. "
                  "Give requirements and artifact only, without implementer confidence. Require requirement IDs, "
                  "path/symbol references, severity and evidence. Wait and close the reviewer. Root alone writes "
                  "assessment.json as {findings: [{requirement, path, symbol, severity, evidence}]}. "
                  "Do not fix auth.py or substitute a default reviewer as named-role success. ")
    if scenario == "adaptation":
        prompt += ("First implement revision 1, verify it, then pause for user acceptance: write checkpoint.json "
                   'as {"revision": 1, "stage": "awaiting-user-acceptance"} and finish this turn. '
                   "Do not anticipate later requirements. ")
    return prompt + "Only these paths may change: " + ", ".join(allowed) + "."


def external_checks(workspace, evidence, scenario, probe, deadline, revision=2):
    """Fail closed if runtime sandbox cannot run the credential-free oracle.

    Candidate imports run only behind an explicit filesystem/network profile.
    Never save unrestricted candidate stdout/stderr as measurement evidence.
    """
    prefix = "checkpoint-oracle" if revision == 1 else "oracle"
    if not LIVE_TREE_SUPPORTED:
        return [{'criterion': 'external-oracle', 'status': 'unrun', 'reason': 'POSIX detached-process containment not implemented'}]
    path = evidence / (prefix + "-results.json")
    try:
        cli = shutil.which('codex.exe') or shutil.which('codex')
        if not cli:
            return [{'criterion': 'external-oracle', 'status': 'unrun', 'reason': 'Oracle sandbox unavailable'}]
        with tempfile.TemporaryDirectory(prefix='ao-oracle-home-') as temporary:
            home = Path(temporary)
            output = home / 'results.json'
            env = {key: os.environ[key] for key in ('PATH', 'SystemRoot', 'WINDIR', 'COMSPEC', 'SystemDrive') if key in os.environ}
            env.update(CODEX_HOME=str(home), HOME=str(home), USERPROFILE=str(home),
                       TMP=str(home), TEMP=str(home), TMPDIR=str(home), PYTHONDONTWRITEBYTECODE='1')
            command = [cli, 'sandbox', '-C', str(workspace), '-P', 'oracle',
                       '-c', 'permissions.oracle.filesystem.":minimal"="read"',
                       '-c', 'permissions.oracle.network.enabled=false']
            for root, access in ((workspace, 'read'), (ORACLES, 'read'),
                                 (Path(sys.base_prefix), 'read'), (Path(sys.executable).parent, 'read'), (home, 'write')):
                command += ['-c', 'permissions.oracle.filesystem.' + json.dumps(str(root.resolve())) + '=' + json.dumps(access)]
            real_home = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
            command += ['-c', 'permissions.oracle.filesystem.' + json.dumps(str((real_home / 'auth.json').resolve())) + '="deny"']
            command += [sys.executable, '-I', str(ORACLES / 'check.py'), '--workspace', str(workspace),
                        '--scenario', scenario, '--revision', str(revision), '--output', str(output)]
            if probe:
                command += ['--probe', probe]
            proc, guard = spawn_process(command, cwd=workspace, env=env, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                proc.wait(timeout=max(0.01, min(20, deadline - time.monotonic() - 5)))
            except subprocess.TimeoutExpired:
                return [{"criterion": "external-oracle", "status": "unrun", "cleanup": cleanup(proc, deadline)}]
            finally:
                guard.close()
            if not output.is_file() or output.is_symlink():
                return [{"criterion": "external-oracle", "status": "unrun", "reason": "Sandboxed oracle produced no results"}]
            results = json.loads(output.read_text(encoding='utf-8'))
            if not isinstance(results, list) or any(not isinstance(item, dict) or item.get('status') not in {'pass', 'fail', 'unrun'} for item in results):
                raise ValueError('invalid oracle result')
            expected = {'root-only': {'R1-label'},
                        'independent': {'R1-duration', 'R2-duration-negative', 'R3-grouping', 'R4-grouping-negative-and-mutation', 'R5-integration'},
                        'verification': {'R1-R3-auth-matrix-negative', 'R4-input-mutation', 'R4-other-side-effects'},
                        'adaptation': {'R1-rounding-revision-' + str(revision), 'R2-conversion-negative', 'R4-revision-and-handoff'}}[scenario]
            if probe == 'reviewer':
                expected = {'P3.3-assessment-artifact', 'P3.3-independent-reviewer-attribution'}
            actual = [item.get('criterion') for item in results]
            if len(actual) != len(expected) or set(actual) != expected:
                raise ValueError('oracle criterion coverage mismatch')
            has_fail = any(item['status'] == 'fail' for item in results)
            if proc.returncode not in (0, 1) or bool(proc.returncode) != has_fail:
                raise ValueError('oracle exit/result mismatch')
            write_json(path, results)
            return results
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return [{"criterion": "external-oracle", "status": "unrun", "reason": type(exc).__name__}]


def checkpoint(workspace, trace, segment):
    path = workspace / "checkpoint.json"
    if segment["timeout"] or segment["exit_code"] != 0 or trace["runtime_failures"] or not trace["session_ids"]:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if path.is_symlink() or data != {"revision": 1, "stage": "awaiting-user-acceptance"}:
        return None
    return {"observed_at": stamp(), "session_id": trace["session_ids"][0],
            "checkpoint_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "scope_hashes": hashes(workspace)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, choices=[PIN[0]])
    parser.add_argument("--effort", default=PIN[1], choices=[PIN[1]])
    parser.add_argument("--scenario", choices=SCENARIOS, default="root-only")
    parser.add_argument("--probe", choices=("worker", "reviewer"))
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--preflight-only", action="store_true", help="Local sandbox read check only; no credentials or inference")
    parser.add_argument("--windows-sandbox", choices=("elevated", "unelevated", "mxc"), help="Explicit temporary native sandbox selection; no automatic fallback")
    parser.add_argument("--auth-home", type=Path, help="Opt-in auth.json copy into a private ephemeral home; never evidence")
    args = parser.parse_args(argv)
    if args.prepare_only and args.preflight_only:
        parser.error("--prepare-only and --preflight-only are mutually exclusive")
    if args.preflight_only and args.auth_home:
        parser.error("--preflight-only does not accept --auth-home")
    if not 6 <= args.timeout <= 600:
        parser.error("--timeout must be 6..600 seconds, including cleanup")
    if args.probe and args.scenario != ("root-only" if args.probe == "worker" else "verification"):
        parser.error("worker probe requires root-only; reviewer probe requires verification")
    evidence = ROOT / "dist" / ("graph-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex)
    evidence.mkdir(parents=True)
    user_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    user_before = config_hash(user_home)
    record = {"scenario": args.scenario, "probe": args.probe, "started_at": stamp(),
              "requested": {"model": args.model, "effort": args.effort}, "confirmed": "unknown",
              "timeout_budget_seconds": args.timeout, "segments": [], "blockers": [],
              "status": "prepared" if args.prepare_only else "incomplete", "rubric": "unrun; independent review required",
              "adaptation": {"status": "unrun", "protocol": "checkpoint then scripted external user update via same-session resume",
                             "limits": "Between turns; no authenticated in-flight injection or continuity of child agents proven"},
              "graph_record": {"status": "missing", "validation": "unrun; validator owned by root"}}
    workspace = None
    try:
        workspace, allowed = prepare(evidence, args.scenario, args.probe)
        record.update(allowed_paths=allowed, before_hashes=hashes(workspace))
        prompt = prompt_for(args.scenario, args.probe, allowed)
        (evidence / "prompt.txt").write_text(prompt, encoding="utf-8")
        with tempfile.TemporaryDirectory(prefix="ao-graph-home-") as temporary:
            home = Path(temporary)
            record["configured"] = install_home(home, evidence)
            if args.windows_sandbox:
                with (home / "config.toml").open("a", encoding="utf-8") as config:
                    config.write('\n[windows]\nsandbox = ' + json.dumps(args.windows_sandbox) + '\n')
            cli = shutil.which("codex.exe") or shutil.which("codex")
            env = dict(os.environ, CODEX_HOME=str(home), PYTHONDONTWRITEBYTECODE="1")
            capabilities = inspect_runtime(cli, home, evidence, env, record["configured"]["profile_data"])
            record["runtime"] = capabilities
            record["blockers"].extend(capabilities["blockers"])
            if not args.prepare_only:
                record["preflight"] = preflight(cli, home, workspace, evidence, args.windows_sandbox)
                if record["preflight"]["status"] != "pass":
                    record["blockers"].append("Sandbox preflight blocked: " + record["preflight"]["reason"])
                elif args.preflight_only:
                    record["status"] = "preflight-passed"
            if not args.prepare_only and not LIVE_TREE_SUPPORTED:
                record['blockers'].append('POSIX detached-process containment not implemented; live pilot disabled')
            if not args.prepare_only and not args.preflight_only and not record["blockers"]:
                record["auth"] = prepare_auth(home, env, capabilities, args.auth_home)
                started = time.monotonic()
                deadline = started + args.timeout
                first = execute(command_for(cli, workspace, args.model, args.effort, prompt),
                                workspace, env, evidence, 1, deadline)
                record["segments"].append(first)
                trace = trace_summary([evidence / first["stdout"]])
                if args.scenario == "adaptation":
                    observed = checkpoint(workspace, trace, first)
                    record["adaptation"]["checkpoint_graph"] = graph_records(workspace, evidence, "checkpoint")
                    checkpoint_checks = external_checks(workspace, evidence, args.scenario, None, deadline, revision=1) if observed else []
                    record["adaptation"]["checkpoint_checks"] = checkpoint_checks
                    required = {"R1-rounding-revision-1", "R2-conversion-negative"}
                    verified = {c["criterion"] for c in checkpoint_checks if c["status"] == "pass"} >= required
                    scope_ok = set(changed_paths(record["before_hashes"], hashes(workspace))) <= set(allowed)
                    if observed and verified and scope_ok and capabilities["resume_supported"] and time.monotonic() < deadline - 5:
                        update = (ORACLES / "adaptation-update.txt").read_text(encoding="utf-8")
                        record["adaptation"].update(status="incomplete", checkpoint=observed,
                                                    trigger_at=stamp(), scripted_user_update=update)
                        write_json(evidence / "external-update.json", record["adaptation"])
                        second = execute(command_for(cli, workspace, args.model, args.effort, update,
                                                     observed["session_id"]), workspace, env, evidence, 2, deadline)
                        record["segments"].append(second)
                        record["adaptation"]["status"] = "exercised; revision/handoff review unrun" if not second["timeout"] and second["exit_code"] == 0 else "incomplete"
                    else:
                        record["adaptation"].update(status="unsupported/incomplete", reason="Checkpoint acceptance/scope, session resume support or remaining budget missing")
                trace = trace_summary([evidence / s["stdout"] for s in record["segments"]])
                record["trace"] = trace
                record["checks"] = external_checks(workspace, evidence, args.scenario, args.probe, deadline)
                timed_out = any(s["timeout"] for s in record["segments"])
                failed = any(s["exit_code"] != 0 for s in record["segments"]) or bool(trace["runtime_failures"])
                oracle_failed = any(c["status"] == "fail" for c in record["checks"])
                record["status"] = "incomplete" if timed_out else "fail" if failed or oracle_failed else "review-required"
                if args.scenario == "adaptation" and not record["adaptation"]["status"].startswith("exercised") and record["status"] != "fail":
                    record["status"] = "incomplete"
                record["elapsed_seconds"] = round(time.monotonic() - started, 3)
            # Preserve trace text with only the private home location redacted.
            # Never read credentials, even to redact their contents.
            for path in evidence.iterdir():
                if path.is_file() and path.suffix in (".txt", ".jsonl", ".stderr", ".stdout"):
                    content = path.read_text(encoding="utf-8", errors="replace")
                    content = content.replace(str(home), "<private temporary home>")
                    content = content.replace(str(home).replace("\\", "/"), "<private temporary home>")
                    content = content.replace(str(home).replace("\\", "\\\\"), "<private temporary home>")
                    path.write_text(content, encoding="utf-8")
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        # Exceptions can carry paths to the private temporary home; keep a type
        # for OS/process failures, and only our authored messages for blockers.
        record["blockers"].append(str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__)
        record["status"] = "blocked"
    finally:
        record["user_config"] = {"before": user_before, "after": config_hash(user_home)}
        record["user_config"]["unchanged"] = record["user_config"]["before"] == record["user_config"]["after"]
        if workspace and "before_hashes" in record:
            record["after_hashes"] = hashes(workspace)
            record["changed_paths"] = changed_paths(record["before_hashes"], record["after_hashes"])
            record["scope_pass"] = set(record["changed_paths"]) <= set(record["allowed_paths"])
            record["graph_record"] = graph_records(workspace, evidence, "final")
            if any(s.get("validation") == "fail" for s in record["graph_record"]["snapshots"]):
                record["status"] = "fail"
            if not record["scope_pass"] or not record["user_config"]["unchanged"]:
                record["status"] = "fail"
        if record["blockers"] and not record["segments"] and record["status"] != "fail":
            record["status"] = "blocked"
        record["ended_at"] = stamp()
        write_json(evidence / "result.json", record)
        print("Evidence: " + str(evidence))
    return 2 if record["status"] in ("blocked", "fail", "incomplete") else 0


if __name__ == "__main__":
    raise SystemExit(main())
