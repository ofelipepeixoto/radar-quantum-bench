import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from radar_quantum_bench.api import create_app


class FrontendHostTests(unittest.TestCase):
    def setUp(self):
        temporary = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(temporary)
        self.dist = self.root / "web" / "dist"
        self.dist.mkdir(parents=True)

    def client(self, with_build=True):
        if with_build:
            (self.dist / "index.html").write_text("<title>Laboratório</title>", encoding="utf-8")
            assets = self.dist / "_astro"
            assets.mkdir()
            (assets / "main.js").write_text("export {};", encoding="utf-8")
        app = create_app(self.root / "data", ui_dir=self.dist)
        return self.enterContext(TestClient(app, base_url="http://127.0.0.1:8000"))

    def test_index_asset_api_and_health_share_headers_and_origin(self):
        client = self.client()
        for path in ["/", "/_astro/main.js", "/api/v1/experimentos", "/health"]:
            with self.subTest(path=path):
                response = client.get(path, headers={"Origin": "http://127.0.0.1:8000"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
                self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
                policy = {p.strip() for p in response.headers["Content-Security-Policy"].split(";")}
                self.assertEqual(policy, {
                    "default-src 'self'", "script-src 'self'", "style-src 'self' 'unsafe-inline'",
                    "font-src 'self'", "img-src 'self' data:", "connect-src 'self'",
                    "object-src 'none'", "base-uri 'none'", "frame-ancestors 'none'",
                })
        self.assertIn("Laboratório", client.get("/").text)
        self.assertEqual(client.get("/_astro/main.js").text, "export {};")
        self.assertEqual({item["id"] for item in client.get("/api/v1/experimentos").json()},
                         {"bell", "ghz", "bv"})

    def test_static_content_rejects_foreign_host_and_origin(self):
        client = self.client()
        self.assertEqual(client.get("/", headers={"Host": "untrusted.invalid"}).status_code, 400)
        response = client.get("/_astro/main.js", headers={"Origin": "https://other.invalid"})
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)

    def test_only_the_built_directory_is_public(self):
        source = self.root / "web" / "src" / "private.txt"
        source.parent.mkdir()
        source.write_text("fixture", encoding="utf-8")
        (self.dist / "outside.txt").symlink_to(source)
        client = self.client()
        for path in ["/src/private.txt", "/web/src/private.txt", "/outside.txt", "/missing"]:
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 404)

    def test_missing_build_explains_recovery_and_keeps_api_available(self):
        client = self.client(with_build=False)
        response = client.get("/")
        self.assertEqual(response.status_code, 503)
        for command in ["npm ci", "npm run build"]:
            self.assertIn(command, response.json()["detail"])
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(client.get("/health").json()["status"], "ok")
        self.assertEqual(client.get("/api/v1/comparacoes").json(), [])
