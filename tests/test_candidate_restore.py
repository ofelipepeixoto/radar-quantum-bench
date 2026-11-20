"""Cópia com processos encerrados preserva o experimento e a seleção do relator."""

from hashlib import sha256
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from radar_quantum_bench.api import create_app


ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "http://127.0.0.1:8000"


class LocalAdvisor:
    """Dublê explícito para uma seleção que precisa sobreviver à restauração."""

    model = "restore-test:latest"
    identity = {"name": model, "digest": "a" * 64, "server_version": "1.0.0"}

    def propose(self, facts):
        proposal = facts["proposta_base"]
        proposal["observacoes"].reverse()
        return proposal


class CandidateRestoreTests(unittest.TestCase):
    def test_a_copied_installation_reopens_data_and_report_without_the_source(self):
        with TemporaryDirectory() as folder:
            base = Path(folder)
            original, restored = base / "original", base / "restored"
            app = create_app(original, advisor=LocalAdvisor())
            store = app.state.store
            raw = (ROOT / "examples/catalogo/bell.json").read_bytes()
            document = json.loads(raw)
            job = store.submit(str(uuid4()), "bell", document["config"]["base_seed"])
            claimed = store.claim()
            store.result_path(job["id"]).write_bytes(raw)
            store.finish(job["id"], claimed["attempt_id"], True, result_sha256=sha256(raw).hexdigest())
            route = f"/api/v1/comparacoes/{job['id']}"
            with TestClient(app, base_url=ORIGIN) as client:
                self.assertEqual(client.post(route + "/relatorio").status_code, 200)
                expected_job = client.get(route).json()
                expected_report = client.get(route + "/relatorio").json()
                expected_metrics = client.get(route + "/metricas").json()
                expected_zip = client.get(route + "/exportacao").content
            # The copy is made only after all writers and HTTP clients stop.
            shutil.copytree(original, restored)
            shutil.rmtree(original)
            with TestClient(create_app(restored), base_url=ORIGIN) as reopened:
                self.assertEqual(reopened.get(route).json(), expected_job)
                self.assertEqual(reopened.get(route + "/metricas").json(), expected_metrics)
                report = reopened.get(route + "/relatorio").json()
                self.assertEqual(report, expected_report)
                self.assertEqual(report["origem_texto"], "modelo_local")
                self.assertEqual(report["run_id"], document["run_id"])
                self.assertEqual(reopened.get(route + "/relatorio.json").json(), report)
                markdown = reopened.get(route + "/relatorio.md").text
                self.assertIn(report["result_sha256"], markdown)
                self.assertEqual(reopened.get(route + "/exportacao").content, expected_zip)
                path = restored / "results" / f"{job['id']}.json"
                changed = json.loads(path.read_bytes())
                changed["environment"]["hardware"]["cpu"] = "ficticio-adulterado"
                path.write_text(json.dumps(changed), encoding="utf-8")
                for suffix in ("", "/metricas", "/relatorio", "/relatorio.json", "/relatorio.md", "/exportacao"):
                    self.assertEqual(reopened.get(route + suffix).status_code, 409)


if __name__ == "__main__":
    unittest.main()
