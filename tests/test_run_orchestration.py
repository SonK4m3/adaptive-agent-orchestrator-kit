"""Offline harness tests. Every model execution is mocked; never dispatch Codex."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_orchestration as harness
import runtime_probe
import process_guard

spec = importlib.util.spec_from_file_location("graph_behavior_oracle", harness.ORACLES / "check.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.evidence = self.base / "evidence"
        self.evidence.mkdir()
        self.guard_patch = patch.object(process_guard, 'ProcessGuard', return_value=Mock())
        self.guard_patch.start()
        self.addCleanup(self.guard_patch.stop)

    def trace(self, events, name="trace.jsonl"):
        path = self.evidence / name
        path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
        return path

    def run_main(self, scenario="root-only", prepare=False, execute=None, checks=None):
        previous_outputs = set((self.base / "dist").glob("graph-*"))
        capabilities = {"blockers": [], "auth_env_capabilities": ["CODEX_API_KEY"], "resume_supported": True}
        args = ["--model", "gpt-6.1-sol", "--scenario", scenario]
        if prepare:
            args.append("--prepare-only")
        with patch.object(harness, "ROOT", self.base), \
                patch.object(harness, 'LIVE_TREE_SUPPORTED', True), \
                patch.object(harness, "install_home", return_value={"profile_data": {"agents": {"enabled": True}}}), \
                patch.object(harness, "inspect_runtime", return_value=capabilities), \
                patch.object(harness, "preflight", return_value={"status": "pass", "reason": "mocked sandbox"}), \
                patch.object(harness.shutil, "which", return_value="mock-codex"), \
                patch.object(harness, "execute", side_effect=execute) as dispatched, \
                patch.object(harness, "external_checks", side_effect=checks or (lambda *a, **k: [])), \
                patch.dict(os.environ, {"CODEX_API_KEY": "test-not-a-real-credential"}), \
                contextlib.redirect_stdout(io.StringIO()):
            code = harness.main(args)
        output = next(iter(set((self.base / "dist").glob("graph-*")) - previous_outputs))
        return code, json.loads((output / "result.json").read_text()), output, dispatched

    def fake_execute(self, bad_scope=False, timed_out=False, failed=False, adapt=False):
        def run(command, workspace, env, evidence, index, deadline):
            self.assertEqual(env["PYTHONDONTWRITEBYTECODE"], "1")
            self.assertEqual(command[command.index("-m") + 1], "gpt-6.1-sol")
            self.assertIn('model_reasoning_effort="medium"', command)
            if bad_scope:
                (workspace / "not-allowed.txt").write_text("violation")
            elif adapt:
                (workspace / "checkpoint.json").write_text(json.dumps({"revision": 1, "stage": "awaiting-user-acceptance"}))
            else:
                (workspace / "label.txt").write_bytes(b"Ready\n")
            events = [{"type": "thread.started", "thread_id": "same-session"}, {"type": "turn.completed", "usage": {"input_tokens": 9}}]
            path = evidence / f"segment-{index}.jsonl"
            path.write_text("\n".join(json.dumps(e) for e in events))
            (evidence / f"segment-{index}.stderr").write_text("")
            return {"stdout": path.name, "stderr": f"segment-{index}.stderr", "timeout": timed_out,
                    "exit_code": 1 if failed else 0, "started_at": harness.stamp(), "ended_at": harness.stamp()}
        return run

    def test_prepare_never_dispatches_and_unique_evidence(self):
        code, record, first, dispatched = self.run_main(prepare=True)
        self.assertEqual(code, 0)
        self.assertEqual(record["status"], "prepared")
        dispatched.assert_not_called()
        _, _, second, _ = self.run_main(prepare=True)
        self.assertNotEqual(first, second)
        self.assertTrue(record["user_config"]["unchanged"])
        self.assertEqual(record["graph_record"]["status"], "missing")
        self.assertNotIn("test-not-a-real-credential", json.dumps(record))

    def test_exit_zero_is_not_rubric_pass(self):
        code, record, _, dispatched = self.run_main(execute=self.fake_execute())
        self.assertEqual(code, 0)
        self.assertEqual(record["status"], "review-required")
        self.assertIn("unrun", record["rubric"])
        self.assertEqual(dispatched.call_count, 1)

    def test_scope_failure_overrides_success(self):
        code, record, _, _ = self.run_main(execute=self.fake_execute(bad_scope=True))
        self.assertEqual(code, 2)
        self.assertFalse(record["scope_pass"])
        self.assertEqual(record["status"], "fail")

    def test_timeout_no_retry(self):
        code, record, _, dispatched = self.run_main(execute=self.fake_execute(timed_out=True))
        self.assertEqual(code, 2)
        self.assertEqual(record["status"], "incomplete")
        self.assertEqual(dispatched.call_count, 1)

    def test_dispatch_failure_not_pass(self):
        _, record, _, dispatched = self.run_main(execute=self.fake_execute(failed=True))
        self.assertEqual(record["status"], "fail")
        self.assertEqual(dispatched.call_count, 1)

    def test_external_failure_not_pass(self):
        _, record, _, _ = self.run_main(execute=self.fake_execute(), checks=lambda *a, **k: [{"criterion": "R1", "status": "fail"}])
        self.assertEqual(record["status"], "fail")

    def test_adaptation_requires_revision_one_oracle(self):
        checks = lambda *a, **k: [{"criterion": "R1-rounding-revision-1", "status": "fail"}, {"criterion": "R2-conversion-negative", "status": "pass"}]
        _, record, _, dispatched = self.run_main("adaptation", execute=self.fake_execute(adapt=True), checks=checks)
        self.assertEqual(dispatched.call_count, 1)
        self.assertEqual(record["adaptation"]["status"], "unsupported/incomplete")
        self.assertNotIn("trigger_at", record["adaptation"])

    def test_adaptation_oracle_unrun_cannot_inject(self):
        _, record, _, dispatched = self.run_main("adaptation", execute=self.fake_execute(adapt=True),
            checks=lambda *a, **k: [{"criterion": "external-oracle", "status": "unrun"}])
        self.assertEqual(dispatched.call_count, 1)
        self.assertNotIn("trigger_at", record["adaptation"])

    def test_adaptation_resume_same_deadline_session_after_observed_checkpoint(self):
        def checks(*args, **kwargs):
            return [{"criterion": "R1-rounding-revision-1", "status": "pass"},
                    {"criterion": "R2-conversion-negative", "status": "pass"}]
        _, record, output, dispatched = self.run_main("adaptation", execute=self.fake_execute(adapt=True), checks=checks)
        self.assertEqual(dispatched.call_count, 2)
        first, second = dispatched.call_args_list
        self.assertEqual(first.args[-1], second.args[-1])
        self.assertIn("resume", second.args[0])
        self.assertIn("same-session", second.args[0])
        adaptation = record["adaptation"]
        self.assertLessEqual(adaptation["checkpoint"]["observed_at"], adaptation["trigger_at"])
        self.assertTrue(adaptation["checkpoint"]["scope_hashes"])
        self.assertTrue((output / "external-update.json").exists())

    def test_cli_pin_budget_and_probe_combinations(self):
        for arguments in (["--model", "other"], ["--model", "gpt-6.1-sol", "--effort", "low"],
                          ["--model", "gpt-6.1-sol", "--timeout", "601"],
                          ["--model", "gpt-6.1-sol", "--probe", "reviewer"]):
            with self.subTest(arguments=arguments), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                harness.main(arguments)

    def test_scenario_repos_are_independent_and_oracles_outside(self):
        first = self.evidence / "first"
        second = self.evidence / "second"
        first.mkdir()
        second.mkdir()
        w1, _ = harness.prepare(first, "root-only", None)
        w2, _ = harness.prepare(second, "independent", None)
        self.assertTrue((w1 / ".git").is_dir())
        self.assertTrue((w2 / ".git").is_dir())
        self.assertFalse(harness.ORACLES.is_relative_to(w1))
        self.assertFalse((w1 / "check.py").exists())

    def test_windows_tree_cleanup_wait_bounded(self):
        proc = Mock(pid=101)
        with patch.object(harness.subprocess, "run", return_value=Mock(returncode=0)) as kill:
            result = harness.cleanup(proc, time.monotonic() + 3, "nt")
        self.assertEqual(kill.call_args.args[0], ["taskkill", "/PID", "101", "/T", "/F"])
        self.assertLessEqual(kill.call_args.kwargs["timeout"], 3)
        self.assertLessEqual(proc.wait.call_args.kwargs["timeout"], 3)
        self.assertNotEqual(result["status"], "pass")

    def test_posix_group_cleanup(self):
        proc = Mock(pid=102)
        with patch.object(harness.os, "killpg", create=True) as kill, \
                patch.object(harness.signal, "SIGKILL", 9, create=True):
            harness.cleanup(proc, time.monotonic() + 3, "posix")
        kill.assert_called_once_with(102, 9)
        self.assertLessEqual(proc.wait.call_args.kwargs["timeout"], 3)

    def test_cleanup_exception_still_kills_and_reaps_parent(self):
        proc = Mock(pid=102)
        with patch.object(harness.subprocess, 'run', side_effect=subprocess.TimeoutExpired('taskkill', 1)):
            result = harness.cleanup(proc, time.monotonic() + 3, 'nt')
        proc.kill.assert_called_once()
        proc.wait.assert_called_once()
        self.assertTrue(result['parent_reaped'])

    def test_normal_exit_closes_owned_tree(self):
        proc, guard = Mock(pid=103, returncode=0), Mock()
        with patch.object(harness, 'spawn_process', return_value=(proc, guard)):
            record = harness.execute(['mock'], self.base, {}, self.evidence, 1, time.monotonic() + 7)
        guard.close.assert_called_once()
        self.assertFalse(record['timeout'])

    def test_oracle_environment_is_credential_free_and_output_discarded(self):
        proc, guard = Mock(returncode=1), Mock()
        with patch.dict(os.environ, {'CODEX_API_KEY': 'fake-never-log', 'OPENAI_API_KEY': 'fake-other'}), \
                patch.object(harness, 'LIVE_TREE_SUPPORTED', True), \
                patch.object(harness.shutil, 'which', return_value='mock-codex'), \
                patch.object(harness, 'spawn_process', return_value=(proc, guard)) as spawn:
            results = harness.external_checks(self.base, self.evidence, 'root-only', None, time.monotonic() + 7)
        kwargs = spawn.call_args.kwargs
        self.assertNotIn('CODEX_API_KEY', kwargs['env'])
        self.assertNotIn('OPENAI_API_KEY', kwargs['env'])
        self.assertEqual(kwargs['stdout'], subprocess.DEVNULL)
        self.assertEqual(kwargs['stderr'], subprocess.DEVNULL)
        self.assertIn('permissions.oracle.network.enabled=false', spawn.call_args.args[0])
        self.assertEqual(results[0]['status'], 'unrun')
        guard.close.assert_called_once()

    def test_oracle_guard_rejects_result_forgery_io_and_introspection(self):
        for source in ('import sys; sys.exit(0)', 'open("results.json", "w")',
                       'import re; re.sys.argv', 'x = globals()', 'x = ().__class__',
                       'from decimal import *', 'from duration import __builtins__ as b',
                       'from re import sys as s', 'import re as __builtins__'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                oracle.guard_source(source)
        oracle.guard_source('from decimal import Decimal\ndef convert(value):\n    return int(Decimal(str(value))*100)\n')

    def test_graph_duplicate_revision_identical_or_conflicting(self):
        original = json.loads((ROOT / 'eval/fixtures/graph-record/l0.json').read_text())
        workspace = self.base / 'graph-workspace'
        workspace.mkdir()
        for name in ('graph-1.json', 'graph-record.json'):
            (workspace / name).write_text(json.dumps(original))
        result = harness.graph_records(workspace, self.evidence, 'same')
        self.assertFalse(any(s.get('validation') == 'fail' for s in result['snapshots']))
        original['nodes'][0]['output'] = 'different'
        (workspace / 'graph-record.json').write_text(json.dumps(original))
        result = harness.graph_records(workspace, self.evidence, 'different')
        self.assertTrue(any(s.get('validation') == 'fail' for s in result['snapshots']))

    def test_execute_timeout_separate_logs_and_new_group(self):
        proc = Mock(pid=103, returncode=-9)
        proc.wait.side_effect = subprocess.TimeoutExpired("mock", 1)
        with patch.object(harness.subprocess, "Popen", return_value=proc) as popen, \
                patch.object(harness, "cleanup", return_value={"status": "requested"}) as cleanup:
            result = harness.execute(["mock"], self.base, {}, self.evidence, 1, time.monotonic() + 7)
        self.assertTrue(result["timeout"])
        cleanup.assert_called_once()
        self.assertNotEqual(popen.call_args.kwargs["stdout"].name, popen.call_args.kwargs["stderr"].name)
        self.assertTrue(popen.call_args.kwargs["start_new_session"] or popen.call_args.kwargs["creationflags"])

    def test_unknown_trace_no_inferred_zero_totals_or_usage_sum(self):
        path = self.trace([{"type": "new.dialect"}, {"type": "turn.completed", "usage": {"total_tokens": 11}}])
        data = harness.trace_summary([path])
        self.assertIn("unknown", data["actual_total_counts"])
        self.assertIsNone(data["usage_total"])
        self.assertEqual(len(data["usage_output"]), 1)
        self.assertTrue(data["unrecognized"])

    def test_trace_camel_snake_dedup_and_requests_not_confirmed(self):
        spawn = {"id": "1", "type": "collabAgentToolCall", "tool": "spawnAgent", "status": "inProgress",
                 "senderThreadId": "root", "receiverThreadIds": ["child"], "model": "configured-child"}
        done = dict(spawn, status="completed", agentsStates={"child": {"status": "running"}})
        close = {"id": "2", "type": "collab_tool_call", "tool": "close_agent", "status": "completed",
                 "sender_thread_id": "root", "receiver_thread_ids": ["child"]}
        path = self.trace([{"type": "item.started", "item": spawn}, {"method": "item/completed", "params": {"item": done}},
                           {"type": "item.completed", "item": close}])
        data = harness.trace_summary([path, path])
        self.assertEqual(data["observed_call_counts"]["spawn"], 1)
        self.assertEqual(data["observed_completed_call_counts"]["close"], 1)
        self.assertIn("unknown", data["confirmed_resources"])
        self.assertEqual(data["calls"][0]["model_requested"], "configured-child")

    def test_malformed_trace_is_unknown(self):
        path = self.trace([None, [], {"item": {"type": "collab_tool_call", "id": "x", "tool": "new-tool"}}])
        self.assertEqual(len(harness.trace_summary([path])["unrecognized"]), 3)

    def test_auth_missing_stops_without_read_or_model(self):
        with self.assertRaisesRegex(RuntimeError, "No supported auth"):
            harness.prepare_auth(self.base, {}, {"auth_env_capabilities": []})

    def test_auth_environment_capability_reuses_without_copy(self):
        with patch.object(harness.shutil, "copy2") as copy:
            result = harness.prepare_auth(self.base, {"CODEX_API_KEY": "never-output"}, {"auth_env_capabilities": ["CODEX_API_KEY"]})
        copy.assert_not_called()
        self.assertNotIn("never-output", json.dumps(result))

    def test_opt_in_auth_private_cleanup_and_no_value_read(self):
        source_home = self.base / "auth-source"
        source_home.mkdir()
        (source_home / "auth.json").write_text("test-private-placeholder")
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            with patch.object(Path, "read_text", side_effect=AssertionError("must not inspect auth")), \
                    patch.object(Path, "read_bytes", side_effect=AssertionError("must not inspect auth")):
                report = harness.prepare_auth(target, {}, {"auth_env_capabilities": []}, source_home)
            self.assertTrue((target / "auth.json").exists())
            self.assertNotIn(str(target), json.dumps(report))
        self.assertFalse(target.exists())
        self.assertTrue((source_home / "auth.json").exists())

    def test_optional_graph_validator_and_missing_coverage(self):
        self.assertEqual(harness.graph_records(self.base, self.evidence, "empty")["status"], "missing")
        (self.base / "graph.json").write_text("{}")
        report = harness.graph_records(self.base, self.evidence, "final")
        self.assertEqual(report["snapshots"][0]["validation"], "fail")
        self.assertTrue(report["snapshots"][0]["errors"])

    def test_oracle_negative_fixtures_fail_without_models(self):
        for scenario in harness.SCENARIOS:
            with self.subTest(scenario=scenario):
                target = self.base / scenario
                harness.shutil.copytree(harness.FIXTURES / scenario, target)
                results = oracle.evaluate(target, scenario)
                self.assertTrue(any(c["status"] == "fail" for c in results))

    def test_oracle_auth_matrix_and_malicious_comparison(self):
        (self.base / "auth.py").write_text(
            "def authorize(role, action):\n    return type(role) is str and type(action) is str and ((role == 'admin' and action in ('read', 'write')) or (role == 'viewer' and action == 'read'))\n")
        results = oracle.evaluate(self.base, "verification")
        self.assertFalse(any(c["status"] == "fail" for c in results))
        self.assertTrue(any(c["status"] == "unrun" for c in results))

    def test_oracle_adaptation_distinguishes_rounding_revisions(self):
        (self.base / "convert.py").write_text(
            "from decimal import Decimal, ROUND_HALF_UP\nimport math\ndef convert(value):\n"
            "    if type(value) not in (int, float) or value < 0 or not math.isfinite(value):\n        raise TypeError\n"
            "    return int((Decimal(str(value)) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))\n")
        first = oracle.evaluate(self.base, "adaptation", revision=1)
        second = oracle.evaluate(self.base, "adaptation", revision=2)
        self.assertFalse(any(c["status"] == "fail" for c in first))
        self.assertTrue(any(c["status"] == "fail" for c in second))

    def test_runtime_inspection_calls_help_schema_only(self):
        cli = self.base / "codex.exe"
        cli.write_bytes(b"CODEX_API_KEY")
        help_text = "--profile --strict-config --json --model --sandbox SESSION_ID"
        def respond(command, **kwargs):
            self.assertNotIn("test-private-placeholder", str(command))
            self.assertTrue(command[1:] == ["--version"] or command[-1] == "--help" or "generate-json-schema" in command)
            return Mock(returncode=0, stdout=help_text, stderr="")
        with patch.object(runtime_probe.subprocess, "run", side_effect=respond) as run:
            result = runtime_probe.inspect_runtime(str(cli), self.base, self.evidence, {}, {"agents": {"enabled": True}})
        self.assertEqual(run.call_count, 5)
        self.assertIn("incomplete", result["profile_validation"])
        self.assertEqual(result["auth_env_capabilities"], ["CODEX_API_KEY"])


if __name__ == "__main__":
    unittest.main()
