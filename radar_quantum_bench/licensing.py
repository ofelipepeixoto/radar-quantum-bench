"""Conferir a licença e a classificação explícita da distribuição pública."""

from hashlib import sha256
import json
from pathlib import PurePosixPath
import re
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED


LICENSE_SHA256 = "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"
SCHEMA = "rqb-license-scope/1"
SUPPORT_FILES = ("LICENSE", "NOTICE", "LICENSE-SCOPE.json", "THIRD_PARTY_NOTICES.md")
_FIELDS = {"schema", "own_license", "scope", "own_files", "generated_own_files",
           "legacy_archives", "third_party_files", "license_support_files"}
NOTICE_TEXT = """Radar Quantum Bench
Public scientific core and portfolio edition
Copyright 2026 Carlos Felipe (@ofelipepeixoto)

Project-owned code, documentation, examples and project-owned portions of
generated interface files identified in LICENSE-SCOPE.json are offered under the
Apache License, Version 2.0. A copy accompanies this distribution in LICENSE.

The unchanged historical scientific archives identified in LICENSE-SCOPE.json
retain their original bytes and scientific manifests. This accompanying
license and notice apply to the project-owned code inside those archives.
Recipients who redistribute that code must preserve the applicable license
and notices. Third-party components retain their own terms.

Font software and its original notices remain under the licenses identified
in THIRD_PARTY_NOTICES.md. Dependency metadata references external packages
and does not relicense those packages.

This public distribution does not include separately developed commercial
components, laboratory data or credentials. Its license does not grant
rights to components absent from the classified public distribution.
"""


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Campo de licença duplicado.")
        result[key] = value
    return result


def _path(value):
    if type(value) is not str or not value or "\\" in value or "\x00" in value:
        raise ValueError("Caminho de licença inválido.")
    path = PurePosixPath(value)
    if (not path.parts or path.is_absolute() or str(path) != value
            or any(part in (".", "..") for part in path.parts)):
        raise ValueError("Caminho de licença inválido.")
    forbidden = {".git", ".env", "node_modules", "local-data", "private", "secrets", "backups"}
    if any(part.lower() in forbidden or part.lower().startswith(".env.") for part in path.parts):
        raise ValueError("Material reservado no escopo público.")
    return value


def _paths(value):
    if type(value) is not list or any(type(item) is not str for item in value):
        raise ValueError("Lista de licença inválida.")
    if value != sorted(set(value)):
        raise ValueError("Lista de licença repetida ou fora de ordem.")
    return {_path(item) for item in value}


def _third_party_path(name):
    return bool(re.fullmatch(r"web/(?:public|dist)/licencas/[A-Za-z0-9_.-]+\.txt", name)
                or re.fullmatch(r"web/dist/_astro/[A-Za-z0-9_.-]+\.woff2?", name))


def validate_license(files):
    """Return the own-code license metadata only after complete classification.

    ``files`` is the actual payload before RELEASE-MANIFEST.json is added.
    This check records the project's grant and preserves third-party exceptions;
    it does not turn technical review into a human or commercial pilot approval.
    """
    if type(files) is not dict or any(type(name) is not str or type(data) is not bytes
                                      for name, data in files.items()):
        raise ValueError("Conteúdo de licença incompatível.")
    try:
        license_raw, notice_raw, scope_raw = (files[name] for name in SUPPORT_FILES[:3])
    except KeyError as exc:
        raise ValueError("Licença, aviso ou escopo ausente.") from exc
    if sha256(license_raw).hexdigest() != LICENSE_SHA256:
        raise ValueError("O texto da Apache 2.0 difere do texto oficial aprovado.")
    if notice_raw != NOTICE_TEXT.encode("utf-8"):
        raise ValueError("O aviso do núcleo público requer revisão.")
    try:
        scope = json.loads(scope_raw, object_pairs_hook=_unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Número inválido.")))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Escopo de licença inválido.") from exc
    if (type(scope) is not dict or set(scope) != _FIELDS or scope["schema"] != SCHEMA
            or scope["own_license"] != "Apache-2.0"
            or scope["scope"] != "public-core-existing-mvp-only"):
        raise ValueError("Contrato do escopo público incompatível.")
    classes = [_paths(scope[key]) for key in
               ("own_files", "generated_own_files", "third_party_files", "license_support_files")]
    if classes[-1] != set(SUPPORT_FILES) or not classes[0]:
        raise ValueError("Os avisos ou o núcleo próprio estão ausentes.")
    if any(name.startswith("web/dist/") or name.endswith(".zip") or _third_party_path(name)
           or name in SUPPORT_FILES for name in classes[0]):
        raise ValueError("Um componente foi classificado como fonte própria indevidamente.")
    for name in classes[1]:
        if not (name == "web/dist/index.html" or re.fullmatch(
                r"web/dist/_astro/[A-Za-z0-9_.-]+\.(?:js|css)", name)):
            raise ValueError("Arquivo gerado próprio fora do escopo aprovado.")
    for name in classes[2]:
        if not _third_party_path(name):
            raise ValueError("Exceção de terceiro fora dos caminhos aprovados.")
    if any(_third_party_path(name) and name not in classes[2] for name in files):
        raise ValueError("Uma fonte ou aviso de terceiro perdeu sua exceção de licença.")
    archives = scope["legacy_archives"]
    if type(archives) is not list:
        raise ValueError("Lista de cápsulas inválida.")
    archive_paths = set()
    for row in archives:
        if (type(row) is not dict or set(row) != {"path", "sha256", "scope"}
                or row["scope"] != "project-owned-code-only"
                or type(row["sha256"]) is not str or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])):
            raise ValueError("Escopo de cápsula inválido.")
        name = _path(row["path"])
        if not name.startswith("artifacts/") or not name.endswith(".zip") or name in archive_paths:
            raise ValueError("Cápsula fora do escopo ou repetida.")
        if name not in files or sha256(files[name]).hexdigest() != row["sha256"]:
            raise ValueError("Uma cápsula histórica difere dos bytes aprovados.")
        archive_paths.add(name)
    classes.append(archive_paths)
    covered = set()
    for names in classes:
        if covered.intersection(names):
            raise ValueError("Um arquivo possui classificações de licença conflitantes.")
        covered.update(names)
    if covered != set(files):
        raise ValueError("O pacote contém arquivos sem classificação ou falta um arquivo do escopo.")
    return {"spdx": "Apache-2.0", "license_sha256": LICENSE_SHA256,
            "notice_sha256": sha256(notice_raw).hexdigest(), "scope_sha256": sha256(scope_raw).hexdigest()}


def notice_files(root):
    """Read only the public sidecars that accompany scientific capsules."""
    files = {}
    for name in SUPPORT_FILES:
        path = root / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
            raise ValueError("Avisos públicos ausentes ou incompatíveis.")
        files[name] = path.read_bytes()
    if (sha256(files["LICENSE"]).hexdigest() != LICENSE_SHA256
            or files["NOTICE"] != NOTICE_TEXT.encode("utf-8")):
        raise ValueError("Licença ou atribuição pública requer revisão.")
    scope = json.loads(files["LICENSE-SCOPE.json"], object_pairs_hook=_unique)
    if (type(scope) is not dict or scope.get("schema") != SCHEMA
            or scope.get("own_license") != "Apache-2.0"):
        raise ValueError("Escopo público incompatível.")
    return files


def write_notice_bundle(files, output):
    """Write a separate notice ZIP, preserving the scientific ZIP format."""
    if set(files) != set(SUPPORT_FILES):
        raise ValueError("Lista de avisos incompatível.")
    created = False
    try:
        with output.open("xb") as stream:
            created = True
            with ZipFile(stream, "w") as archive:
                for name, data in sorted(files.items()):
                    info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                    info.compress_type = ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, data)
    except BaseException:
        if created:
            output.unlink(missing_ok=True)
        raise
