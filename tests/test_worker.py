import fcntl
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import textwrap
import unittest
from unittest.mock import patch

from radar_quantum_bench import experiment
from radar_quantum_bench.store import Store
from radar_quantum_bench.worker import run_worker


class WorkerTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.store = Store(Path(folder.name))

    def assert_result(self, job):
        self.assertEqual(self.store.get(job["id"])["status"], "completed")
        document = experiment.load_result(self.store.result_path(job["id"]))
        self.assertEqual(document["config"]["circuit"], job["circuit"])
        self.assertEqual(document["config"]["base_seed"], job["base_seed"])
        self.assertTrue(document["summary"]["complete"])
        self.assertEqual(document["summary"]["total_shots"], 20_480)
        trials = [(row["repetition"], row["condition"]) for row in document["attempts"]
                  if row["status"] == "ok" and not row["warmup"]]
        self.assertEqual(len(trials), 20)
        self.assertEqual(len(set(trials)), 20)
        return document

    def test_once_handles_empty_queue_and_at_most_one_job(self):
        self.assertEqual(run_worker(self.store, once=True), 0)
        first = self.store.submit("first", "bell", 950)
        second = self.store.submit("second", "bv", 951)
        self.assertEqual(run_worker(self.store, once=True), 0)
        document = self.assert_result(first)
        ideal = document["summary"]["conditions"]["ideal"]["counts"]
        self.assertEqual(ideal["01"] + ideal["10"], 0)
        self.assertEqual(self.store.get(second["id"])["status"], "queued")
        self.assertFalse(self.store.result_path(second["id"]).exists())

    def test_hard_stop_after_result_preserves_science_and_completes_claim(self):
        job = self.store.submit("interrupted", "bell", 2231)
        # The final JSON has reached disk, but the SQLite claim is still running.
        script = textwrap.dedent("""
            import os, sys
            from pathlib import Path
            from unittest.mock import patch
            from radar_quantum_bench.store import Store
            from radar_quantum_bench.worker import run_worker

            store = Store(Path(sys.argv[1]))
            def stop_before_commit(jobid, attempt_id, success, error_code, **kwargs):
                os._exit(79 if success and error_code is None else 80)

            with patch.object(store, "finish", side_effect=stop_before_commit):
                run_worker(store, once=True)
        """)
        stopped = subprocess.run(
            [sys.executable, "-B", "-c", script, str(self.store.root)],
            cwd=Path(__file__).resolve().parents[1], timeout=60, capture_output=True, text=True,
        )
        self.assertEqual(stopped.returncode, 79, stopped.stderr)
        claimed = self.store.get(job["id"])
        self.assertEqual(claimed["status"], "running")
        self.assertEqual([a["status"] for a in claimed["attempts"]], ["running"])
        path = self.store.result_path(job["id"])
        original_bytes = path.read_bytes()
        original = experiment.load_result(path)
        self.assertTrue(original["summary"]["complete"])
        self.assertEqual(original["summary"]["total_shots"], 20_480)

        with patch("radar_quantum_bench.aer.build_runner") as compilation:
            self.assertEqual(run_worker(self.store, once=True), 0)
            compilation.assert_not_called()
        finished = self.assert_result(job)
        self.assertEqual(path.read_bytes(), original_bytes)
        self.assertEqual(finished["run_id"], original["run_id"])
        self.assertEqual(finished["attempts"], original["attempts"])
        recovered = self.store.get(job["id"])
        self.assertEqual(recovered["id"], claimed["id"])
        history = recovered["attempts"]
        self.assertEqual(history[0]["id"], claimed["attempts"][0]["id"])
        self.assertNotEqual(history[0]["id"], history[1]["id"])
        self.assertEqual([(a["status"], a["error_code"]) for a in history],
                         [("failed", "Interrupted"), ("completed", None)])

    def test_second_worker_cannot_recover_an_active_job(self):
        job = self.store.submit("active", "bell", 15)
        with (self.store.root / "worker.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.store.claim()
            with self.assertRaisesRegex(RuntimeError, "executando"):
                run_worker(self.store, once=True)
            self.assertEqual(self.store.get(job["id"])["status"], "running")
        self.assertEqual(run_worker(self.store, once=True), 0)
        self.assert_result(job)

    def test_job_failure_reports_only_type_and_daemon_continues(self):
        first = self.store.submit("failure", "ghz", 450)
        with patch.object(experiment, "run", side_effect=RuntimeError("private diagnostic")):
            self.assertEqual(run_worker(self.store, once=True), 1)
        attempt = self.store.get(first["id"])["attempts"][0]
        self.assertEqual((attempt["status"], attempt["error_code"]), ("failed", "RuntimeError"))

        self.store.retry(first["id"], "retry")
        second = self.store.submit("following", "bv", 451)
        collect = experiment.run
        def fail_first(path, **kwargs):
            if kwargs["circuit"] == "ghz":
                raise OSError("private location")
            return collect(path, **kwargs)

        with patch.object(experiment, "run", side_effect=fail_first), \
             patch("radar_quantum_bench.worker.sleep", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                run_worker(self.store)
        self.assertEqual(self.store.get(first["id"])["attempts"][-1]["error_code"], "OSError")
        self.assert_result(second)
