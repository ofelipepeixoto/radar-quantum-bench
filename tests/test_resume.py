import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from radar_quantum_bench import aer, experiment


class RecoveryTests(unittest.TestCase):
    def test_interruption_after_first_measurement_retries_only_missing_work(self):
        metadata, sample = aer.build_runner()
        calls = 0

        def fail_once(condition, shots, seed):
            nonlocal calls
            calls += 1
            if calls == 4:
                raise RuntimeError("synthetic interruption")
            return sample(condition, shots, seed)

        with TemporaryDirectory() as folder:
            path = Path(folder) / "bell.json"
            with patch.object(aer, "build_runner", return_value=(metadata, fail_once)):
                with self.assertRaisesRegex(RuntimeError, "synthetic interruption"):
                    experiment.run(path)
            partial = experiment.load_result(path)
            self.assertFalse(partial["summary"]["complete"])
            self.assertEqual(partial["summary"]["total_shots"], 1024)
            last = partial["attempts"][-1]
            self.assertEqual(last["status"], "failed")

            # A hard kill leaves the last persisted attempt running. On restart
            # the previous record must remain visible and cannot count as data.
            last["status"] = "running"
            last.pop("error")
            last.pop("elapsed_ms")
            partial["summary"] = experiment._recalculate(partial)
            path.write_text(json.dumps(partial), encoding="utf-8")
            with patch.object(aer, "build_runner", return_value=(metadata, sample)):
                finished = experiment.run(path, resume=True)
            self.assertEqual(finished["summary"]["total_shots"], 20480)
            self.assertEqual(partial["attempts"][:3], finished["attempts"][:3])
            original, retried = finished["attempts"][3:5]
            self.assertEqual((original["status"], original["error"]), ("failed", "Interrupted"))
            self.assertEqual((retried["status"], retried["attempt"]), ("ok", 2))
            self.assertEqual(original["seed"], retried["seed"])
            self.assertEqual(len(finished["sessions"]), 2)
            self.assertEqual(experiment.load_result(path), finished)

    def test_output_lock_and_invalid_seed(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "bell.json"
            with experiment._exclusive_output(path):
                with self.assertRaisesRegex(ValueError, "Outra coleta"):
                    experiment.run(path)
            for seed in (-1, 2**32, True):
                with self.subTest(seed=seed), self.assertRaises(ValueError):
                    experiment.run(path, base_seed=seed)
            self.assertFalse(path.exists())
