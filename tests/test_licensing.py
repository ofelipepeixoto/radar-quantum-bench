"""Concessão do código próprio, exceções e escopo da distribuição pública."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import unittest

from radar_quantum_bench.licensing import LICENSE_SHA256, NOTICE_TEXT, SUPPORT_FILES, validate_license


ROOT = Path(__file__).resolve().parents[1]


class PublicLicenseTests(unittest.TestCase):
    def fixture(self):
        scope = {
            "schema": "rqb-license-scope/1", "own_license": "Apache-2.0",
            "scope": "public-core-existing-mvp-only", "own_files": ["example.py"],
            "generated_own_files": ["web/dist/index.html"],
            "legacy_archives": [{"path": "artifacts/old.zip", "sha256": sha256(b"old-science").hexdigest(),
                                 "scope": "project-owned-code-only"}],
            "third_party_files": ["web/dist/_astro/font.abc.woff2", "web/public/licencas/Geist-OFL.txt"],
            "license_support_files": sorted(SUPPORT_FILES),
        }
        files = {"LICENSE": (ROOT / "LICENSE").read_bytes(), "NOTICE": NOTICE_TEXT.encode(),
                 "THIRD_PARTY_NOTICES.md": b"Third-party notices retained.",
                 "example.py": b"VALUE = 1\n", "web/dist/index.html": b"<html></html>",
                 "web/dist/_astro/font.abc.woff2": b"font-software",
                 "web/public/licencas/Geist-OFL.txt": b"OFL notice",
                 "artifacts/old.zip": b"old-science"}
        return files, scope

    def payload(self, files, scope):
        result = deepcopy(files)
        result["LICENSE-SCOPE.json"] = json.dumps(scope).encode()
        return result

    def test_exact_official_license_scope_and_third_party_exceptions(self):
        files, scope = self.fixture()
        payload = self.payload(files, scope)
        result = validate_license(payload)
        self.assertEqual(result, {"spdx": "Apache-2.0", "license_sha256": LICENSE_SHA256,
            "notice_sha256": sha256(payload["NOTICE"]).hexdigest(),
            "scope_sha256": sha256(payload["LICENSE-SCOPE.json"]).hexdigest()})
        self.assertEqual(files["LICENSE"], (ROOT / "LICENSE").read_bytes())

    def test_missing_tampered_license_or_notice_is_rejected(self):
        files, scope = self.fixture()
        for name in ("LICENSE", "NOTICE", "LICENSE-SCOPE.json"):
            for mode in ("missing", "altered"):
                with self.subTest(name=name, mode=mode):
                    candidate = self.payload(files, scope)
                    if mode == "missing":
                        candidate.pop(name)
                    else:
                        candidate[name] += b" extra"
                    with self.assertRaises(ValueError):
                        validate_license(candidate)

    def test_unknown_source_private_path_and_duplicate_classification_fail(self):
        files, scope = self.fixture()
        candidate = self.payload(files, scope)
        candidate["commercial.py"] = b"private-business-rule"
        with self.assertRaises(ValueError):
            validate_license(candidate)
        for name in ("private/business.py", "local-data/customer.json", "../outside.py", "."):
            with self.subTest(name=name):
                changed = deepcopy(scope)
                changed["own_files"] = sorted(["example.py", name])
                candidate = self.payload({**files, name: b"not-public"}, changed)
                with self.assertRaises(ValueError):
                    validate_license(candidate)
        changed = deepcopy(scope)
        changed["own_files"].append("NOTICE")
        changed["own_files"].sort()
        with self.assertRaises(ValueError):
            validate_license(self.payload(files, changed))

    def test_fonts_cannot_be_relicensed_as_project_owned_code(self):
        files, scope = self.fixture()
        changed = deepcopy(scope)
        path = changed["third_party_files"].pop(0)
        changed["own_files"] = sorted(changed["own_files"] + [path])
        with self.assertRaises(ValueError):
            validate_license(self.payload(files, changed))

    def test_legacy_archive_bytes_and_scope_must_be_preserved(self):
        files, scope = self.fixture()
        for change in ("hash", "scope", "bytes"):
            with self.subTest(change=change):
                changed, copies = deepcopy(scope), deepcopy(files)
                if change == "hash":
                    changed["legacy_archives"][0]["sha256"] = "0" * 64
                elif change == "scope":
                    changed["legacy_archives"][0]["scope"] = "all-third-party-code-too"
                else:
                    copies["artifacts/old.zip"] = b"rewritten"
                with self.assertRaises(ValueError):
                    validate_license(self.payload(copies, changed))

    def test_unknown_fields_duplicates_and_future_wildcards_are_rejected(self):
        files, scope = self.fixture()
        for key, value in (("future_private_license", "Apache-2.0"), ("own_files", ["example.py", "example.py"]),
                           ("scope", "everything-in-this-and-future-repositories")):
            changed = deepcopy(scope)
            changed[key] = value
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    validate_license(self.payload(files, changed))
        candidate = self.payload(files, scope)
        raw = candidate["LICENSE-SCOPE.json"]
        candidate["LICENSE-SCOPE.json"] = raw[:-1] + b',"own_license":"Apache-2.0"}'
        with self.assertRaises(ValueError):
            validate_license(candidate)


if __name__ == "__main__":
    unittest.main()
