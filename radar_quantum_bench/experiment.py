"""Coleta de Bell com histórico atômico e verificação independente de Aer."""

import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter_ns
from uuid import UUID, uuid4

from .metrics import EXPECTED, summarize

CONDITIONS = ("ideal", "readout_2pct")
SHOTS, REPETITIONS = 1024, 10
DEFAULT_SEED = 20261120
ROOT = Path(__file__).resolve().parent.parent
SOURCE_PATHS = (
    "requirements.txt",
    *(f"radar_quantum_bench/{name}.py" for name in
      ("__init__", "__main__", "aer", "bundle", "experiment", "metrics")),
)
PROTOCOL_COMMIT = "fb7315f3471e9af9c34f6a135640cf0289140e27"


def source_hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in SOURCE_PATHS}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _config(seed):
    if type(seed) is not int or not 0 <= seed <= 0xffffffff:
        raise ValueError("A semente deve ser um inteiro entre 0 e 4294967295.")
    return {"circuit": "bell", "shots": SHOTS, "repetitions": REPETITIONS,
            "base_seed": seed, "protocol_commit": PROTOCOL_COMMIT}


def _schedule(base_seed):
    for rep in range(-1, REPETITIONS):
        order = CONDITIONS if rep < 0 or rep % 2 == 0 else CONDITIONS[::-1]
        for condition in order:
            offset = 2 * (rep + 1) + CONDITIONS.index(condition)
            yield rep, condition, (base_seed + offset) % (2**32)


def _recalculate(doc):
    summary = summarize(doc["attempts"], SHOTS, REPETITIONS)
    warmups = {row["condition"] for row in doc["attempts"] if row["warmup"] and row["status"] == "ok"}
    summary["complete"] = summary["complete"] and warmups == set(CONDITIONS)
    return summary


def validate(doc):
    """Conferir o esquema, a proveniência declarada e o resumo das contagens."""
    if type(doc["schema_version"]) is not int or doc["schema_version"] != 1:
        raise ValueError("Versão do formato desconhecida.")
    UUID(doc["run_id"])
    config = doc["config"]
    if config != _config(config["base_seed"]):
        raise ValueError("Configuração incompatível com o protocolo Bell.")
    source = doc["source_sha256"]
    if set(source) != set(SOURCE_PATHS) or any(
        not isinstance(digest, str) or len(digest) != 64 or
        any(char not in "0123456789abcdef" for char in digest)
        for digest in source.values()
    ):
        raise ValueError("Identidade das fontes ausente ou inválida.")
    env = doc["environment"]
    versions = env["versions"]
    for key in ("python", "qiskit", "qiskit-aer", "numpy", "scipy"):
        if not isinstance(versions.get(key), str) or not versions[key].strip():
            raise ValueError(f"Versão do ambiente ausente: {key}")
    for kind in ("logical", "compiled"):
        qasm = env[kind + "_qasm"]
        if hashlib.sha256(qasm.encode("utf-8")).hexdigest() != env[kind + "_qasm_sha256"]:
            raise ValueError("Hash do circuito incompatível com o OpenQASM.")
    if env["bit_order"] != "c1c0" or env["bit_map"] != [
        {"compiled_qubit": 0, "classical_bit": 0}, {"compiled_qubit": 1, "classical_bit": 1}
    ]:
        raise ValueError("Ordem ou mapa dos bits incompatível com Bell.")
    noisy = env["noise_model"]["readout_2pct"]
    if (env["noise_model"]["ideal"]["readout_flip_probability"] != 0 or
            noisy["readout_flip_probability"] != 0.02 or
            noisy["type"] != "independent_symmetric_readout" or
            noisy["transition_matrix"] != [[0.98, 0.02], [0.02, 0.98]]):
        raise ValueError("Modelo de ruído incompatível com o protocolo Bell.")
    if doc["theoretical_probabilities"] != EXPECTED:
        raise ValueError("Distribuição teórica inválida.")
    seeds = {(rep, cond): seed for rep, cond, seed in _schedule(config["base_seed"])}
    for item in doc["attempts"]:
        if seeds.get((item["repetition"], item["condition"])) != item["seed"]:
            raise ValueError("Semente da repetição difere do protocolo.")
        if item["condition"] == "ideal" and item["status"] == "ok" and (
            item["counts"].get("01", 0) or item["counts"].get("10", 0)
        ):
            raise ValueError("O circuito Bell ideal produziu bits diferentes.")
    if doc["summary"] != _recalculate(doc):
        raise ValueError("O resumo diverge das contagens ou do histórico.")


def load_result(path):
    with Path(path).open(encoding="utf-8") as stream:
        doc = json.load(stream)
    validate(doc)
    return doc


def _save(path, doc):
    doc["summary"] = _recalculate(doc)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".bell-", delete=False) as stream:
        tmp = Path(stream.name)
        try:
            json.dump(doc, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
    try:
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


@contextmanager
def _exclusive_output(path):
    # Linux/WSL: o lock é liberado pelo kernel mesmo quando o processo é interrompido.
    import fcntl
    with path.with_name(path.name + ".lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Outra coleta está escrevendo neste arquivo.") from exc
        yield


def run(path, base_seed=None, resume=False):
    from .aer import build_runner

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _exclusive_output(path):
        if resume:
            doc = load_result(path)
            if base_seed is not None and base_seed != doc["config"]["base_seed"]:
                raise ValueError("A semente solicitada difere da coleta existente.")
            if doc["source_sha256"] != source_hashes():
                raise ValueError("O código ou o arquivo de dependências mudou desde a coleta.")
            if doc["summary"]["complete"]:
                return doc
        elif path.exists():
            raise FileExistsError("O arquivo já existe. Para retomar, use --resume.")
        else:
            config = _config(DEFAULT_SEED if base_seed is None else base_seed)

        environment, sample = build_runner()
        if resume:
            previous = doc["environment"]
            if {k: v for k, v in environment.items() if k != "compile_ms"} != {
                k: v for k, v in previous.items() if k != "compile_ms"
            }:
                raise ValueError("Circuito, versões ou ambiente diferentes. Inicie outra coleta.")
            for item in doc["attempts"]:
                if item["status"] == "running":
                    item.update(status="failed", error="Interrupted", finished_at=_now())
        else:
            doc = {"schema_version": 1, "run_id": str(uuid4()), "created_at": _now(),
                   "config": config, "source_sha256": source_hashes(),
                   "environment": environment, "theoretical_probabilities": EXPECTED,
                   "sessions": [], "attempts": []}
        doc["sessions"].append({"started_at": _now(), "compile_ms": environment["compile_ms"]})
        _save(path, doc)

        for rep, condition, seed in _schedule(doc["config"]["base_seed"]):
            prior = [x for x in doc["attempts"] if
                     (x["repetition"], x["condition"]) == (rep, condition)]
            if any(x["status"] == "ok" for x in prior):
                continue
            item = {"condition": condition, "repetition": rep, "warmup": rep == -1,
                    "seed": seed, "attempt": 1 + max((x["attempt"] for x in prior), default=0), "status": "running",
                    "started_at": _now()}
            doc["attempts"].append(item)
            _save(path, doc)
            start = perf_counter_ns()
            try:
                counts = sample(condition, SHOTS, seed)
            except BaseException as exc:
                item.update(status="failed", error=type(exc).__name__, finished_at=_now(),
                            elapsed_ms=(perf_counter_ns() - start) / 1e6)
                _save(path, doc)
                raise
            item.update(status="ok", counts=counts, elapsed_ms=(perf_counter_ns() - start) / 1e6,
                        finished_at=_now())
            _save(path, doc)
        validate(doc)
        return doc
