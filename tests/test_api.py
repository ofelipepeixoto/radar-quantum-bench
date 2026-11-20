import io
import json
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4
from zipfile import ZipFile

from fastapi.testclient import TestClient

from radar_quantum_bench.api import create_app
from radar_quantum_bench.bundle import check_bundle


BASE = "/api/v1"
JOBS = BASE + "/comparacoes"
ORIGIN = "http://127.0.0.1:8000"


class LocalApiTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.app = create_app(self.directory, capacity=2)
        self.client = self.enterContext(TestClient(self.app, base_url=ORIGIN))

    def submit(self, data, key):
        return self.client.post(JOBS, json=data, headers={"Idempotency-Key": key})

    def assert_status(self, response, expected):
        self.assertEqual(response.status_code, expected, response.text[:1000])

    def test_catalog_and_empty_history(self):
        response = self.client.get(BASE + "/experimentos")
        self.assert_status(response, 200)
        catalog = {item["id"]: item for item in response.json()}
        self.assertEqual(set(catalog), {"bell", "ghz", "bv"})
        for item in catalog.values():
            self.assertEqual((item["shots"], item["repetitions"]), (1024, 10))
        self.assertEqual(catalog["bv"]["ideal"]["110"], 1.0)
        history = self.client.get(JOBS)
        self.assert_status(history, 200)
        self.assertEqual(history.json(), [])

    def test_openapi_is_available_without_hosted_documentation(self):
        for route in ("/docs", "/redoc"):
            with self.subTest(route=route):
                self.assert_status(self.client.get(route), 404)
        schema = self.client.get("/openapi.json")
        self.assert_status(schema, 200)
        self.assertIn("post", schema.json()["paths"][JOBS])

    def test_completed_jobs_reject_swapped_results_with_identical_configuration(self):
        from radar_quantum_bench.worker import run_worker

        store = self.app.state.store
        payload = {"circuit": "bv", "base_seed": 20261320}
        job_ids = []
        contents = []
        for key in ("replicate-a", "replicate-b"):
            created = self.submit(payload, key)
            self.assert_status(created, 202)
            job_id = created.json()["id"]
            job_ids.append(job_id)
            self.assertEqual(run_worker(store, once=True), 0)
            original = store.result_path(job_id).read_bytes()
            contents.append(original)
            detail = self.client.get(f"{JOBS}/{job_id}")
            self.assert_status(detail, 200)
            self.assertEqual(detail.json()["result_sha256"], sha256(original).hexdigest())
        self.assertNotEqual(job_ids[0], job_ids[1])
        self.assertNotEqual(json.loads(contents[0])["run_id"], json.loads(contents[1])["run_id"])
        store.result_path(job_ids[0]).write_bytes(contents[1])
        for suffix in ("", "/metricas", "/exportacao"):
            with self.subTest(suffix=suffix):
                self.assert_status(self.client.get(f"{JOBS}/{job_ids[0]}{suffix}"), 409)
        original_owner = self.client.get(f"{JOBS}/{job_ids[1]}/metricas")
        self.assert_status(original_owner, 200)
        self.assertIs(original_owner.json()["complete"], True)

    def test_failed_jobs_validate_checkpoint_configuration_without_final_digest(self):
        from radar_quantum_bench import experiment

        store = self.app.state.store
        example = Path(__file__).resolve().parents[1] / "examples/catalogo/bv.json"
        checkpoint = experiment.load_result(example)
        checkpoint["attempts"] = checkpoint["attempts"][:3]
        checkpoint["summary"] = experiment._recalculate(checkpoint)
        self.assertIs(checkpoint["summary"]["complete"], False)
        self.assertEqual(checkpoint["summary"]["total_shots"], 1024)
        seed = checkpoint["config"]["base_seed"]
        original = json.dumps(checkpoint).encode("utf-8")
        cases = (("bv", seed, 200), ("bv", seed + 1, 409), ("ghz", seed, 409))
        for index, (circuit, requested_seed, expected) in enumerate(cases):
            with self.subTest(circuit=circuit, seed=requested_seed):
                response = self.submit({"circuit": circuit, "base_seed": requested_seed}, str(index))
                self.assert_status(response, 202)
                job_id = response.json()["id"]
                claimed = store.claim()
                self.assertEqual(claimed["id"], job_id)
                store.result_path(job_id).write_bytes(original)
                store.finish(job_id, claimed["attempt_id"], False, "Interrupted")
                self.assertIsNone(store.get(job_id)["result_sha256"])
                for suffix in ("", "/metricas"):
                    self.assert_status(self.client.get(f"{JOBS}/{job_id}{suffix}"), expected)
                self.assert_status(self.client.get(f"{JOBS}/{job_id}/exportacao"), 409)

    def test_retrying_submission_does_not_consume_capacity(self):
        payload = {"circuit": "bv", "base_seed": 20261320}
        created = self.submit(payload, "first")
        self.assert_status(created, 202)
        job = created.json()
        UUID(job["id"])
        self.assertEqual(job["circuit"], "bv")
        self.assertEqual(job["base_seed"], 20261320)
        self.assertIn("attempts", job)
        second = self.submit({"circuit": "ghz"}, "second")
        self.assert_status(second, 202)
        self.assertNotEqual(job["id"], second.json()["id"])
        self.assert_status(self.submit({"circuit": "bell"}, "third"), 429)
        repeated = self.submit(payload, "first")
        self.assert_status(repeated, 202)
        self.assertEqual(repeated.json()["id"], job["id"])
        self.assert_status(self.submit({"circuit": "bell"}, "first"), 409)
        self.assert_status(self.submit({**payload, "base_seed": 23}, "first"), 409)

        page1 = self.client.get(JOBS, params={"limit": 1, "offset": 0})
        page2 = self.client.get(JOBS, params={"limit": 1, "offset": 1})
        for response in (page1, page2):
            self.assert_status(response, 200)
            self.assertEqual(len(response.json()), 1)
        listed = {page1.json()[0]["id"], page2.json()[0]["id"]}
        self.assertEqual(listed, {job["id"], second.json()["id"]})

    def test_request_validation(self):
        for index, payload in enumerate((
            {"circuit": "unknown"}, {"circuit": "bell", "unexpected": "field"},
            {"circuit": "bell", "base_seed": True}, {"circuit": "bell", "base_seed": -1},
            {"circuit": "bv", "base_seed": 2**32},
        )):
            with self.subTest(payload=payload):
                self.assert_status(self.submit(payload, str(index)), 422)
        self.assert_status(self.client.post(JOBS, json={"circuit": "bell"}), 422)
        for key in ("", "   ", "x" * 129):
            with self.subTest(key_length=len(key)):
                self.assert_status(self.submit({"circuit": "bell"}, key), 422)
        malformed = self.client.post(
            JOBS, content=b"{", headers={"Content-Type": "application/json", "Idempotency-Key": "invalid"}
        )
        self.assert_status(malformed, 422)
        self.assert_status(self.submit({"circuit": "ghz", "base_seed": 2**32 - 1}, "x" * 128), 202)

    def test_host_and_origin_boundaries(self):
        headers = {"Idempotency-Key": "origin", "Origin": "http://127.0.0.1:8123"}
        denied = self.client.post(JOBS, json={"circuit": "bell"}, headers=headers)
        self.assert_status(denied, 403)
        headers["Origin"] = ORIGIN
        allowed = self.client.post(JOBS, json={"circuit": "bell"}, headers=headers)
        self.assert_status(allowed, 202)
        self.assert_status(self.client.get(JOBS, headers={"Host": "untrusted.invalid"}), 400)
        self.assert_status(self.client.get(JOBS, headers={"Host": "localhost:8000"}), 200)

    def test_missing_ids_and_pending_artifacts(self):
        response = self.submit({"circuit": "ghz"}, "queued")
        self.assert_status(response, 202)
        job = response.json()
        path = f"{JOBS}/{job['id']}"
        detail = self.client.get(path)
        self.assert_status(detail, 200)
        self.assertEqual(detail.json()["id"], job["id"])
        self.assertIsNone(detail.json()["progress"])
        for suffix in ("/metricas", "/exportacao"):
            self.assert_status(self.client.get(path + suffix), 409)
        self.assert_status(self.client.post(path + "/retentativas", headers={"Idempotency-Key": "r"}), 409)
        missing = f"{JOBS}/{uuid4()}"
        for suffix in ("", "/metricas", "/exportacao"):
            with self.subTest(suffix=suffix):
                self.assert_status(self.client.get(missing + suffix), 404)
        self.assert_status(self.client.get(JOBS + "/not-a-uuid"), 422)

    def test_partial_bv_retry_and_download(self):
        from radar_quantum_bench import aer
        from radar_quantum_bench.worker import run_worker

        submitted = self.submit({"circuit": "bv", "base_seed": 20261320}, "sample")
        self.assert_status(submitted, 202)
        path = f"{JOBS}/{submitted.json()['id']}"
        environment, sample = aer.build_runner("bv")
        calls = 0

        def interrupted(condition, shots, seed):
            nonlocal calls
            calls += 1
            if calls == 4:
                raise RuntimeError("interrupted after first measurement")
            return sample(condition, shots, seed)

        with patch.object(aer, "build_runner", return_value=(environment, interrupted)):
            self.assertEqual(run_worker(self.app.state.store, once=True), 1)
        detail = self.client.get(path)
        self.assert_status(detail, 200)
        self.assertEqual(detail.json()["status"], "failed")
        partial = self.client.get(path + "/metricas")
        self.assert_status(partial, 200)
        self.assertIs(partial.json()["complete"], False)
        self.assertEqual(partial.json()["total_shots"], 1024)
        self.assertEqual(detail.json()["progress"], partial.json())
        self.assert_status(self.client.get(path + "/exportacao"), 409)

        retry = path + "/retentativas"
        self.assert_status(self.client.post(retry), 422)
        headers = {"Idempotency-Key": "retry-sample"}
        for _ in range(2):
            response = self.client.post(retry, headers=headers)
            self.assert_status(response, 202)
            self.assertEqual(response.json()["id"], submitted.json()["id"])
        self.assertEqual(run_worker(self.app.state.store, once=True), 0)
        metrics = self.client.get(path + "/metricas")
        self.assert_status(metrics, 200)
        summary = metrics.json()
        self.assertIs(summary["complete"], True)
        self.assertEqual(summary["total_shots"], 20480)
        self.assertEqual(summary["conditions"]["ideal"]["counts"]["110"], 10240)
        completed = self.client.get(path)
        self.assert_status(completed, 200)
        self.assertEqual(completed.json()["status"], "completed")
        self.assertEqual(completed.json()["progress"], summary)
        self.assertEqual(len(completed.json()["attempts"]), 2)
        self.assert_status(self.client.post(retry, headers={"Idempotency-Key": "new-retry"}), 409)

        exported = self.client.get(path + "/exportacao")
        self.assertEqual(exported.status_code, 200)
        self.assertEqual(exported.headers["content-type"].split(";")[0], "application/zip")
        archive = self.directory / "download.zip"
        archive.write_bytes(exported.content)
        check_bundle(archive)
        with ZipFile(io.BytesIO(exported.content)) as package:
            result = json.loads(package.read("result.json"))
        self.assertEqual(result["config"]["circuit"], "bv")
        self.assertEqual(result["summary"], summary)


if __name__ == "__main__":
    unittest.main()
