import select
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from radar_quantum_bench.experiment import load_result
from radar_quantum_bench.store import Store


ROOT = Path(__file__).resolve().parents[1]
PAUSED_WORKER = """
import signal
import sys
from pathlib import Path
from unittest.mock import patch

from radar_quantum_bench import aer
from radar_quantum_bench.store import Store
from radar_quantum_bench.worker import run_worker

real_runner = aer.build_runner

def build_paused_runner(*args, **kwargs):
    environment, sample = real_runner(*args, **kwargs)
    samples_done = 0
    def sample_until_interrupted(*args):
        nonlocal samples_done
        if samples_done == 3:
            # The fourth attempt is durable before the adapter is called.
            print("checkpoint", flush=True)
            while True:
                signal.pause()
        counts = sample(*args)
        samples_done += 1
        return counts
    return environment, sample_until_interrupted

with patch.object(aer, "build_runner", build_paused_runner):
    sys.exit(run_worker(Store(Path(sys.argv[1])), once=True))
"""


class ProcessRecoveryTests(unittest.TestCase):
    def test_killed_worker_releases_lock_and_replays_only_missing_measurements(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = Store(root)
            job = store.submit("resume-after-kill", "bell", 42)
            job_id = job["id"]
            result_path = store.result_path(job_id)
            worker_command = [sys.executable, "-m", "radar_quantum_bench.local", "worker",
                              "--data-dir", temp, "--once"]
            with subprocess.Popen(
                [sys.executable, "-c", PAUSED_WORKER, temp], cwd=ROOT,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            ) as child:
                try:
                    ready, _, _ = select.select([child.stdout], [], [], 90)
                    self.assertTrue(ready, "worker did not reach the checkpoint")
                    marker = child.stdout.readline()
                    if marker != b"checkpoint\n":
                        self.fail(f"worker stopped before checkpoint: {marker!r}, exit={child.poll()}")

                    active = store.get(job_id)
                    self.assertEqual(active["status"], "running")
                    self.assertEqual(len(active["attempts"]), 1)
                    partial = load_result(result_path)
                    self.assertEqual(partial["summary"]["total_shots"], 1024)
                    self.assertEqual([a["status"] for a in partial["attempts"]],
                                     ["ok", "ok", "ok", "running"])

                    competing = subprocess.run(worker_command, cwd=ROOT, capture_output=True,
                                               text=True, timeout=60)
                    self.assertNotEqual(competing.returncode, 0)
                    self.assertEqual(store.get(job_id), active)
                finally:
                    if child.poll() is None:
                        child.kill()
                    child.communicate(timeout=30)
                self.assertEqual(child.returncode, -signal.SIGKILL)

            self.assertEqual(store.get(job_id)["status"], "running")
            resumed = subprocess.run(worker_command, cwd=ROOT, capture_output=True,
                                     text=True, timeout=90)
            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            final_job = store.submit("resume-after-kill", "bell", 42)
            self.assertEqual((final_job["id"], final_job["status"]), (job_id, "completed"))
            interrupted, completed = final_job["attempts"]
            self.assertEqual(interrupted["id"], active["attempts"][0]["id"])
            self.assertEqual((interrupted["status"], interrupted["error_code"]), ("failed", "Interrupted"))
            self.assertEqual(completed["status"], "completed")

            final = load_result(result_path)
            self.assertTrue(final["summary"]["complete"])
            self.assertEqual(final["run_id"], partial["run_id"])
            self.assertEqual(final["summary"]["total_shots"], 20480)
            self.assertEqual(final["attempts"][:3], partial["attempts"][:3])
            original, retried = final["attempts"][3:5]
            self.assertEqual((original["condition"], original["repetition"], original["seed"]),
                             (retried["condition"], retried["repetition"], retried["seed"]))
            self.assertEqual((original["status"], original["error"]), ("failed", "Interrupted"))
            self.assertEqual((retried["status"], retried["attempt"]), ("ok", 2))
            measured = [(a["condition"], a["repetition"]) for a in final["attempts"]
                        if a["status"] == "ok" and not a["warmup"]]
            self.assertEqual(len(measured), 20)
            self.assertEqual(len(set(measured)), 20)
