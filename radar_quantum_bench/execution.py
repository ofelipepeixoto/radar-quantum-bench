"""Supervisão Linux/WSL de uma coleta em processo separado e com limites."""

from dataclasses import dataclass
import json
from math import isfinite
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import tempfile
from time import monotonic, sleep
from uuid import UUID


@dataclass(frozen=True)
class WorkerLimits:
    timeout_seconds: float = 120.0
    memory_mib: int = 2048

    def __post_init__(self):
        if (type(self.timeout_seconds) not in (int, float)
                or not isfinite(self.timeout_seconds) or not 0 < self.timeout_seconds <= 86400):
            raise ValueError("O prazo precisa ser positivo, finito e de até 86400 segundos.")
        if type(self.memory_mib) is not int or not 256 <= self.memory_mib <= 16384:
            raise ValueError("A memória virtual precisa ser um inteiro entre 256 e 16384 MiB.")


class ExecutionFailure(Exception):
    """Erro operacional reduzido a uma categoria, sem saída bruta do processo."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


_MEMORY_EXIT = 75
_SCIENCE_EXIT = 76
_SETUP_EXIT = 77


def _prepare_child(parent_pid, memory_mib):
    """Set a death signal before importing Aer, including the parent-exit race."""
    if sys.platform != "linux" or os.getppid() != parent_pid:
        raise RuntimeError("A supervisão requer Linux/WSL e um processo pai ativo.")
    import ctypes
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:  # PR_SET_PDEATHSIG
        raise OSError("Não foi possível configurar o encerramento com o supervisor.")
    if os.getppid() != parent_pid:
        os.kill(os.getpid(), signal.SIGKILL)
    maximum = memory_mib * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (maximum, maximum))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def _science_command(path, job, limits):
    return [sys.executable, "-B", "-m", "radar_quantum_bench.execution", "child",
            str(os.getpid()), str(limits.memory_mib), str(path), job["circuit"], str(job["base_seed"])]


def _reap(process, *, block=False):
    pid, status, usage = os.wait4(process.pid, 0 if block else os.WNOHANG)
    if not pid:
        return None
    process.returncode = os.waitstatus_to_exitcode(status)
    return process.returncode, int(usage.ru_maxrss)


def _stop_group(process):
    """The worker owns a new process session, so signals do not reach the API."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    stop = monotonic() + 0.2
    result = None
    while result is None and monotonic() < stop:
        result = _reap(process)
        if result is None:
            sleep(0.01)
    # Kill the group even if its leader already exited, covering descendants.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    return result if result is not None else _reap(process, block=True)


def _supervise(command, limits, *, lock_fd=None):
    """Internal transport primitive. Production supplies only _science_command."""
    environment = dict(os.environ)
    environment.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1",
                       NUMEXPR_NUM_THREADS="1")
    started = monotonic()
    process = subprocess.Popen(
        command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env=environment, start_new_session=True,
        pass_fds=() if lock_fd is None else (lock_fd,),
    )
    result = None
    timed_out = False
    try:
        while result is None:
            remaining = limits.timeout_seconds - (monotonic() - started)
            if remaining <= 0:
                timed_out = True
                result = _stop_group(process)
                break
            result = _reap(process)
            if result is not None:
                break
            sleep(min(0.02, remaining))
        return {"exit_code": result[0], "peak_rss_kib": result[1],
                "elapsed_ms": round((monotonic() - started) * 1000, 6), "timed_out": timed_out}
    finally:
        if process.returncode is None:
            _stop_group(process)


def _job_id(value):
    parsed = UUID(value)
    if parsed.version != 4 or str(parsed) != value:
        raise ValueError("Identificador de execução inválido.")
    return value


def _save_receipt(root, receipt):
    folder = Path(root) / "executions" / receipt["job_id"]
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=folder,
                                         prefix=".execution-", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(receipt, stream, sort_keys=True, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(folder / f"{receipt['attempt_id']}.json")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def execute_job(store, job, limits, *, lock_fd=None):
    """Run one authorized catalog job and write a separate operational receipt.

    Scientific JSONs and their hashes remain unchanged. A hard-killed supervisor
    can leave no receipt; the durable queue attempt records recovery separately.
    """
    if not isinstance(limits, WorkerLimits):
        raise ValueError("Limites de execução inválidos.")
    job_id, attempt_id = _job_id(job["id"]), _job_id(job["attempt_id"])
    if job["circuit"] not in ("bell", "ghz", "bv") or type(job["base_seed"]) is not int \
            or not 0 <= job["base_seed"] <= 4294967295:
        raise ValueError("Configuração de execução inválida.")
    path = store.result_path(job_id).resolve()
    receipt = {"schema_version": "rqb-execution/1", "job_id": job_id, "attempt_id": attempt_id,
               "limits": {"wall_seconds": limits.timeout_seconds, "virtual_memory_mib": limits.memory_mib},
               "elapsed_ms": None, "peak_rss_kib": None, "exit_code": None,
               "status": "failed", "error_code": "ExecutionSetupFailed"}
    started = monotonic()
    try:
        observed = _supervise(_science_command(path, job, limits), limits, lock_fd=lock_fd)
        receipt.update({key: observed[key] for key in ("elapsed_ms", "peak_rss_kib", "exit_code")})
        code = ("TimeLimitExceeded" if observed["timed_out"] else
                "MemoryLimitExceeded" if observed["exit_code"] == _MEMORY_EXIT else
                "ExecutionSetupFailed" if observed["exit_code"] == _SETUP_EXIT else
                None if observed["exit_code"] == 0 else "ExecutionChildFailed")
        receipt.update(status="completed" if code is None else "failed", error_code=code)
    except (KeyboardInterrupt, SystemExit):
        receipt.update(status="interrupted", error_code="ExecutionInterrupted",
                       elapsed_ms=round((monotonic() - started) * 1000, 6))
        raise
    except Exception:
        receipt.update(status="failed", error_code="ExecutionSetupFailed",
                       elapsed_ms=round((monotonic() - started) * 1000, 6))
    finally:
        # Never include subprocess stderr, filesystem paths or untrusted text.
        _save_receipt(store.root, receipt)
    if receipt["error_code"] is not None:
        raise ExecutionFailure(receipt["error_code"])
    return receipt


def _child(arguments):
    try:
        parent_pid, memory_mib = int(arguments[0]), int(arguments[1])
        WorkerLimits(memory_mib=memory_mib)
        _prepare_child(parent_pid, memory_mib)
    except Exception:
        return _SETUP_EXIT
    try:
        # Aer and NumPy are loaded only after RLIMIT_AS and the death signal.
        from .experiment import run
        path = Path(arguments[2])
        run(path, base_seed=int(arguments[4]), circuit=arguments[3], resume=path.exists())
        return 0
    except MemoryError:
        return _MEMORY_EXIT
    except Exception:
        return _SCIENCE_EXIT


def main(argv=None):
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 6 or arguments[0] != "child":
        return _SETUP_EXIT
    return _child(arguments[1:])


if __name__ == "__main__":
    raise SystemExit(main())
