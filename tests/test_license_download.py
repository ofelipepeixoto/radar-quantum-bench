"""Avisos separados preservam a cápsula científica e não incluem dados locais."""

from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from fastapi.testclient import TestClient
from radar_quantum_bench.api import create_app
from radar_quantum_bench.licensing import SUPPORT_FILES, notice_files, write_notice_bundle


class LicenseDownloadTests(unittest.TestCase):
    def test_download_contains_exact_public_sidecars_and_matching_hashes(self):
        with TemporaryDirectory() as folder, TestClient(create_app(Path(folder)), base_url="http://127.0.0.1:8000") as client:
            metadata = client.get("/api/v1/licencas")
            response = client.get("/api/v1/licencas.zip")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(metadata.json()["license"], "Apache-2.0")
        self.assertEqual(response.headers["content-disposition"], 'attachment; filename="Radar-Quantum-Bench-LICENCAS.zip"')
        with ZipFile(BytesIO(response.content)) as archive:
            self.assertEqual(set(archive.namelist()), set(SUPPORT_FILES))
            for name in SUPPORT_FILES:
                self.assertEqual(sha256(archive.read(name)).hexdigest(), metadata.json()["files"][name])
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")

    def test_notice_download_respects_the_same_origin_boundary(self):
        with TemporaryDirectory() as folder, TestClient(create_app(Path(folder)), base_url="http://127.0.0.1:8000") as client:
            self.assertEqual(client.get("/api/v1/licencas.zip", headers={"Origin": "https://foreign.invalid"}).status_code, 403)

    def test_companion_does_not_overwrite_and_rejects_missing_notices(self):
        root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as folder:
            output = Path(folder) / "notices.zip"
            output.write_bytes(b"preservar")
            with self.assertRaises(FileExistsError):
                write_notice_bundle(notice_files(root), output)
            self.assertEqual(output.read_bytes(), b"preservar")
            with self.assertRaises(ValueError):
                notice_files(Path(folder))


if __name__ == "__main__":
    unittest.main()
