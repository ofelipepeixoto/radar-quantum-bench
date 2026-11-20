import json
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEEDS = {"ghz": 20261220, "bv": 20261320}
IDEAL = {"ghz": {"000": 0.5, "111": 0.5}, "bv": {"110": 1.0}}
NOISY_VALID = {"ghz": 0.9412, "bv": 0.941192}
WORDS = tuple(format(index, "03b") for index in range(8))
SHOTS = 1024
REPETITIONS = 10
SAMPLING_TOLERANCE = 0.0235


def cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "radar_quantum_bench", *map(str, args)],
        cwd=ROOT, capture_output=True, text=True, timeout=120, check=False,
    )


def predicted_readout(circuit, word):
    probability = 0.0
    for initial, weight in IDEAL[circuit].items():
        differences = sum(left != right for left, right in zip(initial, word))
        probability += weight * 0.02**differences * 0.98**(3 - differences)
    return probability


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temp.cleanup)
        cls.folder = Path(temp.name)
        cls.documents = {}
        for circuit, seed in SEEDS.items():
            path = cls.folder / f"{circuit}.json"
            result = cli("run", "--circuit", circuit, "--seed", seed, "--output", path)
            if result.returncode:
                raise RuntimeError(f"{circuit}: {result.stdout}\n{result.stderr}")
            cls.documents[circuit] = json.loads(path.read_text(encoding="utf-8"))

    def test_circuits_record_their_qubits_and_measurement_map(self):
        for circuit, doc in self.documents.items():
            with self.subTest(circuit=circuit):
                self.assertEqual(doc["schema_version"], 2)
                config = doc["config"]
                self.assertEqual(config["circuit"], circuit)
                self.assertEqual(config["base_seed"], SEEDS[circuit])
                self.assertEqual((config["shots"], config["repetitions"]), (SHOTS, REPETITIONS))
                env = doc["environment"]
                self.assertEqual(env["bit_order"], "c2c1c0")
                self.assertCountEqual(env["bit_map"], [
                    {"compiled_qubit": index, "classical_bit": index} for index in range(3)
                ])
                for kind in ("logical", "compiled"):
                    resources = env[f"{kind}_resources"]
                    self.assertEqual(resources["qubits"], 4 if circuit == "bv" else 3)
                    self.assertEqual(resources["measured_qubits"], 3)
                    qasm = env[f"{kind}_qasm"]
                    self.assertIn("OPENQASM", qasm)
                    self.assertIn("measure", qasm)
                if circuit == "bv":
                    ideal_counts = doc["summary"]["conditions"]["ideal"]["counts"]
                    self.assertEqual(ideal_counts["110"], SHOTS * REPETITIONS)
                    self.assertEqual(ideal_counts["011"], 0)

    def test_measured_and_predicted_distributions(self):
        for circuit, doc in self.documents.items():
            self.assertIs(doc["summary"]["complete"], True)
            self.assertEqual(doc["summary"]["total_shots"], 2 * REPETITIONS * SHOTS)
            for condition in ("ideal", "readout_2pct"):
                with self.subTest(circuit=circuit, condition=condition):
                    rows = [row for row in doc["attempts"] if row["condition"] == condition]
                    self.assertEqual(sum(row["warmup"] for row in rows), 1)
                    measured_rows = [row for row in rows if not row["warmup"]]
                    self.assertCountEqual(
                        [row["repetition"] for row in measured_rows], range(REPETITIONS)
                    )
                    counts = Counter()
                    for row in measured_rows:
                        self.assertEqual(row["status"], "ok")
                        self.assertEqual(set(row["counts"]), set(WORDS))
                        self.assertEqual(sum(row["counts"].values()), SHOTS)
                        counts.update(row["counts"])
                    metrics = doc["summary"]["conditions"][condition]
                    self.assertEqual(set(metrics["counts"]), set(WORDS))
                    self.assertEqual(counts, metrics["counts"])
                    total = REPETITIONS * SHOTS
                    frequencies = {word: counts[word] / total for word in WORDS}
                    ideal = IDEAL[circuit]
                    expected = doc["theoretical_probabilities"][condition]
                    self.assertEqual(set(expected), set(WORDS))
                    for word in WORDS:
                        predicted = (ideal.get(word, 0.0) if condition == "ideal"
                                     else predicted_readout(circuit, word))
                        self.assertAlmostEqual(expected[word], predicted, places=12)
                        self.assertAlmostEqual(frequencies[word], predicted, delta=SAMPLING_TOLERANCE)
                        if condition == "ideal" and word not in ideal:
                            self.assertEqual(counts[word], 0)
                    valid = sum(frequencies[word] for word in ideal)
                    theoretical_valid = 1.0 if condition == "ideal" else NOISY_VALID[circuit]
                    self.assertAlmostEqual(sum(expected[word] for word in ideal), theoretical_valid)
                    self.assertAlmostEqual(metrics["valid_fraction"], valid)
                    self.assertAlmostEqual(valid, theoretical_valid, delta=SAMPLING_TOLERANCE)
                    tvd = 0.5 * sum(abs(frequencies[word] - ideal.get(word, 0.0)) for word in WORDS)
                    self.assertAlmostEqual(metrics["tvd"], tvd)

    def test_noisy_repetition_replays_with_recorded_seed(self):
        from radar_quantum_bench.aer import build_runner

        for circuit, doc in self.documents.items():
            with self.subTest(circuit=circuit):
                _, sample = build_runner(circuit)
                row = next(row for row in doc["attempts"]
                           if row["condition"] == "readout_2pct" and row["repetition"] == 0)
                self.assertEqual(sample(row["condition"], SHOTS, row["seed"]), row["counts"])

    def test_verify_accepts_v2_and_legacy_bell(self):
        legacy = ROOT / "examples" / "bell.json"
        self.assertEqual(json.loads(legacy.read_text(encoding="utf-8"))["schema_version"], 1)
        for path in (legacy, self.folder / "ghz.json", self.folder / "bv.json"):
            with self.subTest(path=path.name):
                result = cli("verify", path)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_verify_rejects_v2_with_circuit_changed_to_bell(self):
        for circuit in SEEDS:
            with self.subTest(circuit=circuit):
                original = self.folder / f"{circuit}.json"
                modified = json.loads(original.read_text(encoding="utf-8"))
                modified["config"]["circuit"] = "bell"
                path = self.folder / f"{circuit}-as-bell.json"
                path.write_text(json.dumps(modified), encoding="utf-8")
                self.assertNotEqual(cli("verify", path).returncode, 0)

    def test_verify_rejects_swapped_circuits_malformed_counts_and_duplicate_fields(self):
        for defect in ("swapped_qasm", "null_counts", "duplicate"):
            with self.subTest(defect=defect):
                doc = json.loads((self.folder / "ghz.json").read_text())
                if defect == "swapped_qasm":
                    other = self.documents["bv"]["environment"]
                    for key in ("logical_qasm", "compiled_qasm", "logical_qasm_sha256",
                                "compiled_qasm_sha256", "logical_resources", "compiled_resources"):
                        doc["environment"][key] = other[key]
                elif defect == "null_counts":
                    doc["attempts"][0]["counts"] = None
                text = json.dumps(doc)
                if defect == "duplicate":
                    text = text.replace('"schema_version": 2', '"schema_version": 1, "schema_version": 2', 1)
                path = self.folder / f"{defect}.json"
                path.write_text(text)
                result = cli("verify", path)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertNotIn("Traceback", result.stderr)

    def test_unrecognized_circuit_is_an_argument_error(self):
        path = self.folder / "unknown.json"
        self.assertEqual(cli("run", "--circuit", "unknown", "--output", path).returncode, 2)
        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
