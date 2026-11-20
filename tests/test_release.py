"""Distribuição de revisão com build aprovado, commit e marcadores fictícios."""

from hashlib import sha256
import json
from pathlib import Path
import stat
import subprocess
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4
import warnings
from zipfile import ZipFile, ZipInfo

from radar_quantum_bench.release import (
    MANIFEST, POLICY, POLICY_SCHEMA, build_release, verify_release, web_snapshot,
)


class ReviewReleaseTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.archive = self.root.parent / ("rqb-review-" + uuid4().hex + ".zip")
        self.addCleanup(self.archive.unlink, missing_ok=True)
        self.files = {
            "README.md": "Candidata fictícia para revisão.\n",
            "app.py": "VALUE = 1\n",
            "THIRD_PARTY_NOTICES.md": "Inventário fictício.\n",
            "releases/dependencies.json": json.dumps({"schema": "fixture/1", "components": []}),
            "web/dist/index.html": '<html><head><link href="/_astro/index.abc.css" rel="stylesheet"></head>'
                                   '<body><script src="/_astro/app.def.js"></script></body></html>',
            "web/dist/_astro/index.abc.css": '@font-face{src:url(/_astro/font.ghi.woff2)}',
            "web/dist/_astro/font.ghi.woff2": "font-fixture",
            "web/dist/_astro/app.def.js": "console.log('fixture');",
            "web/dist/licencas/Geist-OFL.txt": "OFL fixture",
            "web/dist/licencas/IBM-Plex-Mono-OFL.txt": "OFL fixture",
        }
        for name, value in self.files.items():
            self.write(name, value)
        self.sources = ["README.md", "app.py", "THIRD_PARTY_NOTICES.md",
                        "releases/dependencies.json", POLICY]
        self.refresh_policy()
        self.git("init", "--quiet")
        self.commit()

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()

    def refresh_policy(self):
        self.write(POLICY, json.dumps({"schema": POLICY_SCHEMA, "source_files": self.sources,
                                     "web_files": web_snapshot(self.root)}))

    def commit(self):
        self.git("add", *self.sources)
        self.git("-c", "user.name=Teste", "-c", "user.email=fixture@example.invalid",
                 "commit", "--quiet", "-m", "fixture")
        self.revision = self.git("rev-parse", "HEAD")

    def build(self, **kwargs):
        return build_release(self.root, self.archive, self.revision, **kwargs)

    def rewrite(self, change):
        with ZipFile(self.archive) as archive:
            values = {name: archive.read(name) for name in archive.namelist()}
        change(values)
        with ZipFile(self.archive, "w") as archive:
            for name, value in values.items():
                archive.writestr(name, value)

    def test_reproducible_review_archive_records_commit_and_preserves_previous_file(self):
        expected = self.build()
        digest = sha256(self.archive.read_bytes()).hexdigest()
        self.assertEqual(verify_release(self.archive, expected_sha256=digest), expected)
        self.assertEqual(expected["profile"], "review-candidate")
        self.assertEqual(expected["readiness"]["status"], "blocked")
        self.assertEqual(expected["readiness"]["reasons"], ["licenca_propria_pendente"])
        self.assertEqual(expected["source_revision"], self.revision)
        second = self.root.parent / (uuid4().hex + ".zip")
        self.addCleanup(second.unlink, missing_ok=True)
        build_release(self.root, second, self.revision)
        self.assertEqual(second.read_bytes(), self.archive.read_bytes())
        with self.assertRaises(FileExistsError):
            self.build()
        with self.assertRaisesRegex(ValueError, "SHA-256 esperado"):
            verify_release(self.archive, expected_sha256="f" * 64)

    def test_excluded_lab_data_never_enters_candidate(self):
        marker = uuid4().hex
        self.write("local-data/laboratorio.json", marker)
        self.build(forbidden_markers=[marker])
        with ZipFile(self.archive) as archive:
            self.assertNotIn("local-data/laboratorio.json", archive.namelist())
            self.assertFalse(any(marker.encode() in archive.read(name) for name in archive.namelist()))

    def test_unexpected_build_file_is_a_blocking_error_even_with_javascript_extension(self):
        self.write("web/dist/_astro/extra.abc.js", uuid4().hex)
        with self.assertRaisesRegex(ValueError, "Extras"):
            self.build()
        self.assertFalse(self.archive.exists())

    def test_altered_approved_javascript_or_dirty_source_cannot_be_misattributed(self):
        self.write("web/dist/_astro/app.def.js", "altered build")
        with self.assertRaisesRegex(ValueError, "build difere"):
            self.build()
        self.write("web/dist/_astro/app.def.js", self.files["web/dist/_astro/app.def.js"])
        self.write("app.py", "VALUE = 2\n")
        with self.assertRaisesRegex(ValueError, "revisão Git"):
            self.build()
        self.assertFalse(self.archive.exists())

    def test_declared_marker_blocks_a_committed_candidate_and_reports_only_the_path(self):
        marker = "fixture-" + uuid4().hex
        self.write("web/dist/_astro/app.def.js", "console.log('" + marker + "');")
        self.refresh_policy()
        self.commit()
        with self.assertRaises(ValueError) as caught:
            self.build(forbidden_markers=[marker])
        self.assertIn("web/dist/_astro/app.def.js", str(caught.exception))
        self.assertNotIn(marker, str(caught.exception))
        self.assertFalse(self.archive.exists())

    def test_source_symlink_and_build_sourcemap_are_refused(self):
        (self.root / "app.py").unlink()
        (self.root / "app.py").symlink_to(self.root / "README.md")
        with self.assertRaisesRegex(ValueError, "Link simbólico"):
            self.build()
        (self.root / "app.py").unlink()
        self.write("app.py", self.files["app.py"])
        self.write("web/dist/_astro/app.def.js", "//# sourceMappingURL=data:private")
        with self.assertRaisesRegex(ValueError, "Mapa de código"):
            self.build()

    def test_verifier_rejects_missing_extra_changed_duplicate_and_symlink_members(self):
        changes = (
            lambda files: files.pop("app.py"),
            lambda files: files.update({"unknown.txt": b"extra"}),
            lambda files: files.update({"app.py": b"altered"}),
            lambda files: files.update({"../private.txt": b"extra"}),
        )
        for change in changes:
            with self.subTest(change=change):
                self.build()
                self.rewrite(change)
                with self.assertRaises(ValueError):
                    verify_release(self.archive)
                self.archive.unlink()
        self.build()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with ZipFile(self.archive, "a") as archive:
                archive.writestr("app.py", "duplicate")
        with self.assertRaisesRegex(ValueError, "duplicados"):
            verify_release(self.archive)
        self.archive.unlink()
        self.build()
        with ZipFile(self.archive, "a") as archive:
            info = ZipInfo("link")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, "app.py")
        with self.assertRaisesRegex(ValueError, "não regular"):
            verify_release(self.archive)

    def test_policy_cannot_add_reserved_files_and_verifier_checks_markers_too(self):
        self.build()
        with self.assertRaisesRegex(ValueError, "Marcador reservado"):
            verify_release(self.archive, forbidden_markers=["VALUE = 1"])
        self.archive.unlink()
        policy = json.loads((self.root / POLICY).read_text())
        policy["source_files"].append("local-data/laboratorio.json")
        self.write(POLICY, json.dumps(policy))
        with self.assertRaisesRegex(ValueError, "Caminho reservado"):
            self.build()


if __name__ == "__main__":
    unittest.main()
