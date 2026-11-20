"""Pacote de revisão com arquivos aprovados, hashes e limites de distribuição."""

import argparse
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
from urllib.parse import unquote, urlsplit
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile, ZipInfo

from .licensing import validate_license


POLICY = "releases/public-files.json"
MANIFEST = "RELEASE-MANIFEST.json"
LEGACY_SCHEMA = "rqb-review-candidate/1"
SCHEMA = "rqb-review-candidate/2"
POLICY_SCHEMA = "rqb-public-files/1"
REQUIRED = {POLICY, "releases/dependencies.json", "THIRD_PARTY_NOTICES.md", "README.md"}
LICENSE_FILES = {"LICENSE", "NOTICE", "LICENSE-SCOPE.json"}
DEVELOPMENT_POLICY_FILE = "config/development-policy.json"
LEGACY_READINESS = {"status": "blocked", "reasons": ["licenca_propria_pendente"],
                    "scope": "revisao_tecnica_sem_autorizacao_de_redistribuicao"}
READINESS = {"status": "review_only", "reasons": ["aceites_humanos_pendentes"],
             "scope": "portfolio_cientifico_sem_validacao_comercial"}
DEVELOPMENT_POLICY = {"schema": "rqb-development-policy/1",
                      "buyer_validation": "deferred_by_owner", "integrations": "local_free_only",
                      "paid_execution": False}
MAX_FILE = 4 * 1024 * 1024
MAX_TOTAL = 24 * 1024 * 1024
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_REVISION = re.compile(r"[0-9a-f]{40}\Z")
_ASSET = re.compile(r"web/dist/_astro/[A-Za-z0-9_.-]+\.(?:js|css|woff2?)\Z")
_LICENSES = {"web/dist/licencas/Geist-OFL.txt", "web/dist/licencas/IBM-Plex-Mono-OFL.txt"}


def validate_development_policy(value):
    """Accept the authorized local-only policy with exact types, including bool."""
    if (type(value) is not dict or set(value) != set(DEVELOPMENT_POLICY)
            or any(type(value[key]) is not type(expected) or value[key] != expected
                   for key, expected in DEVELOPMENT_POLICY.items())):
        raise ValueError("A política exige integrações locais gratuitas e execução paga desativada.")
    return dict(value)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Campo JSON duplicado.")
        result[key] = value
    return result


def _json(raw):
    def invalid(_):
        raise ValueError("Valor JSON não finito.")
    return json.loads(raw, object_pairs_hook=_unique, parse_constant=invalid)


def _encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _path(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_./-]+", value):
        raise ValueError("Caminho de distribuição inválido.")
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value or any(part in (".", "..") for part in path.parts):
        raise ValueError("Caminho de distribuição inválido.")
    forbidden = {".git", ".env", "node_modules", "local-data", "__pycache__", "private", "secrets", "backups",
                 "reports", "results", "exports", "executions", "venv"}
    if any(part.lower() in forbidden or (part.startswith(".") and part not in (".github", ".gitignore"))
           for part in path.parts):
        raise ValueError(f"Caminho reservado na distribuição: {value}")
    if value.endswith((".map", ".pyc", ".sqlite", ".sqlite3", ".pem", ".key")):
        raise ValueError(f"Tipo reservado na distribuição: {value}")
    return value


def _read(root, name):
    name = _path(name)
    path = root / name
    for part in (path, *path.parents):
        if part == root:
            break
        if part.is_symlink():
            raise ValueError(f"Link simbólico na distribuição: {name}")
    if not path.is_file() or path.stat().st_size > MAX_FILE:
        raise ValueError(f"Arquivo ausente ou grande demais: {name}")
    return path.read_bytes()


def _policy(raw):
    policy = _json(raw)
    if not isinstance(policy, dict) or set(policy) != {"schema", "source_files", "web_files"}:
        raise ValueError("Lista de distribuição inválida.")
    if policy["schema"] != POLICY_SCHEMA:
        raise ValueError("Versão da lista desconhecida.")
    sources, web = policy["source_files"], policy["web_files"]
    if (type(sources) is not list or not sources or any(type(item) is not str for item in sources)
            or len(set(sources)) != len(sources) or not REQUIRED.issubset(sources)
            or type(web) is not dict or "web/dist/index.html" not in web or not _LICENSES.issubset(web)):
        raise ValueError("A lista não contém os arquivos obrigatórios.")
    for name in sources:
        _path(name)
        if name.startswith("web/dist/") or name == MANIFEST:
            raise ValueError("Arquivo de build na lista de fontes.")
    for name, digest in web.items():
        _path(name)
        if name not in {"web/dist/index.html", *_LICENSES} and not _ASSET.fullmatch(name):
            raise ValueError(f"Arquivo de navegador não aprovado: {name}")
        if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
            raise ValueError("Hash de build inválido.")
    return policy


class _References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets = set()

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in ("src", "href") and value and value.startswith("/_astro/"):
                self.assets.add("web/dist" + unquote(urlsplit(value).path))


def web_snapshot(root):
    """Revisar o conjunto alcançado pelo HTML e CSS antes de congelar seus hashes."""
    root = Path(root).resolve()
    dist = root / "web/dist"
    if dist.is_symlink() or not dist.is_dir():
        raise ValueError("Compile a interface antes de registrar seus arquivos.")
    actual = set()
    for path in dist.rglob("*"):
        if path.is_symlink():
            raise ValueError("Link simbólico no build da interface.")
        if path.is_file():
            actual.add(_path(path.relative_to(root).as_posix()))
    parser = _References()
    parser.feed(_read(root, "web/dist/index.html").decode("utf-8"))
    expected = {"web/dist/index.html", *_LICENSES, *parser.assets}
    for name in tuple(parser.assets):
        if not _ASSET.fullmatch(name):
            raise ValueError("Referência de build fora dos tipos aprovados.")
        data = _read(root, name)
        if name.endswith((".css", ".js")) and b"sourceMappingURL=" in data:
            raise ValueError("Mapa de código no build da interface.")
        if name.endswith(".css"):
            for url in re.findall(r"url\(\s*['\"]?([^)'\"\s]+)", data.decode("utf-8")):
                parsed = urlsplit(url)
                if parsed.scheme or parsed.netloc or not parsed.path.startswith("/_astro/"):
                    raise ValueError("Recurso CSS fora do build local aprovado.")
                asset = _path("web/dist" + unquote(parsed.path))
                if not _ASSET.fullmatch(asset) or not asset.endswith((".woff", ".woff2")):
                    raise ValueError("Recurso CSS não aprovado.")
                expected.add(asset)
    if actual != expected:
        extra = sorted(actual - expected)
        missing = sorted(expected - actual)
        raise ValueError(f"Conteúdo inesperado no build. Extras {extra}; ausentes {missing}.")
    return {name: sha256(_read(root, name)).hexdigest() for name in sorted(expected)}


def _scan(files, forbidden_markers):
    if len(forbidden_markers) > 32:
        raise ValueError("Número excessivo de marcadores.")
    markers = []
    for value in forbidden_markers:
        if not isinstance(value, str) or not 1 <= len(value) <= 256:
            raise ValueError("Marcador inválido.")
        markers.append(value.encode("utf-8"))
    for name, data in files.items():
        if any(marker in data for marker in markers):
            # Report only the path, never the marker or the private content.
            raise ValueError(f"Marcador reservado no arquivo: {name}")


def _bound_revision(root, revision, files):
    if not isinstance(revision, str) or not _REVISION.fullmatch(revision):
        raise ValueError("Informe o SHA completo da revisão Git.")
    for name, data in files.items():
        try:
            recorded = subprocess.run(
                ["git", "-C", str(root), "show", f"{revision}:{name}"],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            ).stdout
        except (OSError, subprocess.CalledProcessError) as exc:
            raise ValueError(f"Arquivo não encontrado na revisão Git: {name}") from exc
        if recorded != data:
            raise ValueError(f"Arquivo difere da revisão Git: {name}")


def build_release(root, output, revision, *, forbidden_markers=()):
    root, output = Path(root).resolve(), Path(output)
    policy = _policy(_read(root, POLICY))
    snapshot = web_snapshot(root)
    if snapshot != policy["web_files"]:
        raise ValueError("O build difere da lista revisada. Revise e registre o build novamente.")
    if not (LICENSE_FILES | {DEVELOPMENT_POLICY_FILE}).issubset(policy["source_files"]):
        raise ValueError("A candidata atual exige licença e política de desenvolvimento.")
    files = {name: _read(root, name) for name in policy["source_files"]}
    _bound_revision(root, revision, files)
    files.update({name: _read(root, name) for name in snapshot})
    if sum(map(len, files.values())) > MAX_TOTAL:
        raise ValueError("A distribuição ultrapassa o limite de tamanho.")
    _scan(files, forbidden_markers)
    inventory = _json(files["releases/dependencies.json"])
    if not isinstance(inventory, dict) or not inventory:
        raise ValueError("Inventário de dependências ausente.")
    license_record = validate_license(files)
    validate_development_policy(_json(files[DEVELOPMENT_POLICY_FILE]))
    if inventory.get("own_code_license") != "Apache-2.0":
        raise ValueError("O inventário não corresponde à licença do núcleo.")
    manifest = {
        "schema": SCHEMA, "profile": "review-candidate", "source_revision": revision,
        "source_revision_verified": True,
        "readiness": dict(READINESS), "license": license_record,
        "development_policy": dict(DEVELOPMENT_POLICY),
        "files": {name: {"sha256": sha256(data).hexdigest(), "bytes": len(data)}
                  for name, data in sorted(files.items())},
    }
    files[MANIFEST] = _encode(manifest)
    # Exclusive creation preserves a previous reviewed artifact.
    created = False
    try:
        with output.open("xb") as stream:
            created = True
            with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
                for name, data in sorted(files.items()):
                    info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                    info.compress_type = ZIP_DEFLATED
                    info.create_system = 3
                    info.external_attr = (stat.S_IFREG | 0o644) << 16
                    archive.writestr(info, data)
    except BaseException:
        if created:
            output.unlink(missing_ok=True)
        raise
    return manifest


def verify_release(path, *, expected_sha256=None, forbidden_markers=()):
    path = Path(path)
    if path.stat().st_size > MAX_TOTAL:
        raise ValueError("O arquivo ZIP excede o tamanho permitido.")
    if expected_sha256 is not None:
        if not isinstance(expected_sha256, str) or not _DIGEST.fullmatch(expected_sha256):
            raise ValueError("SHA-256 esperado inválido.")
        if sha256(path.read_bytes()).hexdigest() != expected_sha256:
            raise ValueError("O ZIP difere do SHA-256 esperado.")
    with ZipFile(path) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(names) > 512 or len(names) != len(set(names)) or MANIFEST not in names:
            raise ValueError("Membros ausentes ou duplicados no ZIP.")
        if sum(entry.file_size for entry in entries) > MAX_TOTAL + MAX_FILE:
            raise ValueError("O ZIP excede o tamanho permitido.")
        files = {}
        for entry in entries:
            _path(entry.filename)
            mode = entry.external_attr >> 16
            if (entry.is_dir() or stat.S_ISLNK(mode) or entry.flag_bits & 1
                    or stat.S_IFMT(mode) not in (0, stat.S_IFREG) or entry.file_size > MAX_FILE):
                raise ValueError("Membro não regular ou excessivo no ZIP.")
            files[entry.filename] = archive.read(entry)
    manifest = _json(files.pop(MANIFEST))
    base_keys = {"schema", "profile", "source_revision", "source_revision_verified", "readiness", "files"}
    if type(manifest) is not dict:
        raise ValueError("Manifesto inválido ou conteúdo inesperado.")
    current = manifest.get("schema") == SCHEMA
    expected_keys = base_keys | {"license", "development_policy"} if current else base_keys
    expected_readiness = READINESS if current else LEGACY_READINESS
    if (set(manifest) != expected_keys or manifest.get("schema") not in (LEGACY_SCHEMA, SCHEMA)
            or manifest["profile"] != "review-candidate" or manifest["source_revision_verified"] is not True
            or not isinstance(manifest["source_revision"], str)
            or not _REVISION.fullmatch(manifest["source_revision"])
            or manifest["readiness"] != expected_readiness
            or type(manifest["files"]) is not dict or set(manifest["files"]) != set(files)):
        raise ValueError("Manifesto inválido ou conteúdo inesperado.")
    if not REQUIRED.issubset(files):
        raise ValueError("Arquivos obrigatórios ausentes no ZIP.")
    policy = _policy(files[POLICY])
    if set(files) != set(policy["source_files"]) | set(policy["web_files"]):
        raise ValueError("O ZIP não corresponde à lista de distribuição.")
    for name, data in files.items():
        record = manifest["files"][name]
        digest = sha256(data).hexdigest()
        if (not isinstance(record, dict) or type(record.get("bytes")) is not int
                or record != {"sha256": digest, "bytes": len(data)}):
            raise ValueError(f"Arquivo divergente: {name}")
        if name in policy["web_files"] and policy["web_files"][name] != digest:
            raise ValueError(f"Build divergente: {name}")
    inventory = _json(files["releases/dependencies.json"])
    if not isinstance(inventory, dict) or not inventory:
        raise ValueError("Inventário inválido.")
    if current:
        if not (LICENSE_FILES | {DEVELOPMENT_POLICY_FILE}).issubset(files):
            raise ValueError("A candidata atual não contém licença e política.")
        validate_development_policy(manifest["development_policy"])
        validate_development_policy(_json(files[DEVELOPMENT_POLICY_FILE]))
        if (manifest["license"] != validate_license(files)
                or inventory.get("own_code_license") != "Apache-2.0"):
            raise ValueError("Licença ou política da candidata divergente.")
    _scan(files, forbidden_markers)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description="Revisar a distribuição do Radar Quantum Bench")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--revision", required=True)
    build.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    check = commands.add_parser("verify")
    check.add_argument("archive", type=Path)
    check.add_argument("--sha256")
    snapshot = commands.add_parser("snapshot-web", help="registrar explicitamente o build após sua revisão")
    snapshot.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    for command in (build, check):
        command.add_argument("--forbid-marker", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        if args.command == "snapshot-web":
            path = args.root / POLICY
            policy = _json(path.read_bytes())
            policy["web_files"] = web_snapshot(args.root)
            _policy(_encode(policy))
            path.write_bytes(_encode(policy))
            print("Build registrado para revisão. Confira o diff da lista antes de publicar o commit.")
        elif args.command == "build":
            manifest = build_release(args.root, args.output, args.revision, forbidden_markers=args.forbid_marker)
            print(json.dumps({"profile": manifest["profile"], "readiness": manifest["readiness"],
                              "sha256": sha256(args.output.read_bytes()).hexdigest()}, ensure_ascii=False))
        else:
            manifest = verify_release(args.archive, expected_sha256=args.sha256,
                                      forbidden_markers=args.forbid_marker)
            print(json.dumps({"integridade_interna": "conferida", "profile": manifest["profile"],
                              "sha256_externo_conferido": args.sha256 is not None,
                              "readiness": manifest["readiness"]}, ensure_ascii=False))
        return 0
    except (BadZipFile, ValueError, OSError, KeyError, TypeError) as exc:
        print(f"Candidata recusada: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
