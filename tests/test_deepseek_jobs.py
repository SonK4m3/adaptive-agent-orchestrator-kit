"""Offline persistence tests for prompt-free DeepSeek job metadata."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from deepseek_jobs import JobStore, JobStoreError, default_job_root, read_progress_file


class JobStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = JobStore(self.root / "jobs")
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        (self.workspace / "src").mkdir()
        (self.workspace / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")

    def test_create_returns_unique_persistent_task_ids_without_prompt(self):
        first = self.store.create(self.workspace, ["src/app.py"])
        second = self.store.create(self.workspace, ["src/app.py"])
        self.assertNotEqual(first["task_id"], second["task_id"])
        loaded = JobStore(self.root / "jobs").get(first["task_id"])
        self.assertEqual(loaded["status"], "queued")
        self.assertNotIn("prompt", loaded)
        self.assertNotIn("task", loaded)
        self.assertTrue((self.root / "jobs" / f"{first['task_id']}.json").is_file())

    def test_resume_adds_history_and_requires_stopped_terminal_state(self):
        record = self.store.create(self.workspace, ["src/app.py"])
        running = self.store.begin_attempt(record["task_id"], process_id=1234, checkpoint_id="tests")
        self.assertEqual(running["attempt"], 1)
        self.assertEqual(running["status"], "running")
        with self.assertRaisesRegex(JobStoreError, "active attempt"):
            self.store.begin_attempt(record["task_id"], session_id="dsh-session-1")
        timed_out = self.store.update(record["task_id"], status="timed_out", session_id="dsh-session-1",
                                      failure_layer="wrapper", final_reason="timeout", exit_code=124)
        resumed = self.store.begin_attempt(record["task_id"], session_id="dsh-session-1",
                                           checkpoint_id="finish-tests")
        self.assertEqual(resumed["attempt"], 2)
        self.assertEqual(resumed["history"][0]["status"], "timed_out")
        self.assertEqual(resumed["session_id"], "dsh-session-1")
        self.assertEqual(resumed["checkpoint_id"], "finish-tests")
        self.assertEqual(resumed["status"], "running")
        self.assertEqual(timed_out["failure_layer"], "wrapper")

    def test_updates_are_bounded_and_reject_secret_fields(self):
        record = self.store.create(self.workspace, ["src/app.py"])
        progress = self.store.update(record["task_id"], last_progress="step_end", session_id="dsh-abc")
        self.assertEqual(progress["last_progress"], "step_end")
        with self.assertRaisesRegex(JobStoreError, "unsupported or empty"):
            self.store.update(record["task_id"], api_key="secret")
        with self.assertRaisesRegex(JobStoreError, "bounded label"):
            self.store.update(record["task_id"], last_progress="provider secret text")
        with self.assertRaisesRegex(JobStoreError, "invalid job transition"):
            self.store.update(record["task_id"], status="completed")

    def test_result_and_patch_paths_must_stay_inside_job_store(self):
        record = self.store.create(self.workspace, [])
        result_path = self.root / "jobs" / record["task_id"] / "report.json"
        result_path.parent.mkdir()
        updated = self.store.update(record["task_id"], result_path=str(result_path))
        self.assertEqual(updated["result_path"], str(result_path.resolve()))
        with self.assertRaisesRegex(JobStoreError, "inside the job store"):
            self.store.update(record["task_id"], patch_path=str(self.root / "outside.patch"))

    def test_input_paths_reject_traversal_absolute_paths_and_duplicates(self):
        for path in ("../secret", "src/../../secret", "C:/Users/private", "/etc/passwd", "src\\app.py"):
            with self.subTest(path=path), self.assertRaises(JobStoreError):
                self.store.create(self.workspace, [path])
        with self.assertRaisesRegex(JobStoreError, "duplicate"):
            self.store.create(self.workspace, ["src/app.py", "src/app.py"])

    def test_corrupt_record_is_quarantined_and_never_reported_as_success(self):
        record = self.store.create(self.workspace, [])
        path = self.root / "jobs" / f"{record['task_id']}.json"
        path.write_text('{broken', encoding="utf-8")
        with self.assertRaisesRegex(JobStoreError, "corrupt"):
            self.store.get(record["task_id"])
        self.assertFalse(path.exists())
        quarantined = list((self.root / "jobs").glob("*.corrupt-*.json"))
        self.assertEqual(len(quarantined), 1)

    def test_list_is_bounded_and_reports_only_structured_records(self):
        for _ in range(3):
            self.store.create(self.workspace, [])
        records = self.store.list(limit=2)
        self.assertEqual(len(records), 2)
        self.assertTrue(all("session_id" in item and "last_progress" in item for item in records))
        with self.assertRaisesRegex(JobStoreError, "between 1 and 1000"):
            self.store.list(limit=0)

    def test_default_store_follows_codex_home_without_reading_other_environment(self):
        path = default_job_root({"CODEX_HOME": str(self.root / "codex-home"), "OPENAI_API_KEY": "secret"})
        self.assertEqual(path, self.root / "codex-home" / "deepseek-worker" / "jobs")
        self.assertNotIn("secret", str(path))

    def test_progress_reader_discards_payload_and_incomplete_tail(self):
        path = self.root / "events.jsonl"
        path.write_text(
            json.dumps({"event_type": "session", "session_id": "dsh-session", "cwd": "secret/path"})
            + "\n" + json.dumps({"event_type": "status", "phase": "step_end", "prompt": "secret"})
            + "\n" + '{"event_type":"final","session_id":"partial',
            encoding="utf-8")
        events = read_progress_file(path)
        self.assertEqual(events, [
            {"event_type": "session", "session_id": "dsh-session"},
            {"event_type": "status", "phase": "step_end"},
        ])
        record = self.store.create(self.workspace, [])
        ingested = self.store.ingest_progress(record["task_id"], events)
        self.assertEqual(ingested["session_id"], "dsh-session")
        self.assertEqual(ingested["last_progress"], "step_end")


if __name__ == "__main__":
    unittest.main()
