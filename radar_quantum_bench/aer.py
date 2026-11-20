"""Local circuit benchmarks on Qiskit Aer, with one compilation per runner."""

from collections.abc import Callable
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
import platform
from time import perf_counter_ns

from qiskit import QuantumCircuit, qasm3, transpile
from qiskit.circuit import Gate
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, ReadoutError


_SEED_TRANSPILER = 1729


def _cpu_model() -> str:
    # Linux commonly leaves platform.processor() empty.
    try:
        with Path("/proc/cpuinfo").open(encoding="utf-8") as cpuinfo:
            for line in cpuinfo:
                key, _, value = line.partition(":")
                if key.strip() == "model name" and value.strip():
                    return value.strip()
    except OSError:
        pass
    return platform.processor() or platform.machine() or "unknown"


def _resources(circuit: QuantumCircuit) -> dict:
    return {
        "qubits": circuit.num_qubits,
        "measured_qubits": len({
            item.qubits[0] for item in circuit.data if item.operation.name == "measure"
        }),
        "depth": circuit.depth(),
        "two_qubit_gates": sum(
            isinstance(item.operation, Gate) and len(item.qubits) == 2
            for item in circuit.data
        ),
    }


def _logical_circuit(name: str) -> QuantumCircuit:
    if name == "bell":
        circuit = QuantumCircuit(2, 2, name=name)
        circuit.h(0)
        circuit.cx(0, 1)
    elif name == "ghz":
        circuit = QuantumCircuit(3, 3, name=name)
        circuit.h(0)
        circuit.cx(0, 1)
        circuit.cx(1, 2)
    elif name == "bv":
        # The secret 110 is displayed as c2,c1,c0. Qubit 3 is the unmeasured ancilla.
        circuit = QuantumCircuit(4, 3, name=name)
        circuit.x(3)
        circuit.h(range(4))
        circuit.cx(1, 3)
        circuit.cx(2, 3)
        circuit.h(range(3))
    else:
        raise ValueError("circuit must be 'bell', 'ghz' or 'bv'")
    data_bits = range(circuit.num_clbits)
    circuit.measure(data_bits, data_bits)
    return circuit


def build_runner(circuit: str = "bell") -> tuple[dict, Callable[[str, int, int], dict[str, int]]]:
    """Compile once, then sample ideal or noisy readout with an explicit seed."""
    logical = _logical_circuit(circuit)
    bit_width = logical.num_clbits
    bitstrings = tuple(format(i, f"0{bit_width}b") for i in range(2**bit_width))
    basis_gates = ["h", "cx", "x"] if circuit == "bv" else ["h", "cx"]

    start_ns = perf_counter_ns()
    compiled = transpile(
        logical, basis_gates=basis_gates, optimization_level=0,
        seed_transpiler=_SEED_TRANSPILER,
    )
    compile_ms = (perf_counter_ns() - start_ns) / 1_000_000

    # A one-bit readout channel is applied separately to each measured qubit.
    readout_matrix = [[0.98, 0.02], [0.02, 0.98]]
    noisy = NoiseModel(basis_gates=basis_gates)
    noisy.add_all_qubit_readout_error(ReadoutError(readout_matrix))
    options = {
        "method": "statevector",
        "device": "CPU",
        "max_parallel_threads": 1,
        "max_parallel_experiments": 1,
        "max_parallel_shots": 1,
    }
    backends = {
        "ideal": AerSimulator(**options),
        "readout_2pct": AerSimulator(noise_model=noisy, **options),
    }
    logical_qasm = qasm3.dumps(logical)
    compiled_qasm = qasm3.dumps(compiled)
    metadata = {
        "logical_qasm": logical_qasm,
        "compiled_qasm": compiled_qasm,
        "logical_qasm_sha256": sha256(logical_qasm.encode("utf-8")).hexdigest(),
        "compiled_qasm_sha256": sha256(compiled_qasm.encode("utf-8")).hexdigest(),
        "seed_transpiler": _SEED_TRANSPILER,
        "optimization_level": 0,
        "basis_gates": basis_gates,
        "compile_ms": compile_ms,
        "bit_order": "".join(f"c{i}" for i in reversed(range(bit_width))),
        "bit_map": [
            {
                "compiled_qubit": compiled.find_bit(item.qubits[0]).index,
                "classical_bit": compiled.find_bit(item.clbits[0]).index,
            }
            for item in compiled.data if item.operation.name == "measure"
        ],
        "logical_resources": _resources(logical),
        "compiled_resources": _resources(compiled),
        "noise_model": {
            "ideal": {"readout_flip_probability": 0.0},
            "readout_2pct": {
                "type": "independent_symmetric_readout",
                "readout_flip_probability": 0.02,
                "transition_matrix": readout_matrix,
            },
        },
        "simulator": {"name": "AerSimulator", **options},
        "hardware": {"cpu": _cpu_model(), "architecture": platform.machine()},
        "versions": {
            "python": platform.python_version(),
            **{name: version(name) for name in ("qiskit", "qiskit-aer", "numpy", "scipy")},
        },
    }

    def sample(condition: str, shots: int, seed: int) -> dict[str, int]:
        if condition not in backends:
            raise ValueError("condition must be 'ideal' or 'readout_2pct'")
        if type(shots) is not int or shots <= 0:
            raise ValueError("shots must be a positive integer")
        if type(seed) is not int or not 0 <= seed <= 0xFFFFFFFF:
            raise ValueError("seed must be an unsigned 32-bit integer")
        result = backends[condition].run(compiled, shots=shots, seed_simulator=seed).result()
        if not result.success:
            raise RuntimeError(f"Aer experiment failed: {result.status}")
        observed = result.get_counts(0)
        if observed.keys() - set(bitstrings) or sum(observed.values()) != shots:
            raise RuntimeError("Aer returned unexpected bitstrings or incomplete counts")
        return {key: int(observed.get(key, 0)) for key in bitstrings}

    return metadata, sample
