"""Portable Bell evidence packages. Inspection never extracts or imports ZIP contents."""

from hashlib import sha256
import json
import os
from pathlib import Path
import stat
from tempfile import NamedTemporaryFile
from zipfile import BadZipFile, ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo
import zlib

from .experiment import SOURCE_PATHS

from . import experiment


_ROOT = Path(__file__).resolve().parents[1]
_TESTS = ("test_cli", "test_metrics", "test_bundle", "test_resume")
_SOURCES = experiment.SOURCE_PATHS
_SHIPPED = _SOURCES + tuple(f"tests/{name}.py" for name in _TESTS)
_FILES = {*_SHIPPED, "bell.json", "logical.qasm", "compiled.qasm", "REPRODUZIR.md"}
_FORMAT = "radar-quantum-bench/bell-package-v1"
_MAX_MEMBER = 16 * 1024 * 1024
_MAX_TOTAL = 24 * 1024 * 1024


def _digest(content: bytes) -> str:
    return sha256(content).hexdigest()


def _unique_fields(pairs):
    fields = {}
    for name, value in pairs:
        if name in fields:
            raise ValueError(f"Campo JSON duplicado: {name!r}")
        fields[name] = value
    return fields


def _json(data: bytes) -> dict:
    result = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_fields)
    if not isinstance(result, dict):
        raise ValueError("O documento JSON deve ser um objeto.")
    return result


def _load_source(name: str) -> bytes:
    source = _ROOT / name
    if source.resolve() != source or not source.is_file():
        raise ValueError(f"Arquivo do pacote ausente ou de origem inesperada: {name}")
    return _read_limited(source)


def _read_limited(path: Path) -> bytes:
    with path.open("rb") as stream:
        content = stream.read(_MAX_MEMBER + 1)
    if len(content) > _MAX_MEMBER:
        raise ValueError(f"Arquivo excede o limite do pacote: {path.name}")
    return content


def _complete_result(raw: bytes) -> dict:
    document = _json(raw)
    experiment.validate(document)
    if document["summary"]["complete"] is not True:
        raise ValueError("O pacote de reprodução requer um experimento completo.")
    return document


def _check_sources(document: dict, entries: dict[str, bytes]) -> None:
    expected = {name: _digest(entries[name]) for name in _SOURCES}
    if document.get("source_sha256") != expected:
        raise ValueError("Os arquivos de implementação ou as dependências divergem da execução.")


def _guide(seed: int) -> bytes:
    return f"""# Reproduzir o experimento Bell

Este pacote inclui as contagens, os circuitos OpenQASM e a revisão do programa
usada no ensaio. Os tempos registrados em `bell.json` pertencem à máquina de
origem e variam com a carga e o equipamento.

No Linux x86_64 ou WSL2 x86_64 com Python 3.12, use uma cópia de confiança do Radar Quantum
Bench para conferir o ZIP antes de extraí-lo.

```bash
python3.12 -m radar_quantum_bench check-package caminho/para/pacote.zip
```

Os hashes permitem detectar inconsistências entre os arquivos. Para comprovar
a procedência, compare o SHA-256 do ZIP com um valor recebido por outro canal.

Extraia o pacote em uma pasta nova, abra o terminal nela e confira as métricas.

```bash
python3.12 -m radar_quantum_bench verify bell.json
```

Para repetir as medições, instale as dependências fixadas e use a semente
registrada neste pacote.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m radar_quantum_bench run --seed {seed} --output replay.json
python -m radar_quantum_bench verify replay.json
python -m unittest discover -s tests
```

Confira as contagens por condição, os parâmetros, o mapa de bits e as versões
do ambiente em ambos os arquivos. As comparações científicas devem usar os
dados por repetição e preservar as diferenças de ambiente observadas.
""".encode("utf-8")


def build_bundle(result_path: Path, destination: Path) -> None:
    """Publish a complete package atomically without replacing an existing path."""
    entries = {"bell.json": _read_limited(result_path)}
    document = _complete_result(entries["bell.json"])
    entries.update({name: _load_source(name) for name in _SHIPPED})
    _check_sources(document, entries)
    for kind in ("logical", "compiled"):
        entries[f"{kind}.qasm"] = document["environment"][f"{kind}_qasm"].encode("utf-8")
    entries["REPRODUZIR.md"] = _guide(document["config"]["base_seed"])
    if sum(map(len, entries.values())) > _MAX_TOTAL - 65536:
        raise ValueError("O conteúdo excede o limite total do pacote.")
    manifest = {"format": _FORMAT, "sha256": {name: _digest(data) for name, data in entries.items()}}
    entries["manifest.json"] = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()

    with NamedTemporaryFile(dir=destination.parent, prefix=".bell-", delete=False) as temporary:
        try:
            with ZipFile(temporary, "w") as archive:
                for name in sorted(entries):
                    # Fixed timestamp and permissions give identical bytes for identical inputs.
                    info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                    info.create_system = 3
                    info.external_attr = (stat.S_IFREG | 0o644) << 16
                    archive.writestr(info, entries[name], compress_type=ZIP_DEFLATED)
            temporary.flush()
            os.fsync(temporary.fileno())
            os.link(temporary.name, destination)
        finally:
            os.unlink(temporary.name)


def check_bundle(path: Path) -> None:
    """Verify inventory, hashes, recorded sources, QASM and metrics using standard Python."""
    expected_names = _FILES | {"manifest.json"}
    try:
        with ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) != len(expected_names) or {m.orig_filename for m in members} != expected_names:
                raise ValueError("O ZIP tem itens ausentes, inesperados ou duplicados.")
            if sum(m.file_size for m in members) > _MAX_TOTAL:
                raise ValueError("O ZIP excede o limite total do pacote.")
            entries = {}
            for member in members:
                file_type = stat.S_IFMT(member.external_attr >> 16)
                if (file_type not in (0, stat.S_IFREG) or member.file_size > _MAX_MEMBER
                        or member.flag_bits & 1 or member.compress_type not in (ZIP_DEFLATED, ZIP_STORED)):
                    raise ValueError(f"Tipo, tamanho ou codificação de item inválido: {member.filename}")
                entries[member.filename] = archive.read(member)
    except (BadZipFile, zlib.error) as error:
        raise ValueError("ZIP inválido ou danificado.") from error

    manifest = _json(entries.pop("manifest.json"))
    expected_hashes = {name: _digest(data) for name, data in entries.items()}
    if manifest != {"format": _FORMAT, "sha256": expected_hashes}:
        raise ValueError("Manifesto ou hashes inconsistentes.")
    document = _complete_result(entries["bell.json"])
    _check_sources(document, entries)
    for kind in ("logical", "compiled"):
        expected_qasm = document["environment"][f"{kind}_qasm"].encode("utf-8")
        if entries[f"{kind}.qasm"] != expected_qasm:
            raise ValueError(f"O circuito {kind}.qasm diverge do registro da execução.")
