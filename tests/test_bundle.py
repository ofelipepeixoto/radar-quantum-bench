import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import warnings
from zipfile import ZipFile

from radar_quantum_bench import bundle


class BellPackageTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name).resolve()
        self.source = self.folder / "checkout"
        self.result = self.folder / "bell.json"
        self.archive = self.folder / "bell.zip"
        for name in bundle._SHIPPED:
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {name}\n", encoding="utf-8")
        (self.source / ".env").write_text("test marker\n", encoding="utf-8")
        (self.source / "tests" / "extra.py").write_text("test marker\n", encoding="utf-8")
        self.enterContext(patch.object(bundle, "_ROOT", self.source))
        # The experiment validator has its own scientific and CLI integration tests.
        self.validator = self.enterContext(patch("radar_quantum_bench.experiment.validate"))
        self.document = {
            "summary": {"complete": True},
            "config": {"base_seed": 215},
            "environment": {
                "logical_qasm": "OPENQASM 3.0; // logical\n",
                "compiled_qasm": "OPENQASM 3.0; // compiled\n",
            },
            "source_sha256": {
                name: hashlib.sha256((self.source / name).read_bytes()).hexdigest()
                for name in bundle._SOURCES
            },
        }
        self.write_result()

    def write_result(self):
        self.result.write_text(json.dumps(self.document), encoding="utf-8")

    def test_complete_reproducible_package_contains_only_known_files(self):
        bundle.build_bundle(self.result, self.archive)
        bundle.check_bundle(self.archive)
        self.assertEqual(self.validator.call_count, 2)
        with ZipFile(self.archive) as archive:
            self.assertEqual(set(archive.namelist()), bundle._FILES | {"manifest.json"})
            self.assertEqual(archive.read("bell.json"), self.result.read_bytes())
            self.assertNotIn(".env", archive.namelist())
            self.assertNotIn("tests/extra.py", archive.namelist())
            self.assertIn(b"--seed 215", archive.read("REPRODUZIR.md"))
            self.assertEqual(archive.read("logical.qasm").decode(),
                             self.document["environment"]["logical_qasm"])
        copy = self.folder / "copy.zip"
        bundle.build_bundle(self.result, copy)
        self.assertEqual(self.archive.read_bytes(), copy.read_bytes())

    def test_refuses_overwrite_without_partial_file(self):
        self.archive.write_bytes(b"existing archive")
        with self.assertRaises(FileExistsError):
            bundle.build_bundle(self.result, self.archive)
        self.assertEqual(self.archive.read_bytes(), b"existing archive")
        self.assertEqual(list(self.folder.glob(".bell-*")), [])

    def test_incomplete_invalid_or_modified_sources_cannot_be_published(self):
        self.document["summary"]["complete"] = False
        self.write_result()
        with self.assertRaises(ValueError):
            bundle.build_bundle(self.result, self.archive)
        self.document["summary"]["complete"] = True
        self.write_result()
        (self.source / "requirements.txt").write_text("changed dependency\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            bundle.build_bundle(self.result, self.archive)
        self.validator.side_effect = ValueError("invalid data")
        with self.assertRaisesRegex(ValueError, "invalid data"):
            bundle.build_bundle(self.result, self.archive)
        self.assertFalse(self.archive.exists())

    def test_symbolic_link_in_allowlist_never_published(self):
        path = self.source / "tests" / "test_cli.py"
        path.unlink()
        path.symlink_to(self.source / ".env")
        with self.assertRaises(ValueError):
            bundle.build_bundle(self.result, self.archive)
        self.assertFalse(self.archive.exists())

    def test_archive_rejects_extra_missing_duplicate_corrupt_and_mismatched_data(self):
        bundle.build_bundle(self.result, self.archive)
        with ZipFile(self.archive) as archive:
            baseline = {name: archive.read(name) for name in archive.namelist()}
        for change in ("extra", "missing", "duplicate", "edited-json", "rehashed-qasm",
                       "rehashed-source", "corrupt"):
            with self.subTest(change=change):
                entries = baseline.copy()
                if change == "extra":
                    entries[f"../{self.folder.name}/extra"] = b"must not extract"
                elif change == "missing":
                    del entries["compiled.qasm"]
                elif change == "edited-json":
                    entries["bell.json"] += b"\n"
                elif change in ("rehashed-qasm", "rehashed-source"):
                    name = "logical.qasm" if change == "rehashed-qasm" else "requirements.txt"
                    entries[name] = b"edited"
                    manifest = json.loads(entries["manifest.json"])
                    manifest["sha256"][name] = hashlib.sha256(entries[name]).hexdigest()
                    entries["manifest.json"] = json.dumps(manifest).encode()
                candidate = self.folder / f"{change}.zip"
                with ZipFile(candidate, "w") as archive:
                    for name, data in entries.items():
                        archive.writestr(name, data)
                    if change == "duplicate":
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore", UserWarning)
                            archive.writestr("bell.json", entries["bell.json"])
                if change == "corrupt":
                    candidate.write_bytes(b"not a zip")
                with self.assertRaises(ValueError):
                    bundle.check_bundle(candidate)
                self.assertFalse((self.folder / "extra").exists())
