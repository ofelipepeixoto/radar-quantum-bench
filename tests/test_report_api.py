"""Relatório JSON, Markdown e pacote científico via API, com persistência e modelo local dublê."""

import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from uuid import uuid4
from zipfile import ZipFile

from fastapi.testclient import TestClient

from radar_quantum_bench.api import create_app
from radar_quantum_bench.experiment import _recalculate
from radar_quantum_bench.ollama import AdvisorError


ORIGIN = "http://127.0.0.1:8000"
JOBS = "/api/v1/comparacoes"
EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "catalogo" / "bell.json"
CANARY = "TEXTO-FICTICIO-FORA-DA-PROPOSTA"


class FakeAdvisor:
    model = "test:latest"
    identity = {"name": model, "digest": "a" * 64, "server_version": "1.0.0"}

    def __init__(self):
        self.calls = 0
        self.mode = "reverse"

    def propose(self, model_input):
        self.calls += 1
        if self.mode == "timeout":
            raise AdvisorError("tempo_esgotado")
        proposal = model_input["proposta_base"]
        if self.mode == "invalid":
            proposal["observacoes"][0]["texto"] = CANARY
        else:
            proposal["observacoes"].reverse()
        return proposal


class ReportApiTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.advisor = FakeAdvisor()
        app = create_app(self.root, advisor=self.advisor)
        self.store = app.state.store
        self.client = self.enterContext(TestClient(app, base_url=ORIGIN))

    def record(self, *, partial=False, run_id=None):
        # Use the versioned Aer counts; replicate the same acquisition if a test requests it.
        doc = json.loads(EXAMPLE.read_bytes())
        doc["run_id"] = run_id or str(uuid4())
        if partial:
            doc["attempts"] = doc["attempts"][:3]
            doc["summary"] = _recalculate(doc)
        job = self.store.submit(str(uuid4()), doc["config"]["circuit"], doc["config"]["base_seed"])
        claim = self.store.claim()
        self.assertEqual(claim["id"], job["id"])
        raw = json.dumps(doc).encode("utf-8")
        self.store.result_path(job["id"]).write_bytes(raw)
        self.store.finish(job["id"], claim["attempt_id"], not partial,
                          error_code="Interrupted" if partial else None,
                          result_sha256=None if partial else sha256(raw).hexdigest())
        return job["id"], doc, raw

    def test_capabilities_reads_and_downloads_do_not_invoke_the_model(self):
        with TestClient(create_app(self.root), base_url=ORIGIN) as default:
            self.assertEqual(default.get("/api/v1/relator").json(), {"modelo_local": False, "modelo": None})
        self.assertEqual(self.client.get("/api/v1/relator").json(), {"modelo_local": True, "modelo": self.advisor.model})
        job_id, document, raw = self.record()
        route = f"{JOBS}/{job_id}/relatorio"
        response = self.client.get(route)
        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(self.client.get(route).json(), report)
        self.assertEqual(report["estado"], "completo")
        self.assertEqual(report["origem_texto"], "deterministico")
        self.assertEqual(report["run_id"], document["run_id"])
        self.assertEqual(report["job_id"], job_id)
        self.assertEqual(report["result_sha256"], sha256(raw).hexdigest())
        self.assertEqual(self.client.get(route + ".json").json(), report)
        self.assertIn(sha256(raw).hexdigest(), self.client.get(route + ".md").text)
        self.assertEqual(self.advisor.calls, 0)

    def test_busy_reporter_keeps_reads_and_export_available(self):
        job_id, _, _ = self.record()
        route = f"{JOBS}/{job_id}/relatorio"
        started, release = Event(), Event()

        def slow_model(data):
            self.advisor.calls += 1
            started.set()
            if not release.wait(5):
                raise AdvisorError("tempo_esgotado")
            return data["proposta_base"]

        self.advisor.propose = slow_model
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(self.client.post, route)
            try:
                self.assertTrue(started.wait(2))
                self.assertEqual(self.client.post(route).status_code, 429)
                self.assertEqual(self.client.get(route).status_code, 200)
                self.assertEqual(self.client.get(f"{JOBS}/{job_id}/exportacao").status_code, 200)
            finally:
                release.set()
            self.assertEqual(pending.result(timeout=2).status_code, 200)
        self.assertEqual(self.advisor.calls, 1)

    def test_incompatible_checkpoint_metadata_is_a_reviewable_conflict(self):
        job_id, document, _ = self.record(partial=True)
        path = self.store.result_path(job_id)
        for simulator in ({"name": "AerSimulator", "device": "GPU"}, None):
            with self.subTest(simulator=simulator):
                document["environment"]["simulator"] = simulator
                path.write_text(json.dumps(document), encoding="utf-8")
                for suffix in ("", ".md", ".json"):
                    response = self.client.get(f"{JOBS}/{job_id}/relatorio{suffix}")
                    self.assertEqual(response.status_code, 409)
        self.assertEqual(self.advisor.calls, 0)

    def test_explicit_generation_persists_the_selected_order_and_downloads(self):
        job_id, document, raw = self.record()
        route = f"{JOBS}/{job_id}/relatorio"
        initial = self.client.get(route).json()
        response = self.client.post(route)
        self.assertEqual(response.status_code, 200, response.text[:500])
        selected = response.json()
        self.assertEqual(selected["origem_texto"], "modelo_local")
        self.assertEqual(selected["modelo_versao"], self.advisor.identity)
        self.assertEqual(selected["observacoes"], list(reversed(initial["observacoes"])))
        self.assertEqual(selected["fatos"], initial["fatos"])
        self.assertEqual(self.client.post(route).json(), selected)
        self.assertEqual(self.advisor.calls, 1)

        with TestClient(create_app(self.root), base_url=ORIGIN) as reopened:
            self.assertFalse(reopened.get("/api/v1/relator").json()["modelo_local"])
            self.assertEqual(reopened.get(route).json(), selected)
            json_file = reopened.get(route + ".json")
            md_file = reopened.get(route + ".md")
        for download, extension, mime in ((json_file, "json", "application/json"),
                                          (md_file, "md", "text/markdown")):
            self.assertEqual(download.status_code, 200)
            self.assertEqual(download.headers["content-disposition"],
                             f'attachment; filename="Radar-Quantum-Relatorio-{job_id}.{extension}"')
            self.assertEqual(download.headers["x-content-type-options"], "nosniff")
            self.assertEqual(download.headers["content-type"].split(";")[0], mime)
        self.assertEqual(json_file.json(), selected)
        for expected in (job_id, document["run_id"], sha256(raw).hexdigest(), self.advisor.model):
            self.assertIn(expected, md_file.text)
        for node in [selected["resumo"], *selected["limitacoes"], selected["proximo_teste"]]:
            self.assertIn(node["texto"], md_file.text)
        positions = [md_file.text.index(item["texto"]) for item in selected["observacoes"]]
        self.assertEqual(positions, sorted(positions))
        for fact in selected["fatos"]:
            self.assertIn(f"`{fact['id']}`", md_file.text)

    def test_result_swap_with_identical_settings_rejects_every_report_route(self):
        first, _, _ = self.record()
        second, second_doc, second_raw = self.record()
        first_route = f"{JOBS}/{first}/relatorio"
        self.assertEqual(self.client.post(first_route).status_code, 200)
        self.store.result_path(first).write_bytes(second_raw)
        for method, suffix in (("GET", ""), ("GET", ".json"), ("GET", ".md"), ("POST", "")):
            with self.subTest(method=method, suffix=suffix):
                self.assertEqual(self.client.request(method, first_route + suffix).status_code, 409)
        self.assertEqual(self.advisor.calls, 1)
        self.assertEqual(self.client.get(f"{JOBS}/{second}/relatorio").json()["run_id"], second_doc["run_id"])

    def test_partial_has_no_cross_condition_claim_and_cannot_call_model(self):
        job_id, _, raw = self.record(partial=True)
        route = f"{JOBS}/{job_id}/relatorio"
        response = self.client.get(route)
        self.assertEqual(response.status_code, 200)
        partial = response.json()
        self.assertEqual(partial["estado"], "parcial")
        self.assertEqual(partial["result_sha256"], sha256(raw).hexdigest())
        self.assertNotIn("variacao_taxa", {f["id"] for f in partial["fatos"]})
        self.assertFalse(any(node["frase_id"].startswith("variacao_taxa") for node in partial["observacoes"]))
        self.assertIsNone(partial["proximo_teste"])
        self.assertEqual(self.client.get(route + ".json").json(), partial)
        self.assertEqual(self.client.post(route).status_code, 409)
        self.assertEqual(self.advisor.calls, 0)

    def test_missing_queued_and_cross_origin_requests(self):
        complete, _, _ = self.record()
        queued = self.store.submit("queued", "bell", 77)["id"]
        for job_id, status in ((str(uuid4()), 404), (queued, 409)):
            for method, suffix in (("GET", ""), ("GET", ".json"), ("GET", ".md"), ("POST", "")):
                with self.subTest(job=job_id, method=method, suffix=suffix):
                    route = f"{JOBS}/{job_id}/relatorio{suffix}"
                    self.assertEqual(self.client.request(method, route).status_code, status)
        origin = {"Origin": "http://127.0.0.1:9999"}
        for method, suffix in (("GET", ".md"), ("GET", ".json"), ("POST", "")):
            response = self.client.request(method, f"{JOBS}/{complete}/relatorio{suffix}", headers=origin)
            self.assertEqual(response.status_code, 403)
        self.assertEqual(self.advisor.calls, 0)

    def test_model_timeout_preserves_the_scientific_zip(self):
        job_id, _, raw = self.record()
        self.advisor.mode = "timeout"
        response = self.client.post(f"{JOBS}/{job_id}/relatorio")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["origem_texto"], "deterministico")
        self.assertEqual(response.json()["fallback_reason"], "tempo_esgotado")
        zipped = self.client.get(f"{JOBS}/{job_id}/exportacao")
        self.assertEqual(zipped.status_code, 200)
        with ZipFile(BytesIO(zipped.content)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.read("result.json"), raw)

    def test_free_text_from_model_stays_out_of_all_outputs_and_saved_selection(self):
        job_id, _, _ = self.record()
        route = f"{JOBS}/{job_id}/relatorio"
        self.advisor.mode = "invalid"
        generated = self.client.post(route)
        self.assertEqual(generated.status_code, 200)
        self.assertEqual(generated.json()["origem_texto"], "deterministico")
        self.assertEqual(generated.json()["fallback_reason"], "proposta_invalida")
        for response in (generated, self.client.get(route), self.client.get(route + ".json"), self.client.get(route + ".md")):
            self.assertNotIn(CANARY, response.text)
        self.assertNotIn(CANARY, (self.root / "reports" / f"{job_id}.json").read_text())
        self.assertEqual(self.advisor.calls, 1)

    def test_foreign_or_tampered_saved_selection_falls_back_without_free_text(self):
        owner, owner_doc, owner_raw = self.record()
        other, other_doc, raw = self.record(run_id=owner_doc["run_id"])
        self.assertEqual(owner_raw, raw)
        self.assertEqual(self.client.post(f"{JOBS}/{owner}/relatorio").status_code, 200)
        records = self.root / "reports"
        valid_bytes = (records / f"{owner}.json").read_bytes()
        (records / f"{other}.json").write_bytes(valid_bytes)
        foreign = self.client.get(f"{JOBS}/{other}/relatorio").json()
        self.assertEqual(foreign["fallback_reason"], "registro_invalido")
        self.assertEqual(foreign["job_id"], other)
        self.assertEqual(foreign["run_id"], other_doc["run_id"])
        self.assertEqual(foreign["result_sha256"], sha256(raw).hexdigest())
        self.assertEqual(foreign["origem_texto"], "deterministico")

        for location in ("record", "proposal"):
            with self.subTest(location=location):
                stored = json.loads(valid_bytes)
                target = stored if location == "record" else stored["proposal"]["observacoes"][0]
                target["texto"] = CANARY
                (records / f"{owner}.json").write_text(json.dumps(stored))
                route = f"{JOBS}/{owner}/relatorio"
                report = self.client.get(route).json()
                self.assertEqual(report["fallback_reason"], "registro_invalido")
                self.assertEqual(report["origem_texto"], "deterministico")
                self.assertNotIn(CANARY, self.client.get(route + ".md").text)
        self.assertEqual(self.advisor.calls, 1)
