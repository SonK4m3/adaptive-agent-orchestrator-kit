"""Offline preflight regressions: sandbox process mocked, no inference/auth."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import runtime_preflight as probe
import run_orchestration as harness


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / "private"
        self.workspace = self.base / "workspace"
        self.evidence = self.base / "evidence"
        for p in (self.home / "skills/adaptive-agent-orchestrator", self.workspace, self.evidence):
            p.mkdir(parents=True)
        (self.workspace / "TASK.md").write_text("fixture")
        (self.workspace / "label.txt").write_text("Draft")
        (self.home / "skills/adaptive-agent-orchestrator/SKILL.md").write_text("skill")

    def test_missing_mode_blocks_without_process(self):
        with patch.object(probe.os, "name", "nt"), patch.object(probe, "spawn_process") as spawn:
            result = probe.preflight("codex", self.home, self.workspace, self.evidence)
        self.assertEqual(result["status"], "blocked")
        spawn.assert_not_called()

    def test_exact_marker_pass_and_credential_free_environment(self):
        proc, guard = Mock(), Mock()
        proc.communicate.return_value = (b"AO_PREFLIGHT_OK\n", b"")
        proc.returncode = 0
        with patch.object(probe.os, "name", "nt"), \
                patch.object(probe, "spawn_process", return_value=(proc, guard)) as spawn, \
                patch.dict(os.environ, {"CODEX_API_KEY": "SECRET", "CODEX_PERMISSION_PROFILE": ":danger-full-access"}):
            result = probe.preflight("codex", self.home, self.workspace, self.evidence, "elevated")
        self.assertEqual(result["status"], "pass")
        command = spawn.call_args.args[0]
        self.assertEqual(command[1], "sandbox")
        self.assertIn("--include-managed-config", command)
        self.assertNotIn("exec", command)
        env = spawn.call_args.kwargs["env"]
        self.assertNotIn("CODEX_API_KEY", env)
        self.assertNotIn("CODEX_PERMISSION_PROFILE", env)
        self.assertNotIn("SECRET", (self.evidence / "preflight.json").read_text())
        self.assertNotIn(str(self.home), (self.evidence / "preflight.json").read_text())
        guard.close.assert_called_once()

    def test_error_output_is_classified_not_persisted(self):
        proc, guard = Mock(), Mock()
        proc.communicate.return_value = (b"SECRET", b"SECRET blocked by policy")
        proc.returncode = 1
        with patch.object(probe.os, "name", "nt"), patch.object(probe, "spawn_process", return_value=(proc, guard)):
            result = probe.preflight("codex", self.home, self.workspace, self.evidence, "elevated")
        self.assertEqual(result["status"], "blocked")
        self.assertIn("blocked by policy", result["error_signals"])
        self.assertNotIn("SECRET", json.dumps(result))

    def test_timeout_blocks_and_closes_owned_job(self):
        proc, guard = Mock(), Mock()
        proc.communicate.side_effect = subprocess.TimeoutExpired("sandbox", 20)
        proc.poll.return_value = None
        with patch.object(probe.os, "name", "nt"), patch.object(probe, "spawn_process", return_value=(proc, guard)):
            result = probe.preflight("codex", self.home, self.workspace, self.evidence, "elevated")
        self.assertEqual(result["error_type"], "TimeoutExpired")
        guard.close.assert_called_once()
        proc.kill.assert_called_once()

    def test_main_gate_blocks_before_auth_or_model(self):
        with patch.object(harness, "ROOT", self.base), \
                patch.object(harness, "install_home", return_value={"profile_data": {}}), \
                patch.object(harness, "inspect_runtime", return_value={"blockers": []}), \
                patch.object(harness, "preflight", return_value={"status": "blocked", "reason": "fixture"}), \
                patch.object(harness, "prepare_auth") as auth, patch.object(harness, "execute") as model, \
                contextlib.redirect_stdout(io.StringIO()):
            code = harness.main(["--model", "gpt-6.1-sol"])
        self.assertEqual(code, 2)
        auth.assert_not_called()
        model.assert_not_called()

    def test_preflight_only_pass_never_dispatches(self):
        with patch.object(harness, "ROOT", self.base), \
                patch.object(harness, "install_home", return_value={"profile_data": {}}), \
                patch.object(harness, "inspect_runtime", return_value={"blockers": []}), \
                patch.object(harness, "preflight", return_value={"status": "pass"}), \
                patch.object(harness, "prepare_auth") as auth, patch.object(harness, "execute") as model, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(harness.main(["--model", "gpt-6.1-sol", "--preflight-only"]), 0)
        auth.assert_not_called()
        model.assert_not_called()


if __name__ == "__main__":
    unittest.main()
