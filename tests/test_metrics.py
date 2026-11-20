import unittest

from radar_quantum_bench.metrics import EXPECTED, summarize


def attempt(counts=None, **overrides):
    record = {
        "condition": "ideal",
        "repetition": 0,
        "attempt": 1,
        "status": "ok",
        "warmup": False,
        "counts": {"00": 5, "11": 5} if counts is None else counts,
        "elapsed_ms": 2.0,
        "seed": 42,
    }
    record.update(overrides)
    return record


class MetricsTests(unittest.TestCase):
    def test_theoretical_conditions_and_reference(self):
        records = [
            attempt({"00": 1250, "11": 1250}),
            attempt({"00": 1201, "01": 49, "10": 49, "11": 1201}, condition="readout_2pct"),
        ]
        result = summarize(records, shots=2500, repetitions=1)
        self.assertTrue(result["complete"])
        self.assertEqual(result["total_shots"], 5000)
        ideal = result["conditions"]["ideal"]
        noisy = result["conditions"]["readout_2pct"]
        self.assertEqual(ideal["valid_fraction"], 1)
        self.assertEqual(ideal["tvd"], 0)
        self.assertAlmostEqual(noisy["valid_fraction"], 0.9608)
        self.assertAlmostEqual(noisy["tvd"], 0.0392)
        self.assertEqual(noisy["valid_shots"], 2402)
        self.assertEqual({key: n / 2500 for key, n in noisy["counts"].items()}, EXPECTED["readout_2pct"])

    def test_unbalanced_ideal_sample_is_valid(self):
        row = summarize([attempt({"00": 10})], 10, 1)["conditions"]["ideal"]
        self.assertEqual(row["counts"], {"00": 10, "01": 0, "10": 0, "11": 0})
        self.assertEqual(row["tvd"], 0.5)
        self.assertEqual(row["valid_fraction"], 1)
        self.assertAlmostEqual(row["wilson95"][0], 0.7224672001371107)
        self.assertEqual(row["wilson95"][1], 1.0)

    def test_disjoint_and_mixed_samples(self):
        row = summarize([attempt({"01": 5, "10": 5})], 10, 1)["conditions"]["ideal"]
        self.assertEqual(row["tvd"], 1)
        self.assertEqual(row["wilson95"][0], 0)
        self.assertAlmostEqual(row["wilson95"][1], 0.2775327998628892)
        row = summarize([attempt({"00": 5, "01": 5})], 10, 1)["conditions"]["ideal"]
        self.assertEqual(row["valid_fraction"], 0.5)
        self.assertAlmostEqual(row["wilson95"][0], 0.236593090512564)
        self.assertAlmostEqual(row["wilson95"][1], 0.763406909487436)

    def test_warmup_failures_and_retries_do_not_add_shots_or_time(self):
        records = [
            attempt({"01": 10}, warmup=True, repetition=-1, elapsed_ms=400),
            attempt(status="failed", elapsed_ms=500),
            attempt(attempt=2, elapsed_ms=4),
            attempt(repetition=1, seed=43, elapsed_ms=10),
            attempt(condition="readout_2pct", status="running", elapsed_ms=None),
        ]
        for record in (records[1], records[4]):
            del record["counts"]
        result = summarize(records, 10, 2)
        self.assertEqual(result, summarize(list(reversed(records)), 10, 2))
        self.assertFalse(result["complete"])
        self.assertEqual(result["total_shots"], 20)
        ideal = result["conditions"]["ideal"]
        self.assertEqual(ideal["completed_repetitions"], 2)
        self.assertEqual(ideal["failed_attempts"], 1)
        self.assertEqual(ideal["median_ms"], 7)
        self.assertEqual(ideal["quartiles_ms"], [5.5, 8.5])
        self.assertEqual(ideal["iqr_ms"], 3)
        noisy = result["conditions"]["readout_2pct"]
        self.assertEqual(noisy["completed_repetitions"], 0)
        for key in ("valid_fraction", "wilson95", "tvd", "median_ms", "iqr_ms"):
            self.assertIsNone(noisy[key])

    def test_duplicate_attempt_and_duplicate_success_are_rejected(self):
        for records in (
            [attempt(status="failed"), attempt(status="failed")],
            [attempt(), attempt(attempt=2)],
            [attempt(warmup=True, repetition=-1), attempt(warmup=True, repetition=-1, attempt=2)],
        ):
            with self.subTest(records=records), self.assertRaises(ValueError):
                summarize(records, 10, 1)

    def test_invalid_counts_and_duration_are_rejected(self):
        cases = [
            {"counts": None}, {"counts": {}}, {"counts": {"1": 10}}, {"counts": {"x": 0, "11": 10}},
            {"counts": {"00": 10.0}}, {"counts": {"00": True, "11": 9}},
            {"counts": {"00": -1, "11": 11}}, {"counts": {"00": 9}},
            {"elapsed_ms": None}, {"elapsed_ms": True}, {"elapsed_ms": -1},
            {"elapsed_ms": float("nan")}, {"elapsed_ms": float("inf")},
        ]
        missing = attempt()
        del missing["counts"]
        for record in [missing] + [{**attempt(), **changes} for changes in cases]:
            with self.subTest(record=record), self.assertRaises(ValueError):
                summarize([record], 10, 1)

    def test_invalid_record_keys_and_parameters_are_rejected(self):
        for overrides in (
            {"condition": "hardware"}, {"status": "partial"}, {"seed": False},
            {"attempt": 0}, {"warmup": 0}, {"repetition": 1},
            {"repetition": -1}, {"warmup": True, "repetition": 0},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                summarize([attempt(**overrides)], 10, 1)
        for shots, reps in ((0, 1), (-1, 1), (True, 1), (10, False), (10, 1.1)):
            with self.subTest(shots=shots, reps=reps), self.assertRaises(ValueError):
                summarize([], shots, reps)
        self.assertFalse(summarize([], 10, 1)["complete"])


if __name__ == "__main__":
    unittest.main()
