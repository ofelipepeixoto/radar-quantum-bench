import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONDITIONS = ("ideal", "readout_2pct")
OUTCOMES = ("00", "01", "10", "11")
SHOTS = 1024
REPETITIONS = 10


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "radar_quantum_bench", *map(str, args)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


class BellCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        cls.source = Path(temporary.name) / "bell.json"
        result = run_cli("run", "--output", cls.source)
        if result.returncode:
            raise RuntimeError(f"Bell simulation failed:\n{result.stdout}\n{result.stderr}")
        cls.document = json.loads(cls.source.read_text(encoding="utf-8"))

    def copy_result(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return Path(shutil.copyfile(self.source, Path(temporary.name) / "bell.json"))

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, f"{result.stdout}\n{result.stderr}")

    def test_run_records_circuit_measurements_and_warmups(self):
        data = self.document
        self.assertEqual(data["schema_version"], 2)
        self.assertEqual(data["config"]["shots"], SHOTS)
        self.assertEqual(data["config"]["repetitions"], REPETITIONS)
        logical = data["environment"]["logical_qasm"]
        compiled = data["environment"]["compiled_qasm"]
        for circuit in (logical, compiled):
            self.assertIn("OPENQASM", circuit)
            self.assertIn("measure", circuit)
        self.assertRegex(logical, r"(?m)^\s*h\s+")
        self.assertRegex(logical, r"(?m)^\s*cx\s+")

        observed = {condition: Counter() for condition in CONDITIONS}
        runs = Counter()
        warmups = Counter()
        seeds = set()
        for row in data["attempts"]:
            self.assertEqual(row["status"], "ok")
            self.assertIsInstance(row["warmup"], bool)
            self.assertGreaterEqual(row["attempt"], 1)
            self.assertGreaterEqual(row["elapsed_ms"], 0)
            condition = row["condition"]
            self.assertIn(condition, CONDITIONS)
            self.assertTrue(row["counts"])
            self.assertTrue(set(row["counts"]).issubset(OUTCOMES))
            for count in row["counts"].values():
                self.assertIs(type(count), int)
                self.assertGreaterEqual(count, 0)
            if row["warmup"]:
                warmups[condition] += 1
                continue
            self.assertEqual(sum(row["counts"].values()), SHOTS)
            self.assertNotIn(row["seed"], seeds)
            seeds.add(row["seed"])
            runs[condition, row["repetition"]] += 1
            observed[condition].update(row["counts"])

        self.assertEqual(warmups, {condition: 1 for condition in CONDITIONS})
        self.assertEqual(runs, {
            (condition, repetition): 1
            for condition in CONDITIONS
            for repetition in range(REPETITIONS)
        })
        summary = data["summary"]
        self.assertIs(summary["complete"], True)
        self.assertEqual(summary["total_shots"], 2 * SHOTS * REPETITIONS)
        ideal = {"00": 0.5, "01": 0.0, "10": 0.0, "11": 0.5}
        flip = 0.02
        odd_flip = flip * (1 - flip)
        noisy = {"00": 0.5 - odd_flip, "01": odd_flip, "10": odd_flip, "11": 0.5 - odd_flip}
        self.assertEqual(observed["ideal"]["01"] + observed["ideal"]["10"], 0)
        self.assertGreater(observed["readout_2pct"]["01"] + observed["readout_2pct"]["10"], 0)
        for condition, prediction in (("ideal", ideal), ("readout_2pct", noisy)):
            with self.subTest(condition=condition):
                measured = observed[condition]
                total = SHOTS * REPETITIONS
                metrics = summary["conditions"][condition]
                self.assertEqual(Counter(metrics["counts"]), measured)
                fraction = (measured["00"] + measured["11"]) / total
                tvd = sum(abs(measured[word] / total - ideal[word]) for word in OUTCOMES) / 2
                self.assertAlmostEqual(metrics["valid_fraction"], fraction)
                self.assertAlmostEqual(metrics["tvd"], tvd)
                for word in OUTCOMES:
                    self.assertAlmostEqual(measured[word] / total, prediction[word], delta=0.0235)

    def test_verify_accepts_original_and_rejects_changed_metric(self):
        self.assert_success(run_cli("verify", self.source))
        path = self.copy_result()
        data = json.loads(path.read_text(encoding="utf-8"))
        data["summary"]["conditions"]["ideal"]["valid_fraction"] -= 0.125
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertNotEqual(run_cli("verify", path).returncode, 0)

    def test_missing_version_or_impossible_ideal_measurement_fails_verification(self):
        from radar_quantum_bench.experiment import _recalculate

        for defect in ("version", "ideal"):
            with self.subTest(defect=defect):
                path = self.copy_result()
                doc = json.loads(path.read_bytes())
                if defect == "version":
                    del doc["environment"]["versions"]["qiskit-aer"]
                else:
                    row = next(r for r in doc["attempts"] if r["condition"] == "ideal" and not r["warmup"])
                    row["counts"]["00"] -= 1
                    row["counts"]["01"] += 1
                    doc["summary"] = _recalculate(doc)
                path.write_text(json.dumps(doc), encoding="utf-8")
                self.assertNotEqual(run_cli("verify", path).returncode, 0)

    def test_sampling_again_with_recorded_seeds_reproduces_counts(self):
        from radar_quantum_bench.aer import build_runner

        _, sample = build_runner()
        for condition in CONDITIONS:
            with self.subTest(condition=condition):
                record = next(
                    row for row in self.document["attempts"]
                    if row["condition"] == condition and not row["warmup"]
                )
                repeated = sample(condition, self.document["config"]["shots"], record["seed"])
                self.assertEqual(Counter(repeated), Counter(record["counts"]))

    def test_run_refuses_to_overwrite_existing_output(self):
        path = self.copy_result()
        original = path.read_bytes()
        self.assertNotEqual(run_cli("run", "--output", path).returncode, 0)
        self.assertEqual(path.read_bytes(), original)

    def test_resume_keeps_finished_attempts_and_summary(self):
        path = self.copy_result()
        self.assert_success(run_cli("run", "--output", path, "--resume"))
        resumed = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(resumed["attempts"], self.document["attempts"])
        self.assertEqual(resumed["summary"], self.document["summary"])
        self.assert_success(run_cli("verify", path))


if __name__ == "__main__":
    unittest.main()
