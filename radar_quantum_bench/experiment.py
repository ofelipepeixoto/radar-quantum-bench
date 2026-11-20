"""Coleta de circuitos versionados com histórico atômico e verificação local."""

import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter_ns
from uuid import UUID, uuid4

from .metrics import specifications, summarize, theoretical_probabilities

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
# Catalog revision 1: exact OpenQASM from the pinned Qiskit 2.6.2 compiler,
# optimization_level=0, seed_transpiler=1729. Changes require a new reference.
QASM_HASHES = {
    "bell": (
        "9bb22cb4e9dfee89afa77e87040341a539ffe9935cb5945e1882ccfa56af22af",
        "9bb22cb4e9dfee89afa77e87040341a539ffe9935cb5945e1882ccfa56af22af",
    ),
    "ghz": (
        "5ea37c5e5f1ea1645f701166b8e84b1f88ed7251f185a9e5742e889b9867f1ee",
        "5ea37c5e5f1ea1645f701166b8e84b1f88ed7251f185a9e5742e889b9867f1ee",
    ),
    "bv": (
        "27945ca83cc178faf20edd5c5e493c4b694c886cd6de872b6a400a79d5781840",
        "15698f1212391c06ef8ddf9c5d6a6771531a1a427565475659eb72669b0c4bc1",
    ),
}


def source_hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in SOURCE_PATHS}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _config(seed, circuit="bell"):
    if type(seed) is not int or not 0 <= seed <= 0xffffffff:
        raise ValueError("A semente deve ser um inteiro entre 0 e 4294967295.")
    specifications(circuit)
    return {"circuit": circuit, "shots": SHOTS, "repetitions": REPETITIONS,
            "base_seed": seed, "protocol_commit": PROTOCOL_COMMIT}


def _schedule(base_seed):
    for rep in range(-1, REPETITIONS):
        order = CONDITIONS if rep < 0 or rep % 2 == 0 else CONDITIONS[::-1]
        for condition in order:
            offset = 2 * (rep + 1) + CONDITIONS.index(condition)
            yield rep, condition, (base_seed + offset) % (2**32)


def _recalculate(doc):
    summary = summarize(doc["attempts"], SHOTS, REPETITIONS, doc["config"]["circuit"])
    warmups = {row["condition"] for row in doc["attempts"] if row["warmup"] and row["status"] == "ok"}
    summary["complete"] = summary["complete"] and warmups == set(CONDITIONS)
    return summary


def validate(doc):
    """Conferir o esquema, a proveniência declarada e o resumo das contagens."""
    if type(doc["schema_version"]) is not int or doc["schema_version"] not in (1, 2):
        raise ValueError("Versão do formato desconhecida.")
    UUID(doc["run_id"])
    config = doc["config"]
    circuit = config["circuit"]
    spec = specifications(circuit)
    if doc["schema_version"] == 1 and circuit != "bell":
        raise ValueError("O formato antigo está restrito ao circuito Bell.")
    if config != _config(config["base_seed"], circuit):
        raise ValueError("Configuração incompatível com o protocolo.")
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
    for index, kind in enumerate(("logical", "compiled")):
        qasm = env[kind + "_qasm"]
        if hashlib.sha256(qasm.encode("utf-8")).hexdigest() != env[kind + "_qasm_sha256"]:
            raise ValueError("Hash do circuito incompatível com o OpenQASM.")
        if env[kind + "_qasm_sha256"] != QASM_HASHES[circuit][index]:
            raise ValueError("O OpenQASM difere da revisão do circuito de referência.")
        resources = env[kind + "_resources"]
        if (resources["qubits"] != spec["qubits"] or
                resources["measured_qubits"] != spec["measured"]):
            raise ValueError("Os recursos divergem do circuito declarado.")
    if env["bit_order"] != "".join(f"c{i}" for i in reversed(range(spec["measured"]))) or env["bit_map"] != [
        {"compiled_qubit": i, "classical_bit": i} for i in range(spec["measured"])
    ]:
        raise ValueError("Ordem ou mapa dos bits incompatível com o circuito.")
    noisy = env["noise_model"]["readout_2pct"]
    if (env["noise_model"]["ideal"]["readout_flip_probability"] != 0 or
            noisy["readout_flip_probability"] != 0.02 or
            noisy["type"] != "independent_symmetric_readout" or
            noisy["transition_matrix"] != [[0.98, 0.02], [0.02, 0.98]]):
        raise ValueError("Modelo de ruído incompatível com o protocolo.")
    if doc["theoretical_probabilities"] != theoretical_probabilities(circuit):
        raise ValueError("Distribuição teórica inválida.")
    calculated = _recalculate(doc)
    seeds = {(rep, cond): seed for rep, cond, seed in _schedule(config["base_seed"])}
    for item in doc["attempts"]:
        if seeds.get((item["repetition"], item["condition"])) != item["seed"]:
            raise ValueError("Semente da repetição difere do protocolo.")
        if item["condition"] == "ideal" and item["status"] == "ok" and any(
            value and spec["ideal"].get(word, 0) == 0 for word, value in item["counts"].items()
        ):
            raise ValueError("O circuito ideal produziu uma leitura fora da referência.")
    if doc["summary"] != calculated:
        raise ValueError("O resumo diverge das contagens ou do histórico.")


def _unique_fields(pairs):
    fields = {}
    for name, value in pairs:
        if name in fields:
            raise ValueError(f"Campo JSON duplicado: {name}")
        fields[name] = value
    return fields


def load_result(path):
    with Path(path).open(encoding="utf-8") as stream:
        doc = json.load(stream, object_pairs_hook=_unique_fields)
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


def run(path, base_seed=None, resume=False, circuit=None):
    from .aer import build_runner

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _exclusive_output(path):
        if resume:
            doc = load_result(path)
            if circuit is not None and circuit != doc["config"]["circuit"]:
                raise ValueError("O circuito solicitado difere da coleta existente.")
            circuit = doc["config"]["circuit"]
            if base_seed is not None and base_seed != doc["config"]["base_seed"]:
                raise ValueError("A semente solicitada difere da coleta existente.")
            if doc["source_sha256"] != source_hashes():
                raise ValueError("O código ou o arquivo de dependências mudou desde a coleta.")
            if doc["summary"]["complete"]:
                return doc
        elif path.exists():
            raise FileExistsError("O arquivo já existe. Para retomar, use --resume.")
        else:
            circuit = "bell" if circuit is None else circuit
            defaults = {"bell": DEFAULT_SEED, "ghz": DEFAULT_SEED + 100, "bv": DEFAULT_SEED + 200}
            if circuit not in defaults:
                raise ValueError("Circuito desconhecido.")
            config = _config(defaults[circuit] if base_seed is None else base_seed, circuit)

        environment, sample = build_runner() if circuit == "bell" else build_runner(circuit)
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
            doc = {"schema_version": 2, "run_id": str(uuid4()), "created_at": _now(),
                   "config": config, "source_sha256": source_hashes(),
                   "environment": environment, "theoretical_probabilities": theoretical_probabilities(circuit),
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
