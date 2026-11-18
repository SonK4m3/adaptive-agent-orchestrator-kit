"""Offline MCP lifecycle tests with a synthetic worker; no model usage."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from deepseek_jobs import JobStore
from deepseek_mcp import BridgeError, JobManager, handle_rpc


FAKE_WORKER = r'''import json, pathlib, sys, time
from pathlib import Path
args = sys.argv
progress = Path(args[args.index("--progress-file") + 1])
sid = "session-fake"
if "--session-id" in args:
    sid = args[args.index("--session-id") + 1]
task = sys.stdin.read()
progress.write_text(json.dumps({"event_type":"session","session_id":sid,"observed_at":"now"})+"\n", encoding="utf-8")
if task == "sleep":
    time.sleep(20)
root = Path.cwd()
target = root / "src" / "module.py"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(target.read_text(encoding="utf-8") + "# " + task + "\n", encoding="utf-8")
(root / "new.txt").write_text("created", encoding="utf-8")
print(json.dumps({"status":"timeout" if task == "timeout" else "completed","session_id":sid,"final_reason":"completed","answer":"done: "+task,"exit_code":124 if task == "timeout" else 0,"failure_layer":"wrapper" if task == "timeout" else None,"cleanup_errors":[]}))
'''


class DeepSeekMcpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.source = root / "source"
        self.source.mkdir()
        (self.source / "src").mkdir()
        (self.source / "src/module.py").write_text("original\n", encoding="utf-8")
        (self.source / ".env").write_text("SECRET_SENTINEL\n", encoding="utf-8")
        (self.source / ".git").mkdir()
        (self.source / ".git/config").write_text("git-private", encoding="utf-8")
        (self.source / ".codex").mkdir()
        (self.source / ".codex/config.toml").write_text("private config", encoding="utf-8")
        (self.source / ".ssh").mkdir()
        (self.source / ".ssh/id_ed25519").write_text("private key sentinel", encoding="utf-8")
        self.root = root / "jobs"
        self.worker = root / "fake_worker.py"
        self.worker.write_text(FAKE_WORKER, encoding="utf-8")
        self.manager = JobManager(JobStore(self.root), self.worker)
        self.addCleanup(self.manager.close)

    def wait_terminal(self, task_id):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            state = self.manager.status(task_id)
            if state["status"] != "running":
                return state
            time.sleep(0.02)
        self.fail("worker did not reach a terminal status")

    def test_async_start_isolated_workspace_patch_and_followup(self):
        state = self.manager.start(task="first", input_paths=["src"], workspace=str(self.source),
                                   permission_mode="workspace-write", timeout_seconds=30)
        self.assertEqual(state["status"], "running")
        task_id = state["task_id"]
        self.wait_terminal(task_id)
        result = self.manager.result(task_id)
        self.assertEqual(result["answer"], "done: first")
        self.assertEqual(result["session_id"], "session-fake")
        self.assertIn("src/module.py", result["changed_paths"])
        self.assertIn("new.txt", result["changed_paths"])
        self.assertEqual((self.source / "src/module.py").read_text(encoding="utf-8"), "original\n")
        record = self.manager.store.get(task_id)
        self.assertEqual(record["last_progress"], "session")
        copied = self.root / task_id / "workspace"
        self.assertFalse((copied / ".env").exists())
        self.assertFalse((copied / ".git").exists())
        self.assertFalse((copied / ".codex").exists())
        self.assertEqual(record["requested_permission_mode"], "workspace-write")

        with self.assertRaisesRegex(BridgeError, "must match the original request"):
            self.manager.start(task_id=task_id, task="followup", input_paths=["src"],
                               workspace=str(self.source), permission_mode="read-only",
                               timeout_seconds=30, session_id="session-fake")
        next_state = self.manager.start(task_id=task_id, task="followup", input_paths=["src"],
                                        workspace=str(self.source), permission_mode="workspace-write",
                                        timeout_seconds=30, session_id="session-fake")
        self.assertEqual(next_state["attempt"], 2)
        self.wait_terminal(task_id)
        self.assertEqual(self.manager.result(task_id)["answer"], "done: followup")
        reloaded = JobManager(JobStore(self.root), self.worker)
        self.addCleanup(reloaded.close)
        self.assertEqual(reloaded.status(task_id)["status"], "completed")
        self.assertEqual(reloaded.result(task_id)["session_id"], "session-fake")

    def test_direct_excluded_paths_are_rejected(self):
        with self.assertRaisesRegex(BridgeError, "excluded or sensitive"):
            self.manager.start(task="inspect", input_paths=[".git/config"], workspace=str(self.source))
        with self.assertRaisesRegex(BridgeError, "excluded or sensitive"):
            self.manager.start(task="inspect", input_paths=[".codex/config.toml"], workspace=str(self.source))
        with self.assertRaisesRegex(BridgeError, "excluded or sensitive"):
            self.manager.start(task="inspect", input_paths=[".env"], workspace=str(self.source))
        with self.assertRaisesRegex(BridgeError, "excluded or sensitive"):
            self.manager.start(task="inspect", input_paths=[".ssh/id_ed25519"], workspace=str(self.source))

    def test_json_rpc_initialize_tools_and_errors(self):
        init = handle_rpc(self.manager, {"jsonrpc":"2.0","id":1,"method":"initialize",
                                        "params":{"protocolVersion":"2025-03-26"}})
        self.assertEqual(init["result"]["serverInfo"]["name"], "adaptive-agent-orchestrator-deepseek")
        listed = handle_rpc(self.manager, {"jsonrpc":"2.0","id":2,"method":"tools/list"})
        names = {tool["name"] for tool in listed["result"]["tools"]}
        self.assertEqual(len(names), 7)
        bad = handle_rpc(self.manager, {"jsonrpc":"2.0","id":3,"method":"tools/call",
                                        "params":{"name":"deepseek_task_status","arguments":{}}})
        self.assertTrue(bad["result"]["isError"])
        self.assertNotIn("Traceback", bad["result"]["content"][0]["text"])
        malformed = handle_rpc(self.manager, {"jsonrpc":"2.0","id":4,"method":"tools/list","params":[]})
        self.assertEqual(malformed["error"]["code"], -32602)

    def test_stdio_mcp_full_start_wait_result_round_trip(self):
        requests = [
            {"jsonrpc":"2.0","id":1,"method":"initialize",
             "params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1"}}},
            {"jsonrpc":"2.0","method":"notifications/initialized"},
            {"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"deepseek_task_start","arguments":{"task":"stdio","input_paths":["src"],"workspace":str(self.source)}}},
        ]
        # Resolve the returned task ID in a second process request. The JSON-RPC
        # server remains alive until stdin closes, so the short worker can settle.
        first = subprocess.Popen([sys.executable, str(SCRIPTS / "deepseek_mcp.py"),
                                  "--job-root", str(self.root), "--worker-script", str(self.worker)],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, encoding="utf-8")
        try:
            for request in requests:
                first.stdin.write(json.dumps(request) + "\n")
            first.stdin.flush()
            init_line = first.stdout.readline()
            start_line = first.stdout.readline()
            self.assertTrue(init_line and start_line)
            start = json.loads(start_line)["result"]["content"][0]["text"]
            task_id = json.loads(start)["task_id"]
            first.stdin.write(json.dumps({"jsonrpc":"2.0","id":3,"method":"tools/call",
                                          "params":{"name":"deepseek_task_wait","arguments":{"task_id":task_id,"wait_seconds":5}}}) + "\n")
            first.stdin.write(json.dumps({"jsonrpc":"2.0","id":4,"method":"tools/call",
                                          "params":{"name":"deepseek_task_result","arguments":{"task_id":task_id}}}) + "\n")
            first.stdin.flush()
            wait_result = json.loads(first.stdout.readline())["result"]["content"][0]["text"]
            result = json.loads(first.stdout.readline())["result"]["content"][0]["text"]
            self.assertEqual(json.loads(wait_result)["status"], "completed")
            self.assertEqual(json.loads(result)["answer"], "done: stdio")
        finally:
            first.stdin.close()
            first.wait(timeout=8)
            first.stdout.close()
            first.stderr.close()

    def test_progress_and_result_do_not_include_raw_prompt_in_job_ledger(self):
        secret_prompt = "PRIVATE_TASK_TEXT_DO_NOT_PERSIST"
        state = self.manager.start(task=secret_prompt, input_paths=["src"], workspace=str(self.source))
        self.wait_terminal(state["task_id"])
        raw_record = (self.root / f"{state['task_id']}.json").read_text(encoding="utf-8")
        self.assertNotIn(secret_prompt, raw_record)
        self.assertIn("session-fake", raw_record)

    def test_cancel_stops_owned_worker(self):
        state = self.manager.start(task="sleep", input_paths=["src"], workspace=str(self.source), timeout_seconds=30)
        cancelled = self.manager.cancel(state["task_id"])
        self.assertNotEqual(cancelled["status"], "running")
        self.assertFalse(self.manager.active)

    def test_worker_timeout_maps_to_durable_timed_out_state(self):
        state = self.manager.start(task="timeout", input_paths=["src"], workspace=str(self.source))
        terminal = self.wait_terminal(state["task_id"])
        self.assertEqual(terminal["status"], "timed_out")
        self.assertEqual(self.manager.result(state["task_id"])["status"], "timed_out")


if __name__ == "__main__":
    unittest.main()
