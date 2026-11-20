from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
import unittest
from uuid import UUID, uuid4

from radar_quantum_bench.store import Conflict, InvalidState, NotFound, QueueFull, Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.store = Store(self.root, capacity=2)

    def test_idempotent_across_connections_and_capacity(self):
        a = self.store.submit("same", "bell", 1)
        b = Store(self.root, capacity=2)
        self.assertEqual(a, b.submit("same", "bell", 1))
        self.store.submit("second", "ghz", 2)
        self.assertEqual(a, b.submit("same", "bell", 1))
        for circuit, seed in (("ghz", 1), ("bell", 2)):
            with self.assertRaises(Conflict):
                b.submit("same", circuit, seed)
        with self.assertRaises(QueueFull):
            b.submit("third", "bell", 4)
        c = self.store.claim()
        self.assertEqual(c["id"], a["id"])
        with self.assertRaises(QueueFull):
            self.store.submit("third", "bell", 4)
        self.store.finish(a["id"], c["attempt_id"], True)
        self.assertEqual("completed", b.submit("same", "bell", 1)["status"])
        self.assertNotEqual(b.submit("third", "bell", 4)["id"], a["id"])

    def test_concurrent_submission_capacity_and_claim(self):
        count = 8
        stores = [Store(self.root, capacity=2) for _ in range(count)]
        def parallel(fn):
            barrier = Barrier(count)
            def work(i):
                barrier.wait(timeout=5)
                return fn(stores[i], i)
            with ThreadPoolExecutor(max_workers=count) as pool:
                return list(pool.map(work, range(count)))
        ids = parallel(lambda store, i: store.submit("shared", "bell", 99)["id"])
        self.assertEqual(len(set(ids)), 1)
        def submit_distinct(store, i):
            try:
                return store.submit(f"unique-{i}", "bell", 99)["id"]
            except QueueFull:
                return None
        new = [jobid for jobid in parallel(submit_distinct) if jobid]
        self.assertEqual(len(new), 1)
        claimed = [job for job in parallel(lambda store, i: store.claim()) if job]
        self.assertEqual({job["id"] for job in claimed}, {ids[0], new[0]})
        self.assertEqual(len(claimed), 2)
        for job in claimed:
            self.assertEqual(job["attempt_id"], job["attempts"][0]["id"])
            self.assertEqual(len(job["attempts"]), 1)

    def test_retry_and_recovery_preserve_attempts_and_reject_stale_finishes(self):
        store = self.store
        jobid = store.submit("one", "bv", 17)["id"]
        with self.assertRaises(InvalidState):
            store.retry(jobid, "retry")
        first = store.claim()["attempt_id"]
        self.assertEqual(store.recover(), 1)
        reopened = Store(self.root)
        self.assertEqual(reopened.recover(), 0)
        self.assertEqual(store.get(jobid)["status"], "queued")
        second = reopened.claim()["attempt_id"]
        self.assertNotEqual(first, second)
        with self.assertRaises(InvalidState):
            store.finish(jobid, first, True)
        state = store.get(jobid)
        self.assertEqual(state["status"], "running")
        interrupted, fresh = state["attempts"]
        self.assertEqual((interrupted["status"], interrupted["error_code"]), ("failed", "Interrupted"))
        self.assertIsNotNone(interrupted["finished_at"])
        self.assertIsNone(fresh["finished_at"])
        reopened.finish(jobid, second, False, "SimulationFailed")
        queued = store.retry(jobid, "retry")
        self.assertEqual(queued["status"], "queued")
        self.assertEqual(len(queued["attempts"]), 2)
        self.assertEqual(queued["attempts"][1]["error_code"], "SimulationFailed")
        self.assertEqual(reopened.retry(jobid, "retry"), queued)
        with self.assertRaises(InvalidState):
            reopened.retry(jobid, "another-key")
        third = store.claim()["attempt_id"]
        reopened.finish(jobid, third, True)
        self.assertEqual(store.retry(jobid, "retry")["status"], "completed")
        self.assertEqual(len(store.get(jobid)["attempts"]), 3)
        with self.assertRaises(InvalidState):
            store.finish(jobid, third, False, "Repeated")
        self.assertIsNone(reopened.claim())

    def test_retry_capacity_and_key_scoped_to_job(self):
        store = Store(self.root, capacity=1)
        a = store.submit("a", "bell", 1)["id"]
        store.finish(a, store.claim()["attempt_id"], False)
        b = store.submit("b", "bell", 1)["id"]
        with self.assertRaises(QueueFull):
            store.retry(a, "shared")
        store.finish(b, store.claim()["attempt_id"], False)
        self.assertEqual(store.retry(a, "shared")["status"], "queued")
        store.finish(a, store.claim()["attempt_id"], True)
        self.assertEqual(store.retry(b, "shared")["status"], "queued")

    def test_pagination_id_validation_and_public_fields(self):
        ids = [self.store.submit(key, "bell", 12)["id"] for key in ("a", "b")]
        self.assertEqual([j["id"] for j in self.store.list_jobs()], ids[::-1])
        self.assertEqual(self.store.list_jobs(limit=1, offset=1)[0]["id"], ids[0])
        self.assertEqual(self.store.list_jobs(limit=0), [])
        self.assertEqual(self.store.list_jobs(offset=4), [])
        job = self.store.get(ids[0])
        self.assertEqual(set(job), {"id", "circuit", "base_seed", "status", "created_at", "updated_at", "attempts", "result_sha256"})
        self.assertEqual(UUID(job["id"]).version, 4)
        self.assertEqual(self.store.result_path(ids[0]), self.root / "results" / f"{ids[0]}.json")
        with self.assertRaises(NotFound):
            self.store.get(str(uuid4()))
        for bad in ("../outside", "not-a-uuid", "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA", "", None):
            for method in (self.store.get, self.store.result_path):
                with self.subTest(bad=bad, method=method), self.assertRaises(NotFound):
                    method(bad)
        for limit, offset in ((-1, 0), (1, -4), (True, 0)):
            with self.assertRaises(ValueError):
                self.store.list_jobs(limit, offset)
