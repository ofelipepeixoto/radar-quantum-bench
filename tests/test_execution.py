"""Limites observados em subprocessos reais, com falhas sintéticas explícitas."""

from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
import textwrap
from time import monotonic, sleep
import unittest
from unittest.mock import patch

from radar_quantum_bench import aer, execution, experiment
from radar_quantum_bench.execution import WorkerLimits
from radar_quantum_bench.store import Store
from radar_quantum_bench.worker import run_worker


ROOT = Path(__file__).resolve().parents[1]
CANARY = "DIAGNOSTICO-FICTICIO-RESERVADO"


class BoundedExecutionTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(Path(self.enterContext(TemporaryDirectory())))

    def receipt(self, job_id):
        paths = list((self.store.root / "executions" / job_id).glob("*.json"))
        self.assertEqual(len(paths), 1)
        raw = paths[0].read_text()
        self.assertNotIn(CANARY, raw)
        self.assertNotIn(str(self.store.root), raw)
        return json.loads(raw)

    @staticmethod
    def fixture(code, memory_mib=256):
        script = (
            "import os,sys,time,signal,resource\n"
            "from radar_quantum_bench.execution import _prepare_child\n"
            f"_prepare_child({os.getpid()}, {memory_mib})\n" + textwrap.dedent(code)
        )
        return [sys.executable, "-B", "-c", script]

    def test_limits_reject_invalid_values_before_claiming_work(self):
        for timeout in (True, 0, -1, float("nan"), float("inf"), 86401, "120"):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                WorkerLimits(timeout_seconds=timeout)
        for memory in (True, 255, 16385, 512.0, "2048"):
            with self.subTest(memory=memory), self.assertRaises(ValueError):
                WorkerLimits(memory_mib=memory)
        self.assertEqual(WorkerLimits(), WorkerLimits(timeout_seconds=120, memory_mib=2048))
        with self.assertRaises(ValueError):
            run_worker(self.store, once=True, limits="unlimited")
        self.assertEqual(self.store.list_jobs(), [])

    def test_three_scientific_jobs_run_under_limits_and_match_the_recorded_counts(self):
        for circuit in ("bell", "ghz", "bv"):
            with self.subTest(circuit=circuit):
                reference = experiment.load_result(ROOT / "examples" / "catalogo" / f"{circuit}.json")
                job = self.store.submit(circuit, circuit, reference["config"]["base_seed"])
                self.assertEqual(run_worker(self.store, once=True, limits=WorkerLimits()), 0)
                done = self.store.get(job["id"])
                result_path = self.store.result_path(job["id"])
                result = experiment.load_result(result_path)
                self.assertEqual(done["status"], "completed")
                self.assertEqual(done["result_sha256"], sha256(result_path.read_bytes()).hexdigest())
                self.assertEqual(result["summary"]["total_shots"], 20480)
                for condition in ("ideal", "readout_2pct"):
                    self.assertEqual(result["summary"]["conditions"][condition]["counts"],
                                     reference["summary"]["conditions"][condition]["counts"])
                receipt = self.receipt(job["id"])
                self.assertEqual(receipt["schema_version"], "rqb-execution/1")
                self.assertEqual(receipt["attempt_id"], done["attempts"][0]["id"])
                self.assertEqual(receipt["limits"], {"wall_seconds": 120, "virtual_memory_mib": 2048})
                self.assertEqual((receipt["status"], receipt["error_code"], receipt["exit_code"]),
                                 ("completed", None, 0))
                self.assertGreater(receipt["peak_rss_kib"], 0)
                self.assertGreater(receipt["elapsed_ms"], 0)
                self.assertLess(receipt["elapsed_ms"], 120000)

    def test_timeout_preserves_checkpoint_and_retry_completes_only_missing_work(self):
        job = self.store.submit("timeout", "bell", 43)
        result_path = self.store.result_path(job["id"])
        metadata, sample = aer.build_runner()
        calls = 0

        def interrupt(condition, shots, seed):
            nonlocal calls
            calls += 1
            if calls == 4:
                raise RuntimeError("synthetic checkpoint")
            return sample(condition, shots, seed)

        with patch.object(aer, "build_runner", return_value=(metadata, interrupt)):
            with self.assertRaises(RuntimeError):
                experiment.run(result_path, base_seed=job["base_seed"])
        original = result_path.read_bytes()
        partial = experiment.load_result(result_path)
        self.assertEqual(partial["summary"]["total_shots"], 1024)
        with patch.object(execution, "_science_command", return_value=self.fixture("time.sleep(30)")):
            start = monotonic()
            self.assertEqual(run_worker(self.store, once=True,
                                        limits=WorkerLimits(timeout_seconds=0.15, memory_mib=256)), 1)
            self.assertLess(monotonic() - start, 3)
        failed = self.store.get(job["id"])
        self.assertEqual(failed["attempts"][0]["error_code"], "TimeLimitExceeded")
        self.assertEqual(result_path.read_bytes(), original)
        receipt = self.receipt(job["id"])
        self.assertEqual(receipt["error_code"], "TimeLimitExceeded")
        self.assertEqual(receipt["status"], "failed")
        self.assertGreater(receipt["peak_rss_kib"], 0)
        self.store.retry(job["id"], "after-timeout")
        self.assertEqual(run_worker(self.store, once=True, limits=WorkerLimits()), 0)
        final = experiment.load_result(result_path)
        self.assertEqual(final["run_id"], partial["run_id"])
        self.assertEqual(final["attempts"][:4], partial["attempts"])
        self.assertEqual(final["summary"]["total_shots"], 20480)
        measured = [(a["condition"], a["repetition"]) for a in final["attempts"]
                    if a["status"] == "ok" and not a["warmup"]]
        self.assertEqual(len(measured), len(set(measured)))
        self.assertEqual(len(measured), 20)
        self.assertEqual(len(list((self.store.root / "executions" / job["id"]).glob("*.json"))), 2)

    def test_memory_allocation_failure_has_a_separate_code_and_sanitized_receipt(self):
        job = self.store.submit("memory", "bell", 44)
        command = self.fixture(f"""
            assert resource.getrlimit(resource.RLIMIT_AS) == (256*1024*1024,256*1024*1024)
            print({CANARY!r}, file=sys.stderr)
            try:
                bytearray(512 * 1024 * 1024)
            except MemoryError:
                sys.exit(75)
            sys.exit(99)
        """)
        with patch.object(execution, "_science_command", return_value=command):
            self.assertEqual(run_worker(self.store, once=True,
                                        limits=WorkerLimits(memory_mib=256)), 1)
        state = self.store.get(job["id"])
        self.assertEqual(state["attempts"][0]["error_code"], "MemoryLimitExceeded")
        receipt = self.receipt(job["id"])
        self.assertEqual(receipt["limits"]["virtual_memory_mib"], 256)
        self.assertEqual(receipt["error_code"], "MemoryLimitExceeded")
        self.assertEqual(receipt["exit_code"], 75)
        self.assertFalse(self.store.result_path(job["id"]).exists())

    def test_unknown_native_signal_is_not_misreported_as_a_memory_limit(self):
        job = self.store.submit("abort", "bell", 45)
        command = self.fixture("os.kill(os.getpid(),signal.SIGABRT)")
        with patch.object(execution, "_science_command", return_value=command):
            self.assertEqual(run_worker(self.store, once=True,
                                        limits=WorkerLimits(memory_mib=256)), 1)
        receipt = self.receipt(job["id"])
        self.assertEqual(receipt["error_code"], "ExecutionChildFailed")
        self.assertEqual(receipt["exit_code"], -signal.SIGABRT)

    def test_spawn_failure_does_not_copy_diagnostic_text_to_history_or_receipt(self):
        job = self.store.submit("spawn", "bell", 46)
        with patch.object(execution.subprocess, "Popen", side_effect=OSError(CANARY)):
            self.assertEqual(run_worker(self.store, once=True, limits=WorkerLimits()), 1)
        self.assertEqual(self.store.get(job["id"])["attempts"][0]["error_code"], "ExecutionSetupFailed")
        receipt = self.receipt(job["id"])
        self.assertEqual((receipt["status"], receipt["error_code"]), ("failed", "ExecutionSetupFailed"))
        self.assertIsNone(receipt["peak_rss_kib"])

    def test_parent_death_kills_child_releases_both_locks_and_allows_recovery(self):
        job = self.store.submit("parent-death", "bell", 47)
        marker = self.store.root / "child-pid"
        script = textwrap.dedent("""
            import os,sys
            from pathlib import Path
            from unittest.mock import patch
            from radar_quantum_bench import execution
            from radar_quantum_bench.execution import WorkerLimits
            from radar_quantum_bench.store import Store
            from radar_quantum_bench.worker import run_worker
            store=Store(Path(sys.argv[1]))
            fixture=("import os,time; from pathlib import Path; "
                     "from radar_quantum_bench.execution import _prepare_child; "
                     f"_prepare_child({os.getpid()},256); "
                     f"Path({str(store.root/'child-pid')!r}).write_text(str(os.getpid())); "
                     "time.sleep(30)")
            with patch.object(execution,'_science_command',return_value=[sys.executable,'-c',fixture]):
                run_worker(store,once=True,limits=WorkerLimits(timeout_seconds=30,memory_mib=256))
        """)
        parent = subprocess.Popen([sys.executable, "-B", "-c", script, str(self.store.root)],
                                  cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        child_pid = None
        try:
            until = monotonic() + 5
            while not marker.exists() and monotonic() < until:
                if parent.poll() is not None:
                    self.fail("O supervisor terminou antes de criar o filho de teste.")
                sleep(0.02)
            self.assertTrue(marker.exists(), "O filho de teste não iniciou.")
            child_pid = int(marker.read_text())
            self.assertEqual(self.store.get(job["id"])["status"], "running")
            parent.kill()
            parent.wait(timeout=3)
            until = monotonic() + 3
            while self.running(child_pid) and monotonic() < until:
                sleep(0.02)
            self.assertFalse(self.running(child_pid), "O filho continuou executando após SIGKILL do supervisor.")
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.wait(timeout=3)
            if child_pid and self.running(child_pid):
                os.kill(child_pid, signal.SIGKILL)
        self.assertEqual(run_worker(self.store, once=True, limits=WorkerLimits()), 0)
        state = self.store.get(job["id"])
        self.assertEqual(state["status"], "completed")
        self.assertEqual([a["error_code"] for a in state["attempts"]], ["Interrupted", None])
        self.assertEqual(experiment.load_result(self.store.result_path(job["id"]))["summary"]["total_shots"], 20480)

    @staticmethod
    def running(pid):
        try:
            # An adopted zombie has stopped and cannot hold the worker/result locks.
            return Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1][0] != "Z"
        except FileNotFoundError:
            return False
